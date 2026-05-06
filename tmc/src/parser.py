"""Parse ShortRepr YAML files into the AST.

Two-pass parsing:
  Pass 1 — Read raw YAML from all files, collect:
    - routine names (filenames)
    - tape_symbols / alphabet / left / blank / accept / reject from main routine
  Pass 2 — Parse each routine's table with full disambiguation context.

Transition list-form disambiguation rules (per Samhain):
  Position constraints:
    - direction (R/L): required, must be last; forbidden on epsilon transitions
    - write symbol: must be after target state, before direction; in tape_symbols
    - subroutine call: must be first; matches a routine name
    - state name target: must be first if no subroutine; anonymous states allowed
"""
from __future__ import annotations
from pathlib import Path
from ruamel.yaml import YAML
from .ast import Routine, State, Transition, Program


_yaml = YAML(typ='safe')

DIRECTIONS = {'L', 'R'}
DISPATCH_KEYS = {'done', 'yes', 'no', 'epsilon',
                 'yes epsilon', 'no epsilon',
                 'yes_epsilon', 'no_epsilon'}
META_KEYS = {'formalism', 'alphabet', 'tape symbols', 'tape_symbols',
             'left', 'blank', 'start state', 'start_state',
             'accept', 'reject', 'name'}


class ParseError(Exception):
    pass


def parse_files(paths: list[str]) -> Program:
    """Parse multiple YAML files into a Program. Two-pass."""
    program = Program()

    # PASS 1: load raw YAML, register routines, find main, resolve metadata
    raw: dict[str, tuple[Path, dict]] = {}
    for path_str in paths:
        path = Path(path_str)
        with open(path, 'r') as f:
            data = _yaml.load(f)
        if not isinstance(data, dict):
            raise ParseError(f"{path}: top-level must be a mapping")
        raw[path.stem] = (path, data)

    # Build the set of routine names AND a "tolerant" lookup map that
    # allows references like "shift dub R" to resolve to file shift_dub_R.
    routine_names = set(raw.keys())
    tolerant_map: dict[str, str] = {}
    for n in routine_names:
        tolerant_map[n] = n
        tolerant_map[n.replace('_', ' ')] = n
        tolerant_map[n.replace(' ', '_')] = n

    # Determine main routine: the one not called by any other routine.
    # (Falls back to "the only one with `start state`" if call analysis is ambiguous.)
    main_name = _detect_main(raw, routine_names, tolerant_map)

    # Extract tape_symbols from main for disambiguation
    main_data = raw[main_name][1]
    tape_symbols = list(main_data.get('tape symbols')
                        or main_data.get('tape_symbols')
                        or [])
    program.tape_symbols = [str(s) for s in tape_symbols]

    # PASS 2: parse each routine's table with disambiguation context
    for name, (path, data) in raw.items():
        routine = _parse_routine(name, path, data, routine_names,
                                 program.tape_symbols, tolerant_map,
                                 is_main=(name == main_name))
        program.routines[name] = routine
        if routine.is_main:
            program.main = routine

    return program


def _resolve_routine_name(s: str, tolerant_map: dict[str, str]) -> str | None:
    """Look up a possibly-spaced routine reference in the tolerant map."""
    if s in tolerant_map:
        return tolerant_map[s]
    return None


def _detect_main(raw: dict[str, tuple[Path, dict]],
                 routine_names: set[str],
                 tolerant_map: dict[str, str]) -> str:
    """Find the routine not called by any other.

    A "call" is any reference to a routine name in another routine's transitions.
    """
    called: set[str] = set()
    for name, (_, data) in raw.items():
        table = data.get('table', {})
        # Also check start state for call-form
        ss = data.get('start state') or data.get('start_state')
        if isinstance(ss, list):
            for item in ss:
                if isinstance(item, str):
                    resolved = tolerant_map.get(item)
                    if resolved:
                        called.add(resolved)

        if not isinstance(table, dict):
            continue
        for state_name, body in table.items():
            _collect_called_routines(body, routine_names, tolerant_map, called)

    candidates = routine_names - called
    if len(candidates) == 1:
        return candidates.pop()
    if len(candidates) > 1:
        # Multiple uncalled routines — prefer one literally named 'main'
        if 'main' in candidates:
            return 'main'
        # Otherwise: prefer the one with both `start state` and metadata fields
        for c in candidates:
            d = raw[c][1]
            if ('alphabet' in d or 'tape symbols' in d or 'tape_symbols' in d):
                return c
        # Fall back to alphabetically first
        return sorted(candidates)[0]
    # No candidate (cycle in calls?) — error
    raise ParseError(f"Could not determine main routine; all routines are called by others. "
                     f"routines={sorted(routine_names)}")


