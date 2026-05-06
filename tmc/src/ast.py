"""AST types for the ShortRepr Turing machine description.

Aligned with Samhain's nesting-minimising formalism:
- Routines have alphabet, tape_symbols, left-marker, blank, accept, reject metadata
- Transitions distinguish state targets from subroutine calls lexically
- α-parameterized states are recognised by name pattern
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Transition:
    """A single transition from a state on one or more read symbols."""
    read: list[str]                   # symbols that trigger this transition
    write: Optional[str] = None       # symbol to write (None = same as read)
    direction: Optional[str] = None   # 'L', 'R', or None (epsilon)
    target: Optional[str] = None      # next state name (None = stay/halt)
    is_subroutine_call: bool = False  # if True, target is a subroutine name
    exit_dispatch: dict[str, str] = field(default_factory=dict)
    # exit_dispatch maps {'done': state, 'yes': state, 'no': state, 'epsilon': state}


@dataclass
class State:
    name: str
    transitions: list[Transition] = field(default_factory=list)
    is_halt: bool = False
    halt_kind: Optional[str] = None   # 'accept', 'reject', 'done', or None
    is_chain: bool = False            # state body was a list of subroutine calls
    chain: list[Transition] = field(default_factory=list)
    # ^ When is_chain=True, transitions field is empty and chain holds the steps


@dataclass
class Routine:
    """A subroutine or main routine."""
    name: str                                      # filename stem (canonical)
    display_name: str                              # original name from YAML
    states: dict[str, State] = field(default_factory=dict)
    start_state: Optional[str] = None
    start_chain: list[str] = field(default_factory=list)
    # ^ if start state is a list (like main_alt), this holds the chain of subroutines
    is_main: bool = False
    # Metadata (only populated if main, or if subroutine declares them):
    alphabet: list[str] = field(default_factory=list)
    tape_symbols: list[str] = field(default_factory=list)
    left: Optional[str] = None
    blank: Optional[str] = None
    accept_name: str = 'accept'
    reject_name: str = 'reject'
    formalism: Optional[str] = None
    source_file: Optional[str] = None


@dataclass
class Program:
    """Collection of all loaded routines."""
    routines: dict[str, Routine] = field(default_factory=dict)
    main: Optional[Routine] = None
    tape_symbols: list[str] = field(default_factory=list)
    # ^ resolved from main, used by parser for disambiguation
