# tmc — ShortRepr to TMVRepr Compiler

Compiles ShortRepr Turing machine descriptions (Samhain's nesting-minimising
formalism with subroutines, α-parameterized states, ε-transitions, and chain
state bodies) to flat TMVRepr YAML.

## Usage

`python -m src.cli <clargs>`
- See [Compilation](#compilation) and elsewhere for details
- You may need to install `ruamel.yaml` (`pip install ruamel.yaml`)
- You may need to do this all in a `venv`
    - `python3 -m venv ./venv`
    - `. venv/bin/activate`

## Status

### What works

**The do2scomp/ test case compiles end-to-end and matches the reference
output exactly.** All three regression tests pass:

```
$ python tests/test_compiler.py
  ✓ test_do2scomp_standard      # 2sc + main + shift  → matches a.out
  ✓ test_do2scomp_alt           # 2sc + main_alt + shift → matches a_alt.out
  ✓ test_integration_with_minicomp  # output is valid input to minicomp.py
```

The output is byte-identical (semantically) to Samhain's hand-compiled
references — same start state, same state names, same transitions, same
writes, same directions, same dash-merged ε-collapsed names.

### What partially works

**Parsing all 23 UTMText files succeeds.** The full UTM (init.yml +
main.yml + proc.yml + 20 subroutines) loads cleanly into the AST. Use
`tmc --show-ast fixtures/UTMText/*.yml` to inspect.

**Linking traverses the full call graph.** With `--keep-unreachable`, 149
states are inlined across the deep call hierarchy:

```
main.proc.1.read_gamma.1.to_left.1.shift_dub_L.1.ready to read
```

Five levels of subroutine nesting, qualified correctly.

### What doesn't work yet (init.yml full compile)

- **`formalism: original` semantics** for init.yml: in this formalism,
  `Gamma`/`Sigma` are state names that should auto-iterate over tape
  symbols / input symbols. tmc currently treats them as plain state names.
- **Nested transition forms** like
  `['move to #', R, {epsilon: {'0': ['00', R], '1': [...]}}]` —
  tmc parses these as flat transitions, missing the nested ε-dispatch.
- **σ/γ "any tape symbol" wildcards** — Samhain's formalism uses these
  as match-anything atoms; tmc currently treats them as literal symbols.
- **State-name aliasing across deep namespace chains** has edge cases
  where similarly-named states (e.g. multiple `to front of dub`) can leak
  references between routines.

These limitations are documented for follow-up work. The pieces that
work — parser, basic linking, ε-resolution, dash-merge naming, transition
completion — are the foundation; the missing pieces are largely about
broader formalism coverage.

## Compilation

```
$ tmc <input1.yml> [input2.yml ...] [-o output.yml]
```

Flags:
- `-o FILE` — output file (default `a.out`; use `-` for stdout)
- `-v` — verbose (progress to stderr)
- `--keep-unreachable` — keep unreachable states in output
- `--show-ast` — pretty-print the parsed AST and exit

## End-to-end pipeline (do2scomp)

```
$ python -m src.cli fixtures/do2scomp/2sc.yml fixtures/do2scomp/main.yml \
    fixtures/do2scomp/shift.yml -o /tmp/machine.yml
$ cat /tmp/machine.yml | python TMVegs/minicomp.py > /tmp/tape.bits
$ # /tmp/tape.bits ready to load into the UTM
```

## Architecture

```
src/
  ast.py        — Routine, State, Transition, Program dataclasses
  parser.py     — YAML → AST (two-pass; tolerant name matching for
                  "shift dub R" → shift_dub_R routine refs)
  validator.py  — Lightweight checks (warns if no tape symbols / no main)
  expander.py   — α-state expansion (alpha/alpha' semantics; drops
                  the '-> alpha\\'' decorative suffix)
  linker.py     — Subroutine inlining + chain handling + ε-merge naming
                  + recursion handling (proc → ... → proc loops back)
  resolver.py   — ε-resolution, transition completion (undefined →
                  reject), unreachable pruning
  emitter.py    — Flat AST → TMVRepr YAML (Samhain's format style)
  cli.py        — Command-line entry point
```

## Test fixtures

- `fixtures/do2scomp/` — Samhain's binary string complement test case
  (3 ShortRepr files + 2 reference outputs)
- `fixtures/UTMText/` — full UTM transcription (23 files), including
  `init.yml`, `main.yml`, `proc.yml`, and 20 subroutines
