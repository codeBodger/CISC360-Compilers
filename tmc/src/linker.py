"""Linker: inline subroutine calls into the main routine.

For each subroutine call in main, produce a renamed copy of the subroutine's
states with prefix 'parent.subroutine.state.lineN' so multiple calls to the
same subroutine produce distinct state sets.

Exit dispatch: subroutine end-states named 'done', 'yes', 'no', 'accept',
'reject' are routed to the dispatcher's targets.
"""
from __future__ import annotations
from copy import deepcopy
from .ast import Program, Routine, State, Transition


# End-state names recognised in subroutines
END_STATES = {'done', 'yes', 'no', 'accept', 'reject', 'success', 'failure'}


class LinkError(Exception):
    pass


def link(program: Program) -> Routine:
    """Inline all subroutine calls into a single flat routine.

    Returns a new Routine with no subroutine calls remaining.
    """
    if program.main is None:
        raise LinkError("No main routine to link")

    main = deepcopy(program.main)
    flat = Routine(
        name=main.name,
        display_name=main.display_name,
        is_main=True,
        start_state=main.start_state,
        input=main.input,
        blank=main.blank,
    )

    call_counter = [0]
    _inline_routine(main, program, flat, prefix='', call_counter=call_counter,
                    visited=set())
    return flat


def _inline_routine(routine: Routine, program: Program, out: Routine,
                    prefix: str, call_counter: list, visited: set,
                    exit_targets: dict[str, str] | None = None) -> str:
    """Inline `routine` into `out` with the given prefix.

    Returns the (possibly prefixed) start-state name.

    `exit_targets` maps end-state names ('done', 'yes', etc.) to the state
    in `out` that should replace transitions targeting that end-state.
    """
    if exit_targets is None:
        exit_targets = {}

    # For each state, copy with renamed name
    for state_name, state in routine.states.items():
        new_name = _qualify(prefix, state_name)
        if new_name in out.states:
            continue  # already inlined this state (can happen with shared names)

        # Check if this is an end-state that should be redirected
        if state_name in END_STATES and state_name in exit_targets:
            # Don't emit this state - its references are redirected
            continue

        new_state = State(name=new_name, is_halt=state.is_halt,
                          halt_kind=state.halt_kind)

        # Detect chain: state body is a sequence of subroutine calls with no
        # read symbols. Process them in sequence: each step's 'done' goes to
        # the next step's start; the last step's 'done' uses its explicit dispatch.
        chain_steps = [t for t in state.transitions
                       if t.is_subroutine_call and not t.read]

        if chain_steps and len(chain_steps) == len(state.transitions):
            # Pure chain. Process steps in reverse so each step knows where to go.
            # Build a list of (call_prefix, sub_routine, exit_dispatch) tuples
            # in forward order, then chain them.
            next_state: str | None = None  # where the LAST step's 'done' goes
            chain_starts: list[str] = []

            # Process in reverse: each step's done goes to the next step's start
            for i in range(len(chain_steps) - 1, -1, -1):
                t = chain_steps[i]
                sub_name = _resolve_routine_name(t.target, program)
                if sub_name is None:
                    # Treat as state goto
                    target = (exit_targets.get(t.target)
                              if t.target in exit_targets
                              else _qualify(prefix, t.target))
                    chain_starts.insert(0, target)
                    next_state = target
                    continue

                if sub_name in visited:
                    raise LinkError(f"Recursive subroutine call: {sub_name}")

                # Build exit_targets for this step
                step_exits: dict[str, str] = {}
                for end_kind, tgt in t.exit_dispatch.items():
                    key = end_kind.replace(' epsilon', '').replace('_epsilon', '').strip()
                    if not tgt:
                        continue
                    if tgt in END_STATES and tgt in exit_targets:
                        step_exits[key] = exit_targets[tgt]
                    else:
                        step_exits[key] = _qualify(prefix, tgt)

                # If this is NOT the last step, override 'done' to go to next step
                if i < len(chain_steps) - 1 and next_state is not None:
                    step_exits['done'] = next_state

                call_counter[0] += 1
                call_prefix = _qualify(prefix, f"{sub_name}_{call_counter[0]}")
                new_visited = visited | {sub_name}
                sub_start = _inline_routine(
                    program.routines[sub_name], program, out, call_prefix,
                    call_counter, new_visited, step_exits,
                )
                chain_starts.insert(0, sub_start)
                next_state = sub_start

            # The state's only transition is an epsilon to the first step's start
            if chain_starts:
                # Mark this state with an epsilon transition to chain_starts[0]
                eps_t = Transition(read=[], target=chain_starts[0],
                                   is_subroutine_call=False)
                new_state.transitions = [eps_t]
        else:
            # Mixed or non-chain state: process each transition individually
            for t in state.transitions:
                new_transitions = _process_transition(
                    t, routine, program, out, prefix, call_counter,
                    visited, exit_targets,
                )
                new_state.transitions.extend(new_transitions)

        out.states[new_name] = new_state

    # If start state is an end-state, return its redirect
    start = routine.start_state or next(iter(routine.states))
    if start in END_STATES and start in exit_targets:
        return exit_targets[start]
    return _qualify(prefix, start)


