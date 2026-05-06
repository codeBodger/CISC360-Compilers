"""Resolve ε-transitions and merge halt states.

After linking, ε-only states (those whose only transition is an unconditional
epsilon-jump) get inlined at their callers. Halt states are kept as-is.

This is gentle: a state with multiple transitions, even if some are ε, is
preserved.
"""
from __future__ import annotations
from .ast import Routine, State, Transition


def resolve_epsilons(routine: Routine) -> Routine:
    """Collapse ε-only states by rewriting references to their target."""
    epsilon_target: dict[str, str] = {}
    for name, state in routine.states.items():
        eps_t = _epsilon_only(state)
        if eps_t is not None and eps_t.target:
            epsilon_target[name] = eps_t.target

    def resolve(name: str, seen=None) -> str:
        seen = seen or set()
        if name in seen or name not in epsilon_target:
            return name
        seen.add(name)
        return resolve(epsilon_target[name], seen)

    # Rewrite targets
    for state in routine.states.values():
        for t in state.transitions:
            if t.target and t.target in epsilon_target:
                t.target = resolve(t.target)
            for k, v in list(t.exit_dispatch.items()):
                if v in epsilon_target:
                    t.exit_dispatch[k] = resolve(v)

    # Update start state
    if routine.start_state and routine.start_state in epsilon_target:
        routine.start_state = resolve(routine.start_state)

    # Remove ε-only states
    for name in list(epsilon_target.keys()):
        s = routine.states.get(name)
        if s and len(s.transitions) == 1 and not s.transitions[0].read:
            del routine.states[name]

    return routine


def _epsilon_only(state: State) -> Transition | None:
    if state.is_halt:
        return None
    if len(state.transitions) != 1:
        return None
    t = state.transitions[0]
    if not t.read and t.target and not t.is_subroutine_call:
        return t
    return None


def complete_transitions(routine: Routine, tape_symbols: list[str]) -> Routine:
    """For each non-halt state, ensure every tape symbol has a defined transition.
    Undefined ones get → reject (matching Samhain's a.out completion convention).
    """
    if not tape_symbols:
        return routine
    reject_state = routine.reject_name
    for state in list(routine.states.values()):
        if state.is_halt:
            continue
        # Determine which symbols are already covered
        covered: set[str] = set()
        for t in state.transitions:
            for r in t.read:
                covered.add(r)
        missing = [s for s in tape_symbols if s not in covered]
        if missing:
            state.transitions.append(Transition(
                read=missing, target=reject_state, direction='R'))
    return routine


def remove_unreachable(routine: Routine, keep_unreachable: bool = False) -> Routine:
    """Remove states not reachable from start.

    If keep_unreachable=True, unreachable states are kept (Samhain's debug
    request). Halt states are always kept.
    """
    if keep_unreachable:
        return routine
    if not routine.start_state:
        return routine
    reachable: set[str] = set()
    stack = [routine.start_state]
    halt_kinds = (routine.accept_name, routine.reject_name)
    for hn in halt_kinds:
        if hn in routine.states:
            reachable.add(hn)
    while stack:
        name = stack.pop()
        if name in reachable or name not in routine.states:
            continue
        reachable.add(name)
        for t in routine.states[name].transitions:
            if t.target:
                stack.append(t.target)
            for v in t.exit_dispatch.values():
                if v:
                    stack.append(v)
    for name in list(routine.states):
        if name not in reachable:
            del routine.states[name]
    return routine