def _collect_called_routines(body, routine_names: set[str],
                             tolerant_map: dict[str, str],
                             out: set[str]) -> None:
    """Walk a state body and add any routine names referenced."""
    if body is None:
        return
    if isinstance(body, list):
        # chain form: list of subroutine names (bare strings) or dicts
        for step in body:
            if isinstance(step, str):
                resolved = tolerant_map.get(step)
                if resolved:
                    out.add(resolved)
            elif isinstance(step, dict):
                for k in step.keys():
                    if isinstance(k, str):
                        resolved = tolerant_map.get(k)
                        if resolved:
                            out.add(resolved)
        return
    if isinstance(body, dict):
        for read_key, val in body.items():
            # check val for subroutine refs
            if isinstance(val, list):
                # transition list - first element could be a subroutine name
                if val and isinstance(val[0], str):
                    resolved = tolerant_map.get(val[0])
                    if resolved:
                        out.add(resolved)


def _parse_routine(name: str, path: Path, data: dict,
                   routine_names: set[str], tape_symbols: list[str],
                   tolerant_map: dict[str, str],
                   is_main: bool) -> Routine:
    """Parse a single routine's data into a Routine."""
    routine = Routine(name=name, display_name=name, source_file=str(path),
                      is_main=is_main)

    routine.formalism = data.get('formalism')
    if 'alphabet' in data:
        routine.alphabet = [str(s) for s in data['alphabet']]
    if 'tape symbols' in data:
        routine.tape_symbols = [str(s) for s in data['tape symbols']]
    elif 'tape_symbols' in data:
        routine.tape_symbols = [str(s) for s in data['tape_symbols']]
    if 'left' in data:
        routine.left = str(data['left'])
    if 'blank' in data:
        routine.blank = str(data['blank'])
    if 'accept' in data:
        routine.accept_name = str(data['accept'])
    if 'reject' in data:
        routine.reject_name = str(data['reject'])

    # start state: may be a string (state name) or a list (chain of subroutines)
    ss = data.get('start state') or data.get('start_state')
    if isinstance(ss, list):
        # Resolve names in the chain via tolerant_map (so "shift dub R" → "shift_dub_R")
        resolved_chain = []
        for x in ss:
            sx = str(x)
            resolved_chain.append(tolerant_map.get(sx, sx))
        routine.start_chain = resolved_chain
    elif ss is not None:
        routine.start_state = str(ss)

    # Use the routine's own tape_symbols if it has them; otherwise inherit from main
    effective_tape = routine.tape_symbols or tape_symbols

    # Parse table
    table = data.get('table', {})
    if not isinstance(table, dict):
        # No table — could be a meta-only file like main_alt.yml. That's allowed
        # when start_chain provides the entry point.
        return routine

    for state_name, body in table.items():
        state = _parse_state(str(state_name), body, routine_names,
                             effective_tape, tolerant_map, path)
        routine.states[state.name] = state

    # If subroutine and start_state not declared, infer first state
    if not routine.is_main and not routine.start_state and routine.states:
        routine.start_state = next(iter(routine.states))

    return routine


def _parse_state(name: str, body, routine_names: set[str],
                 tape_symbols: list[str],
                 tolerant_map: dict[str, str],
                 path: Path) -> State:
    """Parse one state's body into a State."""
    state = State(name=name)

    if body is None or body == '':
        # Halt state
        state.is_halt = True
        if name in ('accept', 'success'):
            state.halt_kind = 'accept'
        elif name in ('reject', 'failure'):
            state.halt_kind = 'reject'
        elif name == 'done':
            state.halt_kind = 'done'
        return state

    if isinstance(body, list):
        # Chain form: list of subroutine calls (bare strings or {sub: dispatch} dicts)
        state.is_chain = True
        for step in body:
            t = _parse_chain_step(step, routine_names, tape_symbols,
                                   tolerant_map, path, name)
            if t is not None:
                state.chain.append(t)
        return state

    if isinstance(body, dict):
        for read_key, val in body.items():
            keys = _normalise_read_key(read_key)
            if any(k in DISPATCH_KEYS for k in keys):
                t = _parse_dispatch_entry(keys, val, routine_names,
                                          tape_symbols, tolerant_map, path, name)
                if t:
                    state.transitions.append(t)
            else:
                t = _parse_dict_transition(keys, val, routine_names,
                                           tape_symbols, tolerant_map, path, name)
                if t:
                    state.transitions.append(t)
        return state

    raise ParseError(f"{path}: state '{name}' has unparseable body type {type(body).__name__}")


def _normalise_read_key(key) -> list[str]:
    """Read keys can be a scalar, a YAML list, or (from ruamel) a tuple."""
    if isinstance(key, (list, tuple)):
        return [str(k) for k in key]
    return [str(key)]


