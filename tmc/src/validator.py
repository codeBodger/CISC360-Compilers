"""Validator: detect bugs in the parsed program before linking."""
from __future__ import annotations
from .ast import Program, Routine, State, Transition


END_STATES = {'done', 'yes', 'no', 'accept', 'reject', 'success', 'failure'}


class ValidationIssue:
    def __init__(self, severity: str, msg: str, where: str = ''):
        self.severity = severity  # 'error' | 'warning'
        self.msg = msg
        self.where = where

    def __str__(self):
        prefix = self.severity.upper()
        loc = f" [{self.where}]" if self.where else ''
        return f"{prefix}{loc}: {self.msg}"


def validate(program: Program) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    if program.main is None:
        issues.append(ValidationIssue('warning', 'No main routine specified'))

    # Build set of routine names (with fuzzy aliases)
    routine_aliases = _build_aliases(program)

    for routine in program.routines.values():
        for state in routine.states.values():
            for t in state.transitions:
                # Check subroutine call resolution
                if t.is_subroutine_call and t.target:
                    if not _resolve_alias(t.target, routine_aliases, routine):
                        # Could be a state goto
                        if t.target not in routine.states and t.target not in END_STATES:
                            issues.append(ValidationIssue(
                                'error',
                                f"unresolved call/goto to '{t.target}'",
                                where=f"{routine.name}:{state.name}",
                            ))
                # Check state goto resolution
                elif t.target and not t.is_subroutine_call:
                    if (t.target not in routine.states
                            and t.target not in END_STATES
                            and not _resolve_alias(t.target, routine_aliases, routine)):
                        issues.append(ValidationIssue(
                            'warning',
                            f"goto to unknown state '{t.target}'",
                            where=f"{routine.name}:{state.name}",
                        ))

    return issues


def _build_aliases(program: Program) -> dict[str, str]:
    """Build a name-aliasing map for fuzzy routine name matching."""
    aliases: dict[str, str] = {}
    for name in program.routines:
        aliases[name] = name
        # Also accept name with underscores stripped
        aliases[name.replace('_', '').lower()] = name
        aliases[name.lower()] = name
    return aliases


def _resolve_alias(name: str, aliases: dict[str, str], routine: Routine) -> str | None:
    if name in aliases:
        return aliases[name]
    flat = name.replace('_', '').replace(' ', '').lower()
    if flat in aliases:
        return aliases[flat]
    # Try munged form
    munged = (name.replace("'", 'p').replace('#', 'sharp').replace('*', 'star')
              .replace('γ', 'g').replace('α', 'alpha').replace('β', 'beta')
              .replace(' ', '_'))
    if munged in aliases:
        return aliases[munged]
    return None
