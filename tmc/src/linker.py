"""Inline subroutine calls into a single flat routine.

Naming convention (per Samhain's a.out):
  parent.subroutine.callsite.state

For example, calling 'shift' from 'main' for the first time produces states
named 'main.shift.1.S', 'main.shift.1.seen 0', etc.

ε-merge: when one state's only "transition" is an ε-jump to another, the two
state names are joined with '-'. So if main.S ε-jumps to main.shift.1.S', the
resulting state is named 'main.S-main.shift.1.S''.

Halt states are preserved separately and merged at the end (one canonical
'accept' and one 'reject' from main's accept_name/reject_name).
"""
from __future__ import annotations
from copy import deepcopy
from .ast import Program, Routine, State, Transition

END_STATES = {'done', 'yes', 'no', 'accept', 'reject', 'success', 'failure'}


class LinkError(Exception):
    pass


def link(program: Program) -> Routine:
    """Inline all calls into a flat routine."""
    if program.main is None:
        raise LinkError("No main routine to link")

    main = program.main
    flat = Routine(
        name=main.name,
        display_name=main.display_name,
        is_main=True,
        blank=main.blank,
        accept_name=main.accept_name,
        reject_name=main.reject_name,
    )

    call_counter: dict = {}
    main_prefix = 'main'  # Samhain's convention: always use 'main' as the top-level prefix

    # Determine entry point
    if main.start_chain:
        # Main has no own states; entry point is the chain
        entry = _link_chain(main.start_chain, [], program, flat,
                            prefix=main_prefix, call_counter=call_counter,
                            end_target=flat.accept_name)
        flat.start_state = entry
    else:
        # Main has states. Inline starting from main's start state.
        entry = _inline_routine(
            main, program, flat,
            prefix=main_prefix,
            call_counter=call_counter,
            visited=set(),
            exit_targets={'accept': flat.accept_name,
                          'reject': flat.reject_name},
            ext_chain_continuation=None,
        )
        flat.start_state = entry

    # Finalise: resolve aliases, perform merges
    _finalise(flat)

    # Ensure halt states exist
    if flat.accept_name not in flat.states:
        flat.states[flat.accept_name] = State(
            name=flat.accept_name, is_halt=True, halt_kind='accept')
    if flat.reject_name not in flat.states:
        flat.states[flat.reject_name] = State(
            name=flat.reject_name, is_halt=True, halt_kind='reject')

    return flat


def _finalise(out: Routine) -> None:
    """Apply pending merges and resolve aliases throughout the routine.

    Steps:
    1. Compute final alias resolution for all aliased names.
    2. Apply each merge: combine the contents of the two source states under
       the merged name.
    3. Rewrite all transition targets / start state / dispatch targets using
       the resolved aliases.
    """
    aliases = getattr(out, '_aliases', {})
    merges = getattr(out, '_merges', [])

    def resolve(name: str, seen=None) -> str:
        seen = seen or set()
        if name in seen or name not in aliases:
            return name
        seen.add(name)
        return resolve(aliases[name], seen)

    # Apply merges: for each (a, b, merged), if either state exists, move its
    # contents under merged name.
    for a, b, merged in merges:
        for src in (a, b):
            if src in out.states and src != merged:
                src_state = out.states.pop(src)
                if merged in out.states:
                    # Append transitions
                    out.states[merged].transitions.extend(src_state.transitions)
                else:
                    src_state.name = merged
                    out.states[merged] = src_state

    # Rewrite all targets / start state / dispatch values via alias resolution
    if out.start_state:
        out.start_state = resolve(out.start_state)
    for state in out.states.values():
        for t in state.transitions:
            if t.target:
                t.target = resolve(t.target)
            for k, v in list(t.exit_dispatch.items()):
                if v:
                    t.exit_dispatch[k] = resolve(v)


def _qualify(*parts) -> str:
    """Join name parts with '.' for qualified state names."""
    return '.'.join(str(p) for p in parts if p)


