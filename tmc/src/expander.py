"""Macro expander: expand σ/γ/σ0/αβ shorthands and α-parameterized states.

Phase 1: Expand sigma_0, sigma, gamma, alpha, beta, alpha_beta meta-symbols
into concrete tape-symbol transitions.

Phase 2: Expand α-parameterized states into N concrete copies, one per α value.
"""
from __future__ import annotations
from copy import deepcopy
from .ast import Program, Routine, State, Transition


# Default tape alphabet for the UTM project. These are the symbols that
# appear in the formalism doc and in Samhain's TMVegs/ examples.
SIGMA_0 = ['0', '1', '#']            # data symbols
ALPHA_VALUES = ['0', '1', '#']        # α can take these values
SIGMA = SIGMA_0 + ['H', 'H0', 'H1']  # σ adds H-marked variants
GAMMA = SIGMA + [' ', '[']           # γ adds blank and left-marker

SHORTHAND_KEYS = {
    'sigma_0': SIGMA_0,
    'sigma': SIGMA,
    'gamma': GAMMA,
    'alpha': ALPHA_VALUES,
    'beta': ['0', '1', '#'],     # β is sometimes used like α
    'alpha_beta': SIGMA_0,        # αβ as a write target gets handled specially
}


def expand(program: Program) -> Program:
    """Run all expansion passes over the program."""
    for routine in program.routines.values():
        _expand_shorthands(routine)
        _expand_alpha_states(routine)
    return program


def _expand_shorthands(routine: Routine) -> None:
    """Expand σ0/γ/etc keys in transitions to concrete read symbols.

    Precedence: more-specific shorthands override more-general ones. This is
    achieved by tracking which (state, symbol) pairs already have concrete
    transitions, and not overwriting them.
    """
    for state in routine.states.values():
        new_trans: list[Transition] = []
        # First pass: collect concrete-symbol transitions
        seen_pairs: set[str] = set()  # symbols already covered

        # Sort: concrete symbols first, then sigma_0, sigma, gamma (most general last)
        ordered = sorted(state.transitions, key=lambda t: _shorthand_priority(t))
        for t in ordered:
            expanded_reads = []
            for sym in t.read:
                if sym in SHORTHAND_KEYS:
                    expanded_reads.extend(SHORTHAND_KEYS[sym])
                else:
                    expanded_reads.append(sym)

            # Filter out symbols already covered by higher-priority entries
            actual = [s for s in expanded_reads if s not in seen_pairs]
            if not actual and t.read:
                # entirely shadowed - skip
                continue

            new_t = Transition(
                read=actual if actual else t.read,
                write=t.write,
                direction=t.direction,
                target=t.target,
                is_subroutine_call=t.is_subroutine_call,
                exit_dispatch=dict(t.exit_dispatch),
            )

            # Handle αβ-style write targets: if write is 'alpha_beta' or similar,
            # we'll need per-symbol writes. For now, if write is a meta-symbol
            # and there are multiple read symbols, expand into one transition each.
            if new_t.write in ('alpha', 'alpha_beta', 'sigma_0', 'sigma', 'gamma'):
                for sym in actual:
                    sub_t = deepcopy(new_t)
                    sub_t.read = [sym]
                    sub_t.write = sym  # identity write
                    new_trans.append(sub_t)
                    seen_pairs.add(sym)
            else:
                new_trans.append(new_t)
                for sym in actual:
                    seen_pairs.add(sym)

        state.transitions = new_trans


def _shorthand_priority(t: Transition) -> int:
    """Lower priority = processed first (more specific wins)."""
    if not t.read:
        return -1  # epsilon/dispatch entries first
    if any(r in ('gamma',) for r in t.read):
        return 3
    if any(r in ('sigma',) for r in t.read):
        return 2
    if any(r in ('sigma_0', 'alpha', 'beta', 'alpha_beta') for r in t.read):
        return 1
    return 0  # concrete symbols


def _expand_alpha_states(routine: Routine) -> None:
    """Phase 2: expand α-parameterized states into N concrete copies.

    A state whose name contains 'alpha' (as a word component) is α-parameterized.
    For each transition that targets such a state, we create a copy of the state
    family with α bound to the symbol on which the transition fires.

    For now: detect states named like 'seen_alpha', 'seen_alpha_to_alphap', etc.
    Replace them with copies seen_0, seen_1, seen_sharp, etc.
    """
    # Find α-parameterized states
    alpha_states = [name for name in routine.states
                    if 'alpha' in name.lower().split('_')
                    or name.lower().endswith('_alpha')
                    or name.lower().startswith('alpha_')]

    if not alpha_states:
        return

    # For each α-state, generate copies for each α value
    new_states: dict[str, State] = {}
    for orig_name in alpha_states:
        orig = routine.states[orig_name]
        for alpha_val in ALPHA_VALUES:
            new_name = _substitute_alpha(orig_name, alpha_val)
            new_state = State(name=new_name)
            for t in orig.transitions:
                new_t = deepcopy(t)
                # Replace 'alpha' write with the bound value
                if new_t.write == 'alpha':
                    new_t.write = alpha_val
                # Replace 'alpha' in target with bound value
                if new_t.target and 'alpha' in new_t.target.lower():
                    new_t.target = _substitute_alpha(new_t.target, alpha_val)
                # Replace 'alpha' in exit_dispatch targets
                for k, v in list(new_t.exit_dispatch.items()):
                    if 'alpha' in v.lower():
                        new_t.exit_dispatch[k] = _substitute_alpha(v, alpha_val)
                new_state.transitions.append(new_t)
            new_states[new_name] = new_state

    # Now rewrite all transitions in OTHER states that target an α-state
    for state in routine.states.values():
        if state.name in alpha_states:
            continue
        new_transitions = []
        for t in state.transitions:
            if t.target in alpha_states:
                # Need to fan out: one transition per α value, with target bound
                for sym in t.read:
                    if sym in ALPHA_VALUES:
                        sub_t = deepcopy(t)
                        sub_t.read = [sym]
                        sub_t.target = _substitute_alpha(t.target, sym)
                        new_transitions.append(sub_t)
                    else:
                        # Non-α read - just keep it pointing at first α copy
                        sub_t = deepcopy(t)
                        sub_t.read = [sym]
                        sub_t.target = _substitute_alpha(t.target, ALPHA_VALUES[0])
                        new_transitions.append(sub_t)
            else:
                new_transitions.append(t)
        state.transitions = new_transitions

    # Remove originals, add expansions
    for n in alpha_states:
        del routine.states[n]
    routine.states.update(new_states)


def _substitute_alpha(name: str, val: str) -> str:
    """Replace 'alpha' token in a state name with the bound value."""
    # Handle common forms: seen_alpha -> seen_0, alpha_to_alphap -> 0_to_0p
    val_safe = {'#': 'sharp', "'": 'p'}.get(val, val)
    # Replace token-by-token
    parts = name.split('_')
    new_parts = []
    for p in parts:
        if p.lower() == 'alpha':
            new_parts.append(val_safe)
        elif p.lower() == "alpha'" or p.lower() == 'alphap':
            new_parts.append(val_safe + 'p')
        else:
            new_parts.append(p)
    return '_'.join(new_parts)