def _parse_chain_step(step, routine_names: set[str], tape_symbols: list[str],
                      tolerant_map: dict[str, str],
                      path: Path, state_name: str) -> Transition | None:
    """A chain step is either:
       - bare string (subroutine name) — call it, default exit chains to next step
       - {subroutine_name: dispatch_dict} — call with explicit exit dispatchers
    """
    if isinstance(step, str):
        resolved = tolerant_map.get(step)
        if resolved is None:
            # Treat as a state goto in current routine
            return Transition(read=[], target=step, is_subroutine_call=False)
        return Transition(read=[], target=resolved, is_subroutine_call=True)

    if isinstance(step, dict):
        if len(step) != 1:
            raise ParseError(f"{path}: chain step in '{state_name}' must be single-key dict; got {step}")
        sub_name, body = next(iter(step.items()))
        sub_name = str(sub_name)
        resolved = tolerant_map.get(sub_name)
        is_sub = resolved is not None
        target = resolved if resolved else sub_name
        t = Transition(read=[], target=target, is_subroutine_call=is_sub)
        if isinstance(body, dict):
            for k, v in body.items():
                t.exit_dispatch[str(k)] = str(v) if v is not None else ''
        return t
    return None


def _parse_dict_transition(read_syms: list[str], val,
                           routine_names: set[str], tape_symbols: list[str],
                           tolerant_map: dict[str, str],
                           path: Path, state_name: str) -> Transition | None:
    """Parse a {read_symbol: action} entry."""
    t = Transition(read=read_syms)

    if val is None:
        return t

    if isinstance(val, list):
        _interpret_list_action(t, val, routine_names, tape_symbols,
                               tolerant_map, path, state_name)
        return t

    if isinstance(val, dict):
        # TMVRepr-style action dict
        if 'write' in val:
            t.write = str(val['write'])
        if 'L' in val:
            t.direction = 'L'
            tgt = val['L']
            if tgt is not None:
                t.target = str(tgt)
        elif 'R' in val:
            t.direction = 'R'
            tgt = val['R']
            if tgt is not None:
                t.target = str(tgt)
        return t

    if isinstance(val, str):
        if val in DIRECTIONS:
            t.direction = val
        else:
            t.target = val
        return t

    return None


def _interpret_list_action(t: Transition, val: list,
                           routine_names: set[str], tape_symbols: list[str],
                           tolerant_map: dict[str, str],
                           path: Path, state_name: str) -> None:
    """Apply Samhain's disambiguation rules to a list-form action."""
    items = [str(x) if not isinstance(x, dict) else x for x in val]

    # Detect inline dispatcher dicts (from things like {epsilon: target})
    for item in items:
        if isinstance(item, dict):
            for k, v in item.items():
                t.exit_dispatch[str(k)] = str(v) if v is not None else ''

    str_items = [s for s in items if isinstance(s, str)]

    direction: str | None = None
    if str_items and str_items[-1] in DIRECTIONS:
        direction = str_items[-1]
        str_items = str_items[:-1]
    t.direction = direction

    if not str_items:
        return

    if len(str_items) == 1:
        s = str_items[0]
        resolved = tolerant_map.get(s)
        if resolved:
            t.target = resolved
            t.is_subroutine_call = True
        elif s in tape_symbols:
            t.write = s
        else:
            t.target = s
    elif len(str_items) == 2:
        first, second = str_items
        resolved = tolerant_map.get(first)
        if resolved:
            t.target = resolved
            t.is_subroutine_call = True
        else:
            t.target = first
        if second in tape_symbols:
            t.write = second
        else:
            t.write = second
    else:
        raise ParseError(f"{path}: state '{state_name}' has transition "
                         f"with {len(str_items)} non-direction items "
                         f"(after stripping {direction!r}): {str_items}. "
                         f"Expected at most 2 (target, write).")


def _parse_dispatch_entry(keys: list[str], val,
                          routine_names: set[str], tape_symbols: list[str],
                          tolerant_map: dict[str, str],
                          path: Path, state_name: str) -> Transition | None:
    """Parse 'epsilon: target' or 'yes epsilon: target' or 'done: target' entries."""
    t = Transition(read=[])
    for k in keys:
        normalised = k.replace(' epsilon', '').replace('_epsilon', '').strip()
        if val is None:
            t.exit_dispatch[normalised] = ''
        elif isinstance(val, str):
            t.exit_dispatch[normalised] = val
        elif isinstance(val, list):
            for item in val:
                if isinstance(item, str):
                    if item in DIRECTIONS:
                        t.direction = item
                    else:
                        t.exit_dispatch[normalised] = item
        elif isinstance(val, dict):
            for kk, vv in val.items():
                if kk in DIRECTIONS:
                    t.direction = kk
                    if vv is not None:
                        t.exit_dispatch[normalised] = str(vv)
                else:
                    t.exit_dispatch[normalised] = str(vv) if vv is not None else ''
    return t
