"""AST types for the ShortRepr Turing machine description."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Union


@dataclass
class Transition:
    """A single transition from a state on one or more read symbols."""
    read: list[str]              # symbols that trigger this transition
    write: Optional[str] = None  # symbol to write (None = same as read)
    direction: Optional[str] = None  # 'L', 'R', or None (no move)
    target: Optional[str] = None  # next state name (None = stay)
    is_subroutine_call: bool = False  # if True, target is a subroutine
    exit_dispatch: dict[str, str] = field(default_factory=dict)
    # exit_dispatch maps {'yes': state, 'no': state, 'epsilon': state, ...}


@dataclass
class State:
    name: str
    transitions: list[Transition] = field(default_factory=list)
    is_halt: bool = False  # accept/reject/done states have no out-transitions
    halt_kind: Optional[str] = None  # 'accept', 'reject', 'done', or None


@dataclass
class Routine:
    """A subroutine or main routine."""
    name: str             # canonical name (filename stem)
    display_name: str     # original name from the YAML, may have spaces/specials
    states: dict[str, State] = field(default_factory=dict)
    start_state: Optional[str] = None
    is_main: bool = False
    # For TMVRepr emission (only meaningful for main):
    input: Optional[str] = None
    blank: str = ' '
    source_file: Optional[str] = None


@dataclass
class Program:
    """Collection of all loaded routines."""
    routines: dict[str, Routine] = field(default_factory=dict)
    main: Optional[Routine] = None
