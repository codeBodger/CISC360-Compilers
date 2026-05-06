"""Tests against Samhain's do2scomp/ ShortRepr files.

These are real ShortRepr inputs with hand-compiled reference outputs. The
compiler is correct iff its output matches the references semantically.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
FIXTURES = ROOT / 'fixtures'


def run_cli(*args):
    result = subprocess.run(
        [sys.executable, '-m', 'src.cli'] + list(args),
        capture_output=True, text=True, cwd=str(ROOT),
    )
    return result.returncode, result.stdout, result.stderr


def load_yaml(path):
    from ruamel.yaml import YAML
    yaml = YAML(typ='safe')
    with open(path) as f:
        return yaml.load(f)


def normalise_body(body):
    if body is None:
        return None
    out = {}
    for k, v in body.items():
        if isinstance(k, tuple):
            k = ('LIST', tuple(sorted(str(x) for x in k)))
        else:
            k = ('SCALAR', str(k))
        if isinstance(v, dict):
            v = tuple(sorted(v.items()))
        out[k] = v
    return out


def assert_compiles_to(input_files, expected_path, label):
    """Compile input_files and assert the result matches expected_path semantically."""
    out_path = f'/tmp/test_{label}.out'
    rc, _, err = run_cli(*input_files, '-o', out_path)
    assert rc == 0, f"{label}: compile failed with rc={rc}\nstderr: {err}"

    mine = load_yaml(out_path)
    expected = load_yaml(expected_path)

    assert mine.get('start state') == expected.get('start state'), \
        f"{label}: start state mismatch: mine={mine.get('start state')!r} exp={expected.get('start state')!r}"
    assert mine.get('blank') == expected.get('blank'), \
        f"{label}: blank mismatch"

    m_states = set(mine['table'].keys())
    e_states = set(expected['table'].keys())
    assert m_states == e_states, \
        f"{label}: state set mismatch:\n  only mine: {m_states - e_states}\n  only exp:  {e_states - m_states}"

    for s in m_states:
        m_body = normalise_body(mine['table'][s])
        e_body = normalise_body(expected['table'][s])
        assert m_body == e_body, f"{label}: state {s!r} body differs:\n  mine: {m_body}\n  exp:  {e_body}"


def test_do2scomp_standard():
    """Compile 2sc.yml + main.yml + shift.yml; expect a.out."""
    assert_compiles_to(
        [str(FIXTURES / 'do2scomp/2sc.yml'),
         str(FIXTURES / 'do2scomp/main.yml'),
         str(FIXTURES / 'do2scomp/shift.yml')],
        FIXTURES / 'do2scomp/a.out',
        'standard',
    )


def test_do2scomp_alt():
    """Compile 2sc.yml + main_alt.yml + shift.yml; expect a_alt.out."""
    assert_compiles_to(
        [str(FIXTURES / 'do2scomp/2sc.yml'),
         str(FIXTURES / 'do2scomp/main_alt.yml'),
         str(FIXTURES / 'do2scomp/shift.yml')],
        FIXTURES / 'do2scomp/a_alt.out',
        'alt',
    )


def test_integration_with_minicomp():
    """The compiler's output should be valid input for Samhain's minicomp.py."""
    import os.path
    minicomp = '/tmp/minicomp.py'
    if not os.path.exists(minicomp):
        print("  (skipping: minicomp.py not at /tmp/minicomp.py)")
        return
    out_path = '/tmp/test_integration.out'
    rc, _, err = run_cli(
        str(FIXTURES / 'do2scomp/2sc.yml'),
        str(FIXTURES / 'do2scomp/main.yml'),
        str(FIXTURES / 'do2scomp/shift.yml'),
        '-o', out_path,
    )
    assert rc == 0, f"compile failed: {err}"

    # Pipe through minicomp.py
    with open(out_path) as f:
        result = subprocess.run(
            [sys.executable, minicomp],
            stdin=f, capture_output=True, text=True,
        )
    assert result.returncode == 0, \
        f"minicomp.py failed on tmc output:\n{result.stderr}"
    assert '#' in result.stdout, f"minicomp output missing # separator: {result.stdout!r}"


if __name__ == '__main__':
    tests = [
        test_do2scomp_standard,
        test_do2scomp_alt,
        test_integration_with_minicomp,
    ]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"  ✓ {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"  ✗ {t.__name__}:\n     {e}")
        except Exception as e:
            failed += 1
            print(f"  ✗ {t.__name__}: {type(e).__name__}: {e}")
    print()
    if failed:
        print(f"{failed}/{len(tests)} failed")
        sys.exit(1)
    else:
        print(f"All {len(tests)} tests passed.")
