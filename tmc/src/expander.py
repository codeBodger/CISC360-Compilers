"""Expand α-parameterized states.

Semantics (per Samhain's nesting-minimising formalism):
- A state whose name contains the token 'alpha' is α-parameterized.
  It is expanded into N copies, one per alphabet value v.
  In the resulting state, 'alpha' in the name → v.
  Any '-> alpha\\'' suffix in the name is dropped after expansion.
- The "outer α" of a copy is its bound value v.
- Inside an α-state's transitions:
    * 'alpha' in a READ slot = iterates over the alphabet (fan out one transition per value)
    * 'alpha' in a TARGET name refers to the CURRENT inner read value (the iteration var)
    * 'alpha'' anywhere = the OUTER state's bound value
- Self-loop optimization: if write == read AND target == current state, drop the write
  (so the output shows {R} or {L} without redundant write).
"""
from __future__ import annotations
import re
from copy import deepcopy
from .ast import Program, Routine, State, Transition

# Regex for stripping '-> alpha\'' suffix from state names
_ALPHA_SUFFIX_RE = re.compile(r"\s*->\s*alpha'\s*$")


def expand(program: Program) -> Program:
    for routine in program.routines.values():
        _expand_alpha_states(routine, program)
    return program


def _expand_alpha_states(routine: Routine, program: Program) -> None:
    """Expand all α-parameterized states in this routine."""
    alphabet = routine.alphabet or (program.main.alphabet if program.main else [])
    if not alphabet:
        return

    alpha_state_names = [n for n in routine.states if _is_alpha_state(n)]
    if not alpha_state_names:
        return

    # Build a map: original α-state name → list of (bound_value, expanded_name)
    expansion_map: dict[str, dict[str, str]] = {}
    for orig in alpha_state_names:
        expansion_map[orig] = {v: _strip_and_substitute(orig, v) for v in alphabet}

    new_states: dict[str, State] = {}

    # Expand each α-state
    for orig_name in alpha_state_names:
        orig_state = routine.states[orig_name]
        for outer_alpha in alphabet:
            new_name = expansion_map[orig_name][outer_alpha]
            new_state = State(name=new_name)
            for t in orig_state.transitions:
                new_transitions = _expand_transition(
                    t, outer_alpha, alphabet, expansion_map, new_name)
                new_state.transitions.extend(new_transitions)
            new_states[new_name] = new_state

    # Rewrite transitions in NON-α states whose targets are α-states
    for state in routine.states.values():
        if state.name in alpha_state_names:
            continue
        rewritten: list[Transition] = []
        for t in state.transitions:
            rewritten.extend(_rewrite_outside_transition(
                t, alpha_state_names, alphabet, expansion_map))
        state.transitions = rewritten

    for n in alpha_state_names:
        del routine.states[n]
    routine.states.update(new_states)


def _is_alpha_state(name: str) -> bool:
    """A state name is α-parameterized if it contains 'alpha' as a token."""
    tokens = re.split(r"[\s\-\>\<,]+", name)
    return any(tok.rstrip("'") == 'alpha' for tok in tokens)


def _strip_and_substitute(name: str, val: str) -> str:
    """Substitute 'alpha' with val in a state name, dropping '-> alpha\\'' suffix."""
    # First strip the "-> alpha'" suffix if present (it's decorative)
    s = _ALPHA_SUFFIX_RE.sub('', name)
    # Replace remaining 'alpha' tokens (use word boundary-ish approach)
    # Replace "alpha'" first, then bare "alpha"
    s = s.replace("alpha'", val + "'")
    s = re.sub(r'\balpha\b', val, s)
    return s