def _process_transition(t: Transition, routine: Routine, program: Program,
                        out: Routine, prefix: str, call_counter: list,
                        visited: set, exit_targets: dict[str, str]) -> list[Transition]:
    """Process a single transition, expanding subroutine calls if needed."""
    if t.is_subroutine_call and t.target:
        # Look up the subroutine
        sub_name = _resolve_routine_name(t.target, program)
        if sub_name is None:
            # Not a subroutine - treat as a state goto within the current routine
            new_t = deepcopy(t)
            new_t.is_subroutine_call = False
            if t.target in END_STATES and t.target in exit_targets:
                new_t.target = exit_targets[t.target]
            else:
                new_t.target = _qualify(prefix, t.target)
            return [new_t]

        sub = program.routines[sub_name]
        if sub_name in visited:
            raise LinkError(f"Recursive subroutine call: {sub_name}")

        # Generate a unique prefix for this call site
        call_counter[0] += 1
        call_prefix = _qualify(prefix, f"{sub_name}_{call_counter[0]}")

        # Build exit_targets for the subroutine: map its end-states to
        # the dispatcher's targets in `out`.
        sub_exits: dict[str, str] = {}
        for end_kind, target_state in t.exit_dispatch.items():
            # Normalise dispatcher key
            key = end_kind.replace(' epsilon', '').replace('_epsilon', '').strip()
            if not target_state:
                continue
            if target_state in END_STATES and target_state in exit_targets:
                sub_exits[key] = exit_targets[target_state]
            else:
                sub_exits[key] = _qualify(prefix, target_state)

        # If no exit dispatch given, default 'done' to fall through to next chain step
        # That's handled at the chain-step level by the parser; here we just ensure
        # any unhandled end-state in the sub is left as a halt.

        new_visited = visited | {sub_name}
        sub_start = _inline_routine(
            sub, program, out, call_prefix, call_counter, new_visited, sub_exits,
        )

        # The transition becomes: read same symbols, but instead of calling, go
        # directly to the sub's start state. If t had no read symbols (chain step),
        # this is an epsilon to sub_start.
        new_t = Transition(
            read=t.read,
            write=t.write,
            direction=t.direction,
            target=sub_start,
            is_subroutine_call=False,
        )
        return [new_t]

    # Not a subroutine call - just rename target
    new_t = deepcopy(t)
    new_t.is_subroutine_call = False
    if t.target:
        if t.target in END_STATES and t.target in exit_targets:
            new_t.target = exit_targets[t.target]
        else:
            new_t.target = _qualify(prefix, t.target)
    # Rename exit_dispatch targets too (for epsilon transitions)
    for k, v in list(new_t.exit_dispatch.items()):
        if v in END_STATES and v in exit_targets:
            new_t.exit_dispatch[k] = exit_targets[v]
        elif v:
            new_t.exit_dispatch[k] = _qualify(prefix, v)
    return [new_t]


def _qualify(prefix: str, name: str) -> str:
    """Build a qualified state name."""
    if not prefix:
        return name
    return f"{prefix}__{name}"


def _resolve_routine_name(name: str, program: Program) -> str | None:
    """Resolve a routine name against the program's routines, with fuzzy matching."""
    if name in program.routines:
        return name
    # Try munged forms
    munged = _munge(name)
    if munged in program.routines:
        return munged
    # Try matching by removing underscores
    flat = name.replace('_', '').replace(' ', '').lower()
    for k in program.routines:
        if k.replace('_', '').lower() == flat:
            return k
    return None


def _munge(name: str) -> str:
    """Convert a display name like 'shift dub R' to filename form 'shift_dub_R'."""
    s = name
    s = s.replace("'", 'p').replace('#', 'sharp').replace('*', 'star')
    s = s.replace('γ', 'g').replace('α', 'alpha').replace('β', 'beta')
    s = s.replace(' ', '_')
    return s