def _inline_routine(routine: Routine, program: Program, out: Routine,
                    prefix: str, call_counter: dict,
                    visited: set, exit_targets: dict,
                    ext_chain_continuation) -> str:
    """Inline a routine's states into `out` with the given prefix.

    Returns the qualified name of the start state.
    `exit_targets` maps end-state names to the state in `out` they should
    redirect to ('done' → next chain step or final accept, 'accept' → main's
    accept, etc.)
    `ext_chain_continuation` is None or a string: the state that the routine's
    'done' should ultimately route to (used inside chain inlining).
    """
    if routine.start_chain:
        # Routine itself is just a chain
        return _link_chain(routine.start_chain, [], program, out,
                           prefix=prefix, call_counter=call_counter,
                           end_target=exit_targets.get('accept', out.accept_name),
                           visited=visited)

    start = routine.start_state or next(iter(routine.states))

    for sname, state in routine.states.items():
        qname = _qualify(prefix, sname)

        # Halt states: emit OR redirect based on context
        if state.is_halt:
            if state.halt_kind == 'accept':
                # Redirect to global accept
                _set_alias(out, qname, exit_targets.get('accept', out.accept_name))
                continue
            elif state.halt_kind == 'reject':
                _set_alias(out, qname, exit_targets.get('reject', out.reject_name))
                continue
            elif state.halt_kind == 'done':
                # If we have a chain continuation, emit a dash-merged ε-state
                # so the merge is visible in the output.
                cont = exit_targets.get('done')
                if cont and cont != qname:
                    merged_name = qname + '-' + cont
                    # Emit merged_name as an ε-only state pointing to cont,
                    # OR (better) inline cont's transitions under merged_name.
                    # We'll just alias and let resolver handle it.
                    _set_alias(out, qname, merged_name)
                    # And alias cont → merged_name so they're treated as one
                    # (we want references to BOTH names to land at merged_name)
                    _set_alias(out, cont, merged_name)
                    # Mark for later: we'll merge contents during finalisation
                    if not hasattr(out, '_merges'):
                        out._merges = []
                    out._merges.append((qname, cont, merged_name))
                else:
                    _set_alias(out, qname, exit_targets.get('accept', out.accept_name))
                continue
            else:
                # Other halt kinds — leave as terminal
                emit_halt = State(name=qname, is_halt=True, halt_kind=state.halt_kind)
                out.states[qname] = emit_halt
                continue

        if state.is_chain:
            # The state's body is a chain; lay out the chain steps and
            # the chain's start state IS this state's qname (with ε-merge handled later)
            chain_start = _link_chain(
                [step.target for step in state.chain],
                [step.exit_dispatch for step in state.chain],
                program, out,
                prefix=prefix,
                call_counter=call_counter,
                end_target=exit_targets.get('done', exit_targets.get('accept', out.accept_name)),
                visited=visited,
            )
            # The state itself epsilons to chain_start. Merge their names with '-'.
            merged = qname + '-' + chain_start if chain_start != qname else qname
            _rename_state(out, chain_start, merged)
            if sname == start:
                _set_alias(out, qname, merged)
            continue

        # Regular state: emit it with qualified name
        new_state = State(name=qname)
        for t in state.transitions:
            new_t = _process_transition(
                t, routine, program, out, prefix, call_counter,
                visited, exit_targets,
            )
            if new_t is not None:
                new_state.transitions.append(new_t)
        out.states[qname] = new_state

    # Resolve start state
    start_qname = _qualify(prefix, start)
    aliased = _resolve_alias(out, start_qname)
    return aliased


def _process_transition(t: Transition, routine: Routine, program: Program,
                        out: Routine, prefix: str, call_counter: dict,
                        visited: set, exit_targets: dict) -> Transition | None:
    """Process a single (non-chain) transition: rename its target, expand subroutine calls."""
    if t.is_subroutine_call and t.target:
        # Inline a subroutine call as a single epsilon-like transition
        sub_name = t.target
        if sub_name not in program.routines:
            raise LinkError(f"unresolved subroutine call to '{sub_name}'")

        # Build exit_targets for this call site
        sub_exits: dict[str, str] = {}
        for end_kind, target_state in t.exit_dispatch.items():
            key = end_kind.replace(' epsilon', '').replace('_epsilon', '').strip()
            if not target_state:
                continue
            if target_state in END_STATES:
                if target_state == 'accept':
                    sub_exits[key] = exit_targets.get('accept', out.accept_name)
                elif target_state == 'reject':
                    sub_exits[key] = exit_targets.get('reject', out.reject_name)
                else:
                    sub_exits[key] = exit_targets.get(target_state, target_state)
            else:
                sub_exits[key] = _qualify(prefix, target_state)

        call_counter[sub_name] = call_counter.get(sub_name, 0) + 1
        n = call_counter[sub_name]
        call_prefix = _qualify(prefix, sub_name, n)
        new_visited = visited | {sub_name}
        sub_start = _inline_routine(
            program.routines[sub_name], program, out,
            prefix=call_prefix, call_counter=call_counter,
            visited=new_visited, exit_targets=sub_exits,
            ext_chain_continuation=None,
        )

        new_t = Transition(
            read=t.read, write=t.write, direction=t.direction,
            target=sub_start, is_subroutine_call=False,
        )
        return new_t

    # Regular state goto
    new_t = deepcopy(t)
    new_t.is_subroutine_call = False
    if t.target:
        if t.target in END_STATES:
            if t.target == 'accept':
                new_t.target = exit_targets.get('accept', out.accept_name)
            elif t.target == 'reject':
                new_t.target = exit_targets.get('reject', out.reject_name)
            else:
                new_t.target = exit_targets.get(t.target, t.target)
        else:
            new_t.target = _qualify(prefix, t.target)
    for k, v in list(new_t.exit_dispatch.items()):
        if v in END_STATES:
            new_t.exit_dispatch[k] = exit_targets.get(v, v)
        elif v:
            new_t.exit_dispatch[k] = _qualify(prefix, v)
    return new_t


