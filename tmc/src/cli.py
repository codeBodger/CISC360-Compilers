"""CLI for tmc (Turing Machine Compiler).

Usage:
    tmc <input1.yml> [input2.yml ...] [-o output.yml]

Defaults output to a.out. Use -o - for stdout.
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

from .parser import parse_files, ParseError
from .validator import validate
from .expander import expand
from .linker import link, LinkError
from .resolver import resolve_epsilons, merge_end_states, remove_unreachable
from .emitter import emit_manual


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog='tmc',
                                     description='Compile ShortRepr Turing machine YAML to TMVRepr.')
    parser.add_argument('inputs', nargs='+', help='Input YAML files')
    parser.add_argument('-o', '--output', default='a.out',
                        help="Output file (default a.out, '-' for stdout)")
    parser.add_argument('--no-link', action='store_true',
                        help='Skip linking (for debugging)')
    parser.add_argument('-v', '--verbose', action='store_true')
    args = parser.parse_args(argv)

    # Parse
    try:
        program = parse_files(args.inputs)
    except ParseError as e:
        print(f"Parse error: {e}", file=sys.stderr)
        return 1

    if args.verbose:
        print(f"Parsed {len(program.routines)} routines", file=sys.stderr)
        if program.main:
            print(f"Main: {program.main.name}", file=sys.stderr)

    # Validate
    issues = validate(program)
    errors = [i for i in issues if i.severity == 'error']
    warnings = [i for i in issues if i.severity == 'warning']
    for w in warnings:
        print(f"  {w}", file=sys.stderr)
    for e in errors:
        print(f"  {e}", file=sys.stderr)
    if errors:
        print(f"{len(errors)} error(s); aborting", file=sys.stderr)
        return 1

    # Expand
    expand(program)
    if args.verbose:
        print("Expanded shorthands", file=sys.stderr)

    # Link
    if args.no_link:
        # Output the main routine as-is
        if program.main is None:
            print("No main to emit", file=sys.stderr)
            return 1
        flat = program.main
    else:
        try:
            flat = link(program)
        except LinkError as e:
            print(f"Link error: {e}", file=sys.stderr)
            return 1
        if args.verbose:
            print(f"Linked: {len(flat.states)} states", file=sys.stderr)

    # Resolve epsilons, merge end states, prune
    resolve_epsilons(flat)
    merge_end_states(flat)
    remove_unreachable(flat)
    if args.verbose:
        print(f"After resolve/merge/prune: {len(flat.states)} states", file=sys.stderr)

    # Emit
    output_str = emit_manual(flat)

    if args.output == '-':
        sys.stdout.write(output_str)
    else:
        with open(args.output, 'w') as f:
            f.write(output_str)
        if args.verbose:
            print(f"Wrote {args.output}", file=sys.stderr)

    return 0


if __name__ == '__main__':
    sys.exit(main())
