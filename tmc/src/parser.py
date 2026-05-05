"""Parse ShortRepr YAML files into the AST."""
from __future__ import annotations
import os
from pathlib import Path
from ruamel.yaml import YAML
from .ast import Routine, State, Transition, Program


_yaml = YAML(typ='safe')


# Special dispatcher keys that don't carry a read symbol
DISPATCH_KEYS = {'epsilon', 'yes epsilon', 'no epsilon',
                 'yes_epsilon', 'no_epsilon',
                 'yes', 'no', 'done'}

DIRECTIONS = {'L', 'R'}


class ParseError(Exception):
    pass


def parse_file(path: str) -> Routine:
    """Parse one YAML file into a Routine."""
    p = Path(path)
    with open(p, 'r') as f:
        data = _yaml.load(f)
    name = p.stem
    routine = Routine(name=name, display_name=name, source_file=str(p))

    if not isinstance(data, dict):
        raise ParseError(f"{path}: top-level must be a mapping")

    # Check for main-routine fields (input/blank/start state)
    is_main = False
    if 'start state' in data or 'start_state' in data:
        is_main = True
        routine.is_main = True
        routine.start_state = data.get('start state') or data.get('start_state')
    if 'input' in data:
        routine.input = data['input']
        is_main = True
        routine.is_main = True
    if 'blank' in data:
        routine.blank = data['blank']

    # 'table' contains the states; otherwise top-level keys are states
    if 'table' in data:
        states_data = data['table']
    else:
        # Subroutine: all top-level keys are states (excluding meta keys)
        meta_keys = {'name', 'input', 'blank', 'start state', 'start_state'}
        states_data = {k: v for k, v in data.items() if k not in meta_keys}

    if not isinstance(states_data, dict):
        raise ParseError(f"{path}: states must be a mapping, got {type(states_data)}")

    for state_name, state_body in states_data.items():
        state = _parse_state(str(state_name), state_body, path)
        routine.states[state.name] = state

    # If subroutine, infer start state as first state
    if not routine.is_main and routine.states and not routine.start_state:
        routine.start_state = next(iter(routine.states))

    return routine


def _parse_state(name: str, body, path: str) -> State:
    """A state body can be:
    - None or empty (halt state)
    - dict mapping read-symbol -> transition
    - list of chain steps (subroutine calls or state gotos)
    """
    state = State(name=name)

    if body is None or body == '':
        state.is_halt = True
        if name in ('accept', 'success'):
            state.halt_kind = 'accept'
        elif name in ('reject', 'failure'):
            state.halt_kind = 'reject'
        elif name == 'done':
            state.halt_kind = 'done'
        return state

    if isinstance(body, list):
        # Chain: each element is a step (subroutine call or state goto)
        for step in body:
            t = _parse_chain_step(step, path, state_name=name)
            if t:
                state.transitions.append(t)
        return state

    if isinstance(body, dict):
        for read_key, val in body.items():
            # The key may be a list of symbols, a single symbol, or a dispatcher
            keys = _normalise_read_key(read_key)
            if any(k in DISPATCH_KEYS for k in keys):
                # Dispatcher entry: produce an epsilon-style transition
                t = _parse_epsilon_dispatch(keys, val, path, name)
                if t:
                    state.transitions.append(t)
            else:
                t = _parse_transition(keys, val, path, name)
                if t:
                    state.transitions.append(t)
        return state

    raise ParseError(f"{path}: state '{name}' has unparseable body: {body!r}")


def _normalise_read_key(key) -> list[str]:
    """A read key can be a string, a number, or a list/tuple of symbols."""
    if isinstance(key, (list, tuple)):
        return [str(k) for k in key]
    return [str(key)]


def _parse_transition(read_syms: list[str], val, path: str, state_name: str) -> Transition | None:
    """Parse a {read: action} entry in dict-form."""
    t = Transition(read=read_syms)

    if val is None:
        # No action - just stay
        return t

    if isinstance(val, dict):
        # TMVRepr-style or shorthand dict
        # Examples: {R}, {L: target}, {write: X, R: target}, {R: target}
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

    if isinstance(val, list):
        # ShortRepr-style list: [target, write, dir] or [dir] etc.
        # Items may be: state name, write symbol, direction, dispatcher dict
        for item in val:
            if isinstance(item, dict):
                # Inline dispatcher (e.g. {epsilon: target} mid-transition)
                for k, v in item.items():
                    t.exit_dispatch[str(k)] = str(v)
            elif isinstance(item, str) and item in DIRECTIONS:
                t.direction = item
            elif isinstance(item, str) and len(item) == 1:
                # Single character - could be a write symbol or state name
                # Heuristic: if no write yet and looks like a tape symbol, write
                if t.write is None and t.target is None:
                    # Ambiguous: could be write or single-char state name
                    # In ShortRepr, writes typically come AFTER target
                    t.write = item
                else:
                    if t.target is None:
                        t.target = item
                    else:
                        t.write = item
            else:
                # Multi-char string - likely a state or subroutine name
                if t.target is None:
                    t.target = str(item)
                else:
                    # Two strings -> first was target, second is write?
                    # Or first was write, second is target. Use position.
                    t.write = str(item)
        return t

    if isinstance(val, str):
        # Single string: could be direction-only, target-only, or write-only
        if val in DIRECTIONS:
            t.direction = val
        else:
            t.target = val
        return t

    return None


def _parse_chain_step(step, path: str, state_name: str) -> Transition | None:
    """Parse a step in a state's chain (list-form state body)."""
    if isinstance(step, str):
        # Plain goto - subroutine call or state goto
        return Transition(read=[], target=step, is_subroutine_call=True)

    if isinstance(step, dict):
        # Single-key dict: {subroutine_name: dispatcher}
        if len(step) == 1:
            name, body = next(iter(step.items()))
            t = Transition(read=[], target=str(name), is_subroutine_call=True)
            if isinstance(body, dict):
                for k, v in body.items():
                    t.exit_dispatch[str(k)] = str(v) if v is not None else ''
            return t
        else:
            # Multi-key dict in chain - treat as transitions on this row
            return None
    return None


def _parse_epsilon_dispatch(keys: list[str], val, path: str, state_name: str) -> Transition | None:
    """Parse 'epsilon: target' or 'yes epsilon: target' entries."""
    t = Transition(read=[])
    for k in keys:
        if val is None:
            t.exit_dispatch[k] = ''
        elif isinstance(val, str):
            t.exit_dispatch[k] = val
        elif isinstance(val, list):
            # [target, dir]
            for item in val:
                if isinstance(item, str):
                    if item in DIRECTIONS:
                        t.direction = item
                    else:
                        t.exit_dispatch[k] = item
        elif isinstance(val, dict):
            for kk, vv in val.items():
                if kk in DIRECTIONS:
                    t.direction = kk
                    if vv is not None:
                        t.exit_dispatch[k] = str(vv)
                else:
                    t.exit_dispatch[k] = str(vv) if vv is not None else ''
    return t


def parse_files(paths: list[str]) -> Program:
    """Parse multiple YAML files into a Program."""
    program = Program()
    for path in paths:
        routine = parse_file(path)
        program.routines[routine.name] = routine
        if routine.is_main:
            if program.main is not None:
                raise ParseError(f"Multiple main routines: {program.main.name} and {routine.name}")
            program.main = routine
    return program
