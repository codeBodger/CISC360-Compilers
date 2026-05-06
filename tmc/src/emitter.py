"""Emit a flat Routine as TMVRepr YAML matching Samhain's a.out format.

Style conventions (per a.out):
- input is optional (not in a.out for subroutines-style compiles)
- blank: ' '
- start state: <name in double quotes if it has special chars>
- table:
    state_name:           # quoted if needed
        symbol_or_list: {R: target, write: X}    # write before direction
    halt_state:           # empty body
"""
from __future__ import annotations
from .ast import Routine, State, Transition


def emit(routine: Routine) -> str:
    """Render a flat routine as TMVRepr YAML."""
    lines: list[str] = []

    if routine.input is not None if hasattr(routine, 'input') else False:
        lines.append(f"input: '{routine.input}'")
    blank = routine.blank if routine.blank else ' '
    lines.append(f"blank: '{blank}'")
    if routine.start_state:
        lines.append(f"start state: {_quote_state_name(routine.start_state)}")
    lines.append("table:")

    state_order = _bfs_order(routine)
    for state_name in state_order:
        state = routine.states[state_name]
        if state.is_halt or not state.transitions:
            lines.append(f"    {_quote_state_name(state_name)}:")
            continue

        lines.append(f"    {_quote_state_name(state_name)}:")
        # Group transitions sharing the same action
        grouped: list[tuple[list[str], str]] = []
        for t in state.transitions:
            action_str = _emit_action_str(t)
            symbols = list(t.read)
            merged = False
            for i, (syms, act) in enumerate(grouped):
                if act == action_str:
                    grouped[i] = (syms + symbols, act)
                    merged = True
                    break
            if not merged:
                grouped.append((symbols, action_str))

        for syms, action_str in grouped:
            if len(syms) == 1:
                key_str = _quote_symbol(syms[0])
            else:
                items = ', '.join(_quote_symbol(s) for s in syms)
                key_str = f"[{items}]"
            lines.append(f"        {key_str}: {action_str}")

    return '\n'.join(lines) + '\n'


def _emit_action_str(t: Transition) -> str:
    """Render transition action as a flow-style mapping string.

    Order in Samhain's a.out: direction first, then write.
    e.g. {R: target, write: X} or {R: target} or {L} or {L, write: X}
    """
    parts: list[str] = []
    direction = t.direction or 'R'
    if t.target:
        parts.append(f"{direction}: {_quote_state_name(t.target)}")
    else:
        parts.append(direction)
    if t.write is not None:
        parts.append(f"write: {_quote_symbol(t.write)}")
    return '{' + ', '.join(parts) + '}'


def _quote_symbol(sym: str) -> str:
    """Quote a tape symbol the way Samhain's a.out does."""
    s = str(sym)
    # Per a.out: digits are quoted ('0', '1'), letters bare (like V)
    if s.isdigit() and len(s) == 1:
        return f"'{s}'"
    if s in ('R', 'L'):
        return s
    if s and s.isalpha() and len(s) <= 2:
        return s
    return f"'{s}'"


def _quote_state_name(name: str) -> str:
    """Quote a state name if it contains special characters."""
    if not name:
        return "''"
    # Plain identifier (only word chars and underscores) — no quoting
    if all(c.isalnum() or c == '_' for c in name):
        return name
    return f'"{name}"'


def _bfs_order(routine: Routine) -> list[str]:
    """BFS from start state, then any unvisited (halt) states at the end."""
    if not routine.start_state:
        return list(routine.states.keys())
    order: list[str] = []
    seen: set[str] = set()
    queue = [routine.start_state]
    while queue:
        name = queue.pop(0)
        if name in seen or name not in routine.states:
            continue
        seen.add(name)
        order.append(name)
        for t in routine.states[name].transitions:
            if t.target and t.target not in seen:
                queue.append(t.target)
            for v in t.exit_dispatch.values():
                if v and v not in seen:
                    queue.append(v)
    # Append any unvisited (e.g., halts) at the end
    halt_order = [routine.accept_name, routine.reject_name]
    for n in halt_order:
        if n in routine.states and n not in seen:
            order.append(n)
            seen.add(n)
    for n in routine.states:
        if n not in seen:
            order.append(n)
    return order
