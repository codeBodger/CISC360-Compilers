"""Emit a flat Routine as TMVRepr YAML.

Output format matches Samhain's TMVegs/2scomp.yaml exactly:

    input: '...'              # optional pre-loaded tape
    blank: ' '
    start state: SS
    table:
      state_name:
        symbol: {direction: target_state}
        symbol: {write: X, direction: target_state}
        [sym1, sym2]: {direction: target_state}
      halt_state_name:        # halt states have no body

States are emitted in BFS order from start. Halt states (no transitions)
have empty bodies. Multi-symbol transitions sharing the same action are
grouped into a list-keyed entry.
"""
from __future__ import annotations
from collections import OrderedDict
from io import StringIO
from ruamel.yaml import YAML
from ruamel.yaml.scalarstring import SingleQuotedScalarString as SQS
from .ast import Routine, State, Transition


def emit(routine: Routine) -> str:
    """Render the routine as a TMVRepr YAML string."""
    yaml = YAML()
    yaml.default_flow_style = False
    yaml.indent(mapping=2, sequence=4, offset=2)

    doc: OrderedDict = OrderedDict()
    if routine.input is not None:
        doc['input'] = SQS(str(routine.input))
    doc['blank'] = SQS(routine.blank if routine.blank else ' ')
    if routine.start_state:
        doc['start state'] = routine.start_state

    # Build the table
    table: OrderedDict = OrderedDict()
    state_order = _bfs_order(routine)
    for state_name in state_order:
        state = routine.states[state_name]
        if state.is_halt or not state.transitions:
            table[state_name] = None
        else:
            table[state_name] = _emit_state_body(state)

    doc['table'] = table

    out = StringIO()
    yaml.dump(doc, out)
    return out.getvalue()


def _emit_state_body(state: State) -> OrderedDict:
    """Group transitions by action and emit dict {symbol_or_list: action}."""
    # Group transitions by their action signature
    # action signature = (write, direction, target)
    body: OrderedDict = OrderedDict()

    # First pass: group transitions with identical actions
    grouped: list[tuple[list[str], dict]] = []
    for t in state.transitions:
        action = _emit_action(t)
        symbols = list(t.read)
        # Try to merge with an existing group with same action
        merged = False
        for i, (syms, act) in enumerate(grouped):
            if act == action:
                grouped[i] = (syms + symbols, act)
                merged = True
                break
        if not merged:
            grouped.append((symbols, action))

    for syms, action in grouped:
        if len(syms) == 1:
            key = _format_symbol_key(syms[0])
        else:
            key = [_format_symbol_key(s) for s in syms]
        body[_make_yaml_key(key)] = action

    return body


def _emit_action(t: Transition) -> dict:
    """Convert a transition into the TMVRepr action dict.

    Forms:
      {R}                    -> direction-only, no write, stay in state
      {L: target}            -> direction + transition
      {write: X, R: target}  -> write + direction + transition
      {write: X, L}          -> write + direction, stay in state
    """
    action: OrderedDict = OrderedDict()
    if t.write is not None:
        action['write'] = _format_symbol_key(t.write)
    direction = t.direction or 'R'  # default to R if unspecified
    if t.target:
        action[direction] = t.target
    else:
        # Direction-only, no transition - emit {R} as bare string
        # In ruamel we need a flow-style dict with just the key
        action[direction] = None

    return action


def _format_symbol_key(sym: str):
    """Convert a Python str to the right YAML scalar form.

    Symbols like '0', '1', '#', ' ', '[', 'V', 'H' need careful quoting:
    - bare ints stay int (0 -> 0)
    - special chars need single quotes
    """
    if sym is None:
        return None
    s = str(sym)
    if s.isdigit() and len(s) == 1:
        return int(s)  # YAML can render 0/1 as bare integers
    # Quote everything else as single-quoted to match 2scomp.yaml style
    return SQS(s)


def _make_yaml_key(key):
    """Make a hashable key for the YAML body dict."""
    if isinstance(key, list):
        # ruamel can use a tuple as a flow-style sequence key... actually we
        # need to use a CommentedSeq with flow style. Simpler: use tuple, ruamel
        # will render it as a flow seq key if we set flow style.
        # Actually safest is to manually construct via the YAML library.
        from ruamel.yaml.comments import CommentedSeq
        cs = CommentedSeq(key)
        cs.fa.set_flow_style()
        # CommentedSeq isn't hashable by default; we need to use it as a key
        # in a way ruamel can serialize. Use a frozenset-like wrapper... 
        # Actually, we'll build the table differently below.
        return tuple(key)  # placeholder - we'll rebuild below
    return key


def _bfs_order(routine: Routine) -> list[str]:
    """BFS order from start state, then any unvisited states."""
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
    # Append any unvisited states at the end (shouldn't happen if remove_unreachable was run)
    for n in routine.states:
        if n not in seen:
            order.append(n)
    return order


# ---- Manual emitter (more reliable than fighting ruamel for list keys) ----

def emit_manual(routine: Routine) -> str:
    """Emit TMVRepr YAML by hand. Avoids ruamel quirks with list keys."""
    lines: list[str] = []

    if routine.input is not None:
        lines.append(f"input: '{routine.input}'")
    blank = routine.blank if routine.blank else ' '
    lines.append(f"blank: '{blank}'")
    if routine.start_state:
        lines.append(f"start state: {routine.start_state}")
    lines.append("table:")

    state_order = _bfs_order(routine)
    for state_name in state_order:
        state = routine.states[state_name]
        if state.is_halt or not state.transitions:
            lines.append(f"  {_quote_state_name(state_name)}:")
            continue

        lines.append(f"  {_quote_state_name(state_name)}:")
        # Group transitions by action
        grouped: list[tuple[list[str], str]] = []
        for t in state.transitions:
            symbols = list(t.read)
            action_str = _emit_action_str(t)
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
            lines.append(f"    {key_str}: {action_str}")

    return '\n'.join(lines) + '\n'


def _emit_action_str(t: Transition) -> str:
    """Render the action portion of a transition as a string."""
    parts: list[str] = []
    if t.write is not None:
        parts.append(f"write: {_quote_symbol(t.write)}")
    direction = t.direction or 'R'
    if t.target:
        parts.append(f"{direction}: {t.target}")
    else:
        parts.append(direction)  # bare direction
    return '{' + ', '.join(parts) + '}'


def _quote_symbol(sym: str) -> str:
    """Quote a tape symbol for YAML output."""
    s = str(sym)
    if s.isdigit() and len(s) == 1:
        return s  # bare int
    if s in ('R', 'L'):
        return s  # bare letters fine
    if s and s[0].isalpha() and s.isalnum() and len(s) <= 4:
        # Plain identifier-like
        return s
    # Everything else gets single-quoted
    return f"'{s}'"


def _quote_state_name(name: str) -> str:
    """Quote a state name if it contains special chars."""
    if not name:
        return "''"
    # Plain identifier: no quoting
    if all(c.isalnum() or c in '_' for c in name):
        return name
    return f'"{name}"'