def _link_chain(steps: list, dispatches: list, program: Program, out: Routine,
                prefix: str, call_counter: dict, end_target: str,
                visited: set | None = None) -> str:
    """Inline a chain of subroutine calls.

    `steps` is a list of subroutine names (or state names) in order.
    `dispatches` is a parallel list of exit_dispatch dicts (or empty dicts).
    The chain executes step1, then on its 'done' goes to step2, etc.
    The last step's 'done' goes to `end_target`.

    Returns the qualified name of the first step's start state.

    Recursion handling: if the same routine appears at multiple positions in
    the chain (e.g., proc → ... → proc as a loop), all subsequent occurrences
    after the first become loop-backs to the first occurrence's start state.
    Also: if a step's routine is in `visited` (we're inside that routine
    already at a higher level), its call also becomes a loop-back to where
    that ancestor was placed.
    """
    if not steps:
        return end_target

    if visited is None:
        visited = set()

    # First, build a forward-order plan: figure out for each step whether it
    # introduces a new inlining or whether it's a loop-back to an earlier
    # occurrence. We compute this BEFORE inlining so we know exit-targets
    # for recursion edges.
    plan: list[tuple[str, str]] = []  # (kind, name): kind ∈ {'inline','loop','goto'}
    name_first_index: dict[str, int] = {}
    for i, step in enumerate(steps):
        if step in program.routines:
            if step in name_first_index or step in visited:
                plan.append(('loop', step))
            else:
                plan.append(('inline', step))
                name_first_index[step] = i
        else:
            plan.append(('goto', step))

    # We'll fill in starts during reverse-pass inlining
    starts: list[str | None] = [None] * len(steps)

    # PASS 1: walk forward to allocate start names for *inlined* steps
    # without actually inlining yet — we need the names so loop-back targets
    # are known when we inline in reverse.
    # Simpler approach: do a reverse pass but for 'loop' steps, defer start
    # resolution until pass 2.

    # Reverse-pass inlining (only for 'inline' kind):
    next_target = end_target
    # We need to handle 'loop' steps by knowing where their loop-back target
    # is. Since loop-back targets are *earlier* in forward order, we'll
    # resolve them in a final fix-up pass after reverse inlining of the
    # 'inline' kinds.

    # First reverse pass: inline 'inline' steps with placeholder loop targets
    PLACEHOLDER = '__PLACEHOLDER__'
    for i in range(len(steps) - 1, -1, -1):
        kind, step = plan[i]
        disp = dispatches[i] if i < len(dispatches) else {}

        if kind == 'goto':
            target = _qualify(prefix, step)
            starts[i] = target
            next_target = target
        elif kind == 'loop':
            # Defer; we'll fix up after.
            starts[i] = PLACEHOLDER + str(i)
            next_target = starts[i]
        elif kind == 'inline':
            sub_exits: dict[str, str] = {'done': next_target,
                                          'accept': out.accept_name,
                                          'reject': out.reject_name}
            for k, v in disp.items():
                k_norm = k.replace(' epsilon', '').replace('_epsilon', '').strip()
                if v in END_STATES:
                    sub_exits[k_norm] = (out.accept_name if v == 'accept'
                                         else out.reject_name if v == 'reject'
                                         else next_target)
                elif v:
                    sub_exits[k_norm] = _qualify(prefix, v)
            call_counter[step] = call_counter.get(step, 0) + 1
            n = call_counter[step]
            call_prefix = _qualify(prefix, step, n)
            new_visited = visited | {step}
            sub_start = _inline_routine(
                program.routines[step], program, out,
                prefix=call_prefix, call_counter=call_counter,
                visited=new_visited, exit_targets=sub_exits,
                ext_chain_continuation=next_target,
            )
            starts[i] = sub_start
            next_target = sub_start

    # Pass 2: resolve 'loop' steps. Each loop step's target is either an
    # earlier occurrence in this chain, OR (if in `visited`) an ancestor
    # routine's start, which we don't have direct access to here.
    # For chain self-loops (proc → ... → proc), the ancestor routine's start
    # is the first occurrence in this chain.
    for i in range(len(steps)):
        kind, step = plan[i]
        if kind != 'loop':
            continue
        if step in name_first_index:
            # Loop-back to first occurrence in this same chain
            target = starts[name_first_index[step]]
        else:
            # Ancestor recursion: target is the routine we're already inside.
            # We don't have that here; for now, route to end_target as a
            # safe fallback (will be wrong for ancestor recursion).
            target = end_target

        placeholder = starts[i]
        # Rewrite the previous step's 'done' / chain transitions that point
        # to this placeholder.
        if i > 0:
            prev_start = starts[i - 1]
            _replace_target(out, placeholder, target, scope_prefix=prev_start)
        starts[i] = target

    # Final cleanup: replace any remaining placeholders globally (defensive)
    for i in range(len(starts)):
        if starts[i] and starts[i].startswith(PLACEHOLDER):
            starts[i] = end_target

    return starts[0] if starts else end_target


