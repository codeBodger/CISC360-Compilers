"""Lightweight validator: reports unresolved targets and warnings."""
from __future__ import annotations
from .ast import Program, Routine


class ValidationIssue:
    def __init__(self, severity: str, msg: str, where: str = ''):
        self.severity = severity
        self.msg = msg
        self.where = where

    def __str__(self):
        loc = f" [{self.where}]" if self.where else ''
        return f"{self.severity.upper()}{loc}: {self.msg}"


def validate(program: Program) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if program.main is None:
        issues.append(ValidationIssue('warning', 'No main routine identified'))
    if not program.tape_symbols:
        issues.append(ValidationIssue(
            'warning',
            'No tape symbols declared — write/state disambiguation may be wrong. '
            "If this is a standalone subroutine compile, consider including a main routine that declares 'tape symbols'."))
    return issues
