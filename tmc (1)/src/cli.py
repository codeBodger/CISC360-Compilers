"""tmc — Turing Machine Compiler CLI.

Usage:
    tmc <input1.yml> [input2.yml ...] [-o output.yml]

Defaults output to a.out. Use -o - for stdout.
"""
from __future__ import annotations
import argparse
import sys
from .parser import parse_files, ParseError
from .validator import validate
from .expander import expand
from .linker import link, LinkError
from .resolver import resolve_epsilons, remove_unreachable
from .emitter import emit


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog='tmc',
                                description='Compile ShortRepr Turing machines to TMVRepr.')
    p.add_argument('inputs', nargs='+', help='Input YAML files')
    p.add_argument('-o', '--output', default='a.out',
                   help="Output file ('-' for stdout, default a.out)")
    p.add_argument('-v', '--verbose', action='store_true')
    p.add_argument('--keep-unreachable', action='store_true',
                   help='Keep unreachable states in output (for debugging)')
    p.add_argument('--show-ast', action='store_true',
                   help='Pretty-print the parsed AST and exit (no compilation)')
    args = p.parse_args(argv)

    try:
        program = parse_files(args.inputs)
    except ParseError as e:
        print(f"Parse error: {e}", file=sys.stderr)
        return 1
    except FileNotFoundError as e:
        print(f"Error: file not found: {e.filename}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error reading inputs: {type(e).__name__}: {e}", file=sys.stderr)
        return 1

    if args.show_ast:
        from pprint import pp
        pp(program)
        return 0

    if args.verbose:
        print(f"Parsed {len(program.routines)} routines; main={program.main.name if program.main else None}",
              file=sys.stderr)

    for issue in validate(program):
        print(f"  {issue}", file=sys.stderr)

    expand(program)
    if args.verbose:
        print("Expanded α/shorthand", file=sys.stderr)

    try:
        flat = link(program)
    except LinkError as e:
        print(f"Link error: {e}", file=sys.stderr)
        return 1

    if args.verbose:
        print(f"Linked: {len(flat.states)} states", file=sys.stderr)

    resolve_epsilons(flat)
    # Fill in undefined transitions with -> reject
    from .resolver import complete_transitions
    complete_transitions(flat, program.tape_symbols)
    remove_unreachable(flat, keep_unreachable=args.keep_unreachable)

    if args.verbose:
        print(f"After resolve/prune: {len(flat.states)} states", file=sys.stderr)

    output_str = emit(flat)
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