def _replace_target(out: Routine, old: str, new: str, scope_prefix: str | None = None) -> None:
    """Replace all references to `old` with `new` in transitions. If
    scope_prefix given, only rewrite within states whose name starts with
    that prefix's namespace (so we don't bleed across calls)."""
    if scope_prefix:
        # Determine namespace: e.g., scope_prefix 'main.proc.1.foo' → ns 'main.proc.1.'
        parts = scope_prefix.split('.')
        if len(parts) >= 3:
            ns = '.'.join(parts[:3]) + '.'
        else:
            ns = scope_prefix
    else:
        ns = ''
    for state_name, state in out.states.items():
        if ns and not state_name.startswith(ns):
            continue
        for t in state.transitions:
            if t.target == old:
                t.target = new
            for k, v in list(t.exit_dispatch.items()):
                if v == old:
                    t.exit_dispatch[k] = new
    # Also rewrite start_state if it matches
    if out.start_state == old:
        out.start_state = new


def _redirect_done(out: Routine, scope_start: str, old_target: str, new_target: str) -> None:
    """Legacy helper, kept for compatibility but unused now."""
    _replace_target(out, old_target, new_target, scope_prefix=scope_start)


def _remove_inlined(out: Routine, start_name: str) -> None:
    """Legacy helper, kept for compatibility but unused now."""
    parts = start_name.split('.')
    if len(parts) < 2:
        return
    prefix = '.'.join(parts[:-1]) + '.'
    to_remove = [n for n in out.states if n.startswith(prefix)]
    for n in to_remove:
        del out.states[n]


def _rename_state(out: Routine, old_name: str, new_name: str) -> None:
    """Rename a state and update all references to it."""
    if old_name == new_name:
        return
    if old_name in out.states:
        state = out.states.pop(old_name)
        state.name = new_name
        out.states[new_name] = state
    # Update references in all transitions
    for state in out.states.values():
        for t in state.transitions:
            if t.target == old_name:
                t.target = new_name
            for k, v in list(t.exit_dispatch.items()):
                if v == old_name:
                    t.exit_dispatch[k] = new_name
    # Update start state if needed
    if out.start_state == old_name:
        out.start_state = new_name


# Aliasing: track when one name maps to another (used for chain entry points)
_aliases: dict = {}


def _set_alias(out: Routine, name: str, target: str) -> None:
    """Mark `name` as an alias for `target`."""
    # Use the routine itself to store aliases
    if not hasattr(out, '_aliases'):
        out._aliases = {}
    out._aliases[name] = target


def _resolve_alias(out: Routine, name: str) -> str:
    if not hasattr(out, '_aliases'):
        return name
    seen = set()
    while name in out._aliases and name not in seen:
        seen.add(name)
        name = out._aliases[name]
    return name