def _substitute_target(target: str, current_v: str, outer_alpha: str,
                       alphabet: list[str], expansion_map: dict) -> str:
    """Substitute alpha and alpha' in a target name.
       alpha = current_v (the inner iteration value)
       alpha' = outer_alpha (the state's bound value)
    """
    if target in expansion_map:
        # Direct reference to an α-state — pick the expansion bound to current_v
        return expansion_map[target].get(current_v, target)
    # Otherwise substitute textually: alpha' → outer, alpha → current_v
    s = target
    s = s.replace("alpha'", outer_alpha + "'")
    s = re.sub(r'\balpha\b', current_v, s)
    # Strip "-> X'" suffix that may remain
    s = _ALPHA_SUFFIX_RE.sub('', s)
    s = re.sub(r"\s*->\s*[^\s]+\s*$", '', s) if 'alpha' not in s and "'" in s else s
    return s


def _expand_transition(t: Transition, outer_alpha: str, alphabet: list[str],
                       expansion_map: dict, current_state_name: str) -> list[Transition]:
    """Expand a transition that lives inside an α-state.

    If a read symbol is 'alpha', fan out one transition per alphabet value.
    Otherwise, substitute alpha → read symbol (the read is a literal alphabet member),
    and alpha' → outer_alpha.
    """
    out: list[Transition] = []
    for read_sym in t.read:
        if read_sym == 'alpha':
            for v in alphabet:
                new_t = _make_concrete(t, v, outer_alpha, alphabet,
                                       expansion_map, current_state_name)
                out.append(new_t)
        else:
            new_t = _make_concrete(t, read_sym, outer_alpha, alphabet,
                                   expansion_map, current_state_name)
            out.append(new_t)
    return out


def _make_concrete(t: Transition, current_v: str, outer_alpha: str,
                   alphabet: list[str], expansion_map: dict,
                   current_state_name: str) -> Transition:
    """Produce one concrete transition by binding alpha=current_v, alpha'=outer_alpha."""
    new_t = deepcopy(t)
    new_t.read = [current_v]

    # Substitute write
    if new_t.write is not None:
        if new_t.write == 'alpha':
            new_t.write = current_v
        elif new_t.write == "alpha'":
            new_t.write = outer_alpha
        elif 'alpha' in new_t.write:
            new_t.write = new_t.write.replace("alpha'", outer_alpha)
            new_t.write = re.sub(r'\balpha\b', current_v, new_t.write)

    # Substitute target
    if new_t.target is not None:
        new_t.target = _substitute_target(
            new_t.target, current_v, outer_alpha, alphabet, expansion_map)

    # Substitute exit_dispatch values
    for k, v in list(new_t.exit_dispatch.items()):
        if v:
            new_t.exit_dispatch[k] = _substitute_target(
                v, current_v, outer_alpha, alphabet, expansion_map)

    # Self-loop optimization: if write == read and target == current state, drop write
    if (new_t.write is not None and new_t.write == new_t.read[0]
            and new_t.target == current_state_name):
        new_t.write = None

    return new_t


def _rewrite_outside_transition(t: Transition, alpha_state_names: list[str],
                                alphabet: list[str], expansion_map: dict) -> list[Transition]:
    """Rewrite transitions in non-α-states that target α-states.

    For each read symbol that's an alphabet value, target the matching α-state copy.
    If read is 'alpha', fan out one per alphabet value.
    """
    if t.target not in alpha_state_names:
        # No α-target. Still: if read symbol is 'alpha', fan out.
        if 'alpha' in t.read:
            out = []
            for av in alphabet:
                new_t = deepcopy(t)
                new_t.read = [av if r == 'alpha' else r for r in t.read]
                out.append(new_t)
            return out
        return [t]

    # Targets an α-state. Each read sym determines which α-copy.
    out: list[Transition] = []
    for r in t.read:
        if r == 'alpha':
            for av in alphabet:
                new_t = deepcopy(t)
                new_t.read = [av]
                new_t.target = expansion_map[t.target][av]
                out.append(new_t)
        elif r in alphabet:
            new_t = deepcopy(t)
            new_t.read = [r]
            new_t.target = expansion_map[t.target][r]
            out.append(new_t)
        else:
            new_t = deepcopy(t)
            new_t.read = [r]
            # Read isn't an alphabet member; default to first alphabet value
            new_t.target = expansion_map[t.target][alphabet[0]]
            out.append(new_t)
    return out
