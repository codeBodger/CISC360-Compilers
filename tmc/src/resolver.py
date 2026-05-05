"""Resolve epsilon transitions and merge end-states.

After linking, the flat routine may contain:
- States that have only epsilon transitions (jump to another state without reading)
- Multiple accept/reject/done states scattered around

This module:
1. Resolves epsilon-only states by inlining them at their callers
2. Merges all 'accept' states into one 'accept', same for 'reject'
3. Removes unreachable states
"""
from __future__ import annotations
from copy import deepcopy
from .ast import Routine, State, Transition


def resolve_epsilons(routine: Routine) -> Routine:
    """Resolve epsilon transitions in-place.

    A state has an 'epsilon transition' if it has a Transition with no read
    symbols and a target. We collapse chains of such states.
    """
    # Build a map: state_name -> ultimate epsilon target (after following chains)
    epsilon_target: dict[str, str] = {}
    for name, state in routine.states.items():
        eps_t = _epsilon_transition(state)
        if eps_t is not None and eps_t.target:
            epsilon_target[name] = eps_t.target

    # Resolve transitive chains
    def resolve(name: str, seen=None) -> str:
        seen = seen or set()
        if name in seen:
            return name  # cycle, give up
        if name not in epsilon_target:
            return name
        seen.add(name)
        return resolve(epsilon_target[name], seen)

    # Rewrite all transitions: any target that has an epsilon-resolution is replaced
    for state in routine.states.values():
        for t in state.transitions:
            if t.target and t.target in epsilon_target:
                t.target = resolve(t.target)

    # Update start state if it's an epsilon-only state
    if routine.start_state and routine.start_state in epsilon_target:
        routine.start_state = resolve(routine.start_state)

    # Remove epsilon-only states (they're now bypassed)
    for name in list(epsilon_target.keys()):
        # Only remove if the state is purely epsilon (no other transitions)
        state = routine.states.get(name)
        if state and len(state.transitions) == 1 and not state.transitions[0].read:
            del routine.states[name]

    return routine


def _epsilon_transition(state: State) -> Transition | None:
    """Return the state's epsilon transition if it has exactly one and no others."""
    if len(state.transitions) != 1:
        return None
    t = state.transitions[0]
    if not t.read and t.target and not t.is_subroutine_call:
        return t
    return None


def merge_end_states(routine: Routine) -> Routine:
    """Collapse all accept/reject/done states into single canonical halts.

    Preserves the user's naming convention: if the routine consistently uses
    'success'/'failure', keeps those; if it uses 'accept'/'reject', keeps those.
    Only renames when there's a mix (e.g. nested subroutines used different conventions).
    """
    accept_aliases = {'accept', 'success'}
    reject_aliases = {'reject', 'failure'}
    done_aliases = {'done'}

    accepts = [n for n in routine.states if _basename(n) in accept_aliases]
    rejects = [n for n in routine.states if _basename(n) in reject_aliases]
    dones = [n for n in routine.states if _basename(n) in done_aliases]

    # Pick canonical name based on what's already there
    if any(_basename(n) == 'success' for n in accepts):
        accept_canonical = 'success'
    elif accepts:
        accept_canonical = 'accept'
    else:
        accept_canonical = None

    if any(_basename(n) == 'failure' for n in rejects):
        reject_canonical = 'failure'
    elif rejects:
        reject_canonical = 'reject'
    else:
        reject_canonical = None

    # Build remap: any halt-state that isn't already the canonical name gets remapped
    remap: dict[str, str] = {}
    for n in accepts:
        if accept_canonical and n != accept_canonical:
            remap[n] = accept_canonical
    for n in rejects:
        if reject_canonical and n != reject_canonical:
            remap[n] = reject_canonical
    # done states without further continuation become accept (final halt)
    for n in dones:
        s = routine.states[n]
        if not s.transitions:
            if accept_canonical:
                remap[n] = accept_canonical

    # Apply remap to transition targets
    for state in routine.states.values():
        for t in state.transitions:
            if t.target in remap:
                t.target = remap[t.target]
            for k, v in list(t.exit_dispatch.items()):
                if v in remap:
                    t.exit_dispatch[k] = remap[v]

    # Remove old halt states (replaced by canonical), keep canonical
    for old_name in remap:
        if old_name in routine.states and old_name != remap[old_name]:
            del routine.states[old_name]

    # Ensure canonical halt states exist as halt states with no transitions
    if accept_canonical:
        if accept_canonical not in routine.states:
            routine.states[accept_canonical] = State(
                name=accept_canonical, is_halt=True, halt_kind='accept')
        else:
            s = routine.states[accept_canonical]
            s.is_halt = True
            s.halt_kind = 'accept'
            s.transitions = []

    if reject_canonical:
        if reject_canonical not in routine.states:
            routine.states[reject_canonical] = State(
                name=reject_canonical, is_halt=True, halt_kind='reject')
        else:
            s = routine.states[reject_canonical]
            s.is_halt = True
            s.halt_kind = 'reject'
            s.transitions = []

    # Update start if it was remapped
    if routine.start_state in remap:
        routine.start_state = remap[routine.start_state]

    return routine


def _basename(state_name: str) -> str:
    """Extract the un-prefixed base name from a qualified state name."""
    if '__' in state_name:
        return state_name.split('__')[-1]
    return state_name


def remove_unreachable(routine: Routine) -> Routine:
    """Remove states not reachable from start."""
    if not routine.start_state:
        return routine
    reachable: set[str] = set()
    stack = [routine.start_state]
    while stack:
        name = stack.pop()
        if name in reachable or name not in routine.states:
            continue
        reachable.add(name)
        for t in routine.states[name].transitions:
            if t.target:
                stack.append(t.target)

    for name in list(routine.states):
        if name not in reachable:
            del routine.states[name]

    return routine
