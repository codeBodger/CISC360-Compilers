# tmc — Turing Machine Compiler

Compiles ShortRepr Turing machine descriptions (with subroutines, σ/γ shorthand,
ε-transitions, exit dispatchers) to flat TMVRepr YAML compatible with
[turingmachine.io](https://turingmachine.io) and Samhain's TMVegs/ format.

## Status

**Working end-to-end.** The compiler:

1. Parses ShortRepr YAML using `ruamel.yaml` (handles list-keyed transitions,
   chain-form state bodies, dispatcher keys like `yes epsilon`, etc.)
2. Validates the program (catches unresolved subroutine calls, unknown state
   gotos, naming-convention mismatches via fuzzy aliasing)
3. Expands shorthand meta-symbols (`sigma_0`, `sigma`, `gamma`, `alpha_beta`)
   with correct precedence — concrete symbols override general shorthands
4. Inlines subroutine calls — multiple call sites produce distinct prefixed
   copies (e.g. `scan_right_1__scan`, `scan_right_2__scan`)
5. Handles chain-form state bodies (a list of subroutine calls in sequence,
   each step's `done` chaining to the next)
6. Resolves ε-transitions and removes ε-only states
7. Merges end-states (preserves `success`/`failure` if that's what input uses,
   else canonical `accept`/`reject`)
8. Removes unreachable states
9. Emits TMVRepr YAML matching Samhain's TMVegs/2scomp.yaml format byte-style

## Tests

```
$ python tests/test_compiler.py
  ✓ test_2scomp_round_trip      # Parse Samhain's TMVegs/2scomp.yaml, recompile,
                                #   verify semantically identical
  ✓ test_odd_as_round_trip      # Same for TMVegs/odd_as.yaml
  ✓ test_subroutine_inlining    # Multi-call subroutine produces distinct copies
  ✓ test_sigma_expansion        # sigma_0 expands to [0,1,'#'] correctly
  ✓ test_chain_inlining         # Chain of subroutine calls flattens correctly

All 5 tests passed.
```

The first two tests verify that the compiler can reproduce Samhain's TMVegs/
files byte-for-byte semantically (states, transitions, halt states, all
identical after parsing both into structured form).

## Usage

```
$ tmc <main.yaml> [subroutine1.yaml subroutine2.yaml ...] [-o output.yaml]
```

- Output defaults to `a.out`. Use `-o -` for stdout.
- `--no-link` skips the linker (useful for debugging the parser/expander).
- `-v` prints progress to stderr.
- One of the input files must contain a `start state:` field (the main routine).
  Subroutine files have only state definitions (no `start state` or `input`).

## Architecture

```
src/
  ast.py        — Routine, State, Transition, Program dataclasses
  parser.py     — YAML → AST (handles all formalism shapes)
  validator.py  — Detects unresolved references, naming mismatches
  expander.py   — Expands sigma_0 / sigma / gamma / alpha shorthands
  linker.py     — Inlines subroutine calls with state-name prefixing
  resolver.py   — Resolves ε-transitions, merges end-states, prunes unreachable
  emitter.py    — AST → TMVRepr YAML (matches TMVegs format)
  cli.py        — Command-line entry point
```

## What's known to work

- ✅ Parse and re-emit `TMVegs/2scomp.yaml` (Samhain's reference example)
- ✅ Parse and re-emit `TMVegs/odd_as.yaml`
- ✅ Compile a ShortRepr file with subroutine calls (linker generates distinct
  state copies per call site)
- ✅ Chain semantics: list-form state body chains subroutine calls, each step's
  `done` going to the next step
- ✅ Shorthand expansion with precedence (concrete > sigma_0 > sigma > gamma)
- ✅ ε-resolution: bypass ε-only states
- ✅ Halt-state preservation (uses `success`/`failure` if input uses them)

## What's still rough

- α-parameterized state expansion (Phase 2 of expander) is sketched but not
  thoroughly tested. It works for simple cases but needs more fixtures from
  the real init.yml/UTMText routines to validate.
- Naming-convention mismatches between filename munging (e.g. `verify #1` ↔
  `verify_sharp1.yml`) are handled by fuzzy aliasing in the validator/linker,
  but if Wesley/Samhain's actual files have edge cases I haven't seen,
  there'll be more aliases to add.

## Testing against real init.yml

Once you pull the latest `wesleysimpson/yaml-transcriptions` branch, run:

```
$ tmc UTMText/init.yml UTMText/*.yml -o /tmp/utm_compiled.yaml
$ # then load /tmp/utm_compiled.yaml at https://turingmachine.io
```

If something breaks, the validator will report it before the linker runs.
The most likely failure modes:

1. **Subroutine name mismatch** — file is named `foo_bar.yml` but called as
   `"foo bar"` in YAML. Fuzzy aliasing handles most cases; if not, add an
   explicit alias to `validator._build_aliases`.
2. **Recursive subroutine call** — the linker raises `LinkError`. Per
   formalism doc D3, this is expected. If found, the YAML needs to be
   restructured.
3. **α-state with non-standard naming** — if a state name doesn't follow the
   `something_alpha` convention, `expander._expand_alpha_states` won't pick
   it up. Add the new pattern there.
