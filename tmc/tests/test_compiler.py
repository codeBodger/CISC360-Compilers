"""Smoke tests for the compiler."""
import subprocess
import sys
import os
from pathlib import Path

ROOT = Path(__file__).parent.parent
FIXTURES = ROOT / 'fixtures'


def run_cli(*args):
    """Run the CLI and return (returncode, stdout, stderr)."""
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


def normalise_table(table):
    """Normalise a table for comparison: turn list-keys into sorted tuples,
    and turn dict values into sorted tuples."""
    if table is None:
        return None
    out = {}
    for state_name, body in table.items():
        if body is None:
            out[state_name] = None
            continue
        norm_body = {}
        for k, v in body.items():
            if isinstance(k, tuple):
                k = ('LIST', tuple(sorted(str(x) for x in k)))
            else:
                k = ('SCALAR', str(k))
            if isinstance(v, dict):
                v = tuple(sorted(v.items()))
            norm_body[k] = v
        out[state_name] = norm_body
    return out


def assert_equivalent(file_a, file_b, msg=''):
    """Assert two TMVRepr YAML files describe the same machine."""
    a = load_yaml(file_a)
    b = load_yaml(file_b)
    assert a.get('start state') == b.get('start state'), \
        f"{msg}: start state diff: {a.get('start state')} vs {b.get('start state')}"
    assert a.get('blank') == b.get('blank'), \
        f"{msg}: blank diff: {a.get('blank')!r} vs {b.get('blank')!r}"
    a_table = normalise_table(a.get('table'))
    b_table = normalise_table(b.get('table'))
    assert set(a_table.keys()) == set(b_table.keys()), \
        f"{msg}: state set diff: {set(a_table) ^ set(b_table)}"
    for state in a_table:
        assert a_table[state] == b_table[state], \
            f"{msg}: state '{state}' differs:\n  a: {a_table[state]}\n  b: {b_table[state]}"


def test_2scomp_round_trip():
    """Compiling 2scomp.yaml (already TMVRepr) should yield equivalent output."""
    rc, _, err = run_cli(str(FIXTURES / '2scomp_reference.yaml'),
                         '-o', '/tmp/test_2scomp.yaml')
    assert rc == 0, f"compile failed: {err}"
    assert_equivalent(FIXTURES / '2scomp_reference.yaml', '/tmp/test_2scomp.yaml',
                      'test_2scomp_round_trip')


def test_odd_as_round_trip():
    rc, _, err = run_cli(str(FIXTURES / 'odd_as_reference.yaml'),
                         '-o', '/tmp/test_odd.yaml')
    assert rc == 0, f"compile failed: {err}"
    assert_equivalent(FIXTURES / 'odd_as_reference.yaml', '/tmp/test_odd.yaml',
                      'test_odd_as_round_trip')


def test_subroutine_inlining():
    """Multi-call subroutine should produce distinct copies."""
    rc, _, err = run_cli(str(FIXTURES / 'twocall_main.yaml'),
                         str(FIXTURES / 'scan_right.yaml'),
                         '-o', '/tmp/test_link.yaml')
    assert rc == 0, f"compile failed: {err}"
    out = load_yaml('/tmp/test_link.yaml')
    states = set(out['table'].keys())
    # Two distinct copies of the subroutine + start + accept + reject
    assert any('scan_right_1' in s for s in states), f"missing 1st copy in {states}"
    assert any('scan_right_2' in s for s in states), f"missing 2nd copy in {states}"
    assert 'start' in states
    assert 'accept' in states
    assert 'reject' in states


def test_sigma_expansion():
    """sigma_0 should expand to [0, 1, '#']."""
    rc, _, err = run_cli(str(FIXTURES / 'sigma_test.yaml'),
                         '-o', '/tmp/test_sigma.yaml')
    assert rc == 0, f"compile failed: {err}"
    out = load_yaml('/tmp/test_sigma.yaml')
    # 'start' should have [0,1,'#'] as a key
    start_body = out['table']['start']
    keys = list(start_body.keys())
    has_sigma_expansion = any(
        isinstance(k, tuple) and set(str(x) for x in k) == {'0', '1', '#'}
        for k in keys
    )
    assert has_sigma_expansion, f"sigma_0 not expanded; keys={keys}"


def test_chain_inlining():
    """A chain of subroutine calls should produce a flat chain in output."""
    rc, _, err = run_cli(str(FIXTURES / 'chain_main.yaml'),
                         str(FIXTURES / 'scan_right.yaml'),
                         '-o', '/tmp/test_chain.yaml')
    assert rc == 0, f"compile failed: {err}"
    out = load_yaml('/tmp/test_chain.yaml')
    states = set(out['table'].keys())
    # Should have start, accept, reject, plus 2 distinct scan_right copies
    # (the chain produces only 2 calls, not 3, because chain_state's first call's
    # done implicitly chains to the second, replacing the explicit 'chain_state2' link)
    scan_copies = [s for s in states if 'scan_right' in s]
    assert len(scan_copies) >= 2, f"expected at least 2 scan_right copies, got {scan_copies}"
    assert 'start' in states
    assert 'accept' in states


if __name__ == '__main__':
    tests = [
        test_2scomp_round_trip,
        test_odd_as_round_trip,
        test_subroutine_inlining,
        test_sigma_expansion,
        test_chain_inlining,
    ]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"  ✓ {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"  ✗ {t.__name__}: {e}")
        except Exception as e:
            failed += 1
            print(f"  ✗ {t.__name__}: {type(e).__name__}: {e}")
    print()
    if failed:
        print(f"{failed}/{len(tests)} failed")
        sys.exit(1)
    else:
        print(f"All {len(tests)} tests passed.")
