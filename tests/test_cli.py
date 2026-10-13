import json
import subprocess
import sys

import pytest

from retry_trace_check.cli import InputError, validate


def write(tmp_path, trace, policy='{"max_attempts":3}'):
    trace_path = tmp_path / "trace.jsonl"
    policy_path = tmp_path / "policy.json"
    trace_path.write_bytes(trace if isinstance(trace, bytes) else trace.encode("utf-8"))
    policy_path.write_text(policy, encoding="utf-8")
    return trace_path, policy_path


def test_interleaving_error_only_and_inclusive_limit(tmp_path):
    trace, policy = write(tmp_path,
        '{"call_id":"a","attempt":1,"outcome":"error"}\r\n'
        '{"call_id":"b","attempt":1,"outcome":"error"}\r'
        '{"call_id":"a","attempt":2,"outcome":"error"}\n'
        '{"call_id":"a","attempt":3,"outcome":"success"}')
    assert validate(trace, policy) == {
        "status": "valid", "call_count": 2, "record_count": 4, "findings": []}


def test_gap_duplicate_out_of_order_and_multiple_sorted_findings(tmp_path):
    trace, policy = write(tmp_path,
        '{"call_id":"a","attempt":2,"outcome":"success"}\n'
        '{"call_id":"a","attempt":2,"outcome":"error"}\n'
        '{"call_id":"a","attempt":1,"outcome":"error"}\n')
    result = validate(trace, policy)
    assert result["status"] == "violations"
    assert result["findings"] == [
        {"line": 1, "kind": "sequence"},
        {"line": 2, "kind": "after_success"},
        {"line": 3, "kind": "after_success"},
        {"line": 3, "kind": "sequence"},
    ]


def test_attempt_over_limit_and_post_success(tmp_path):
    trace, policy = write(tmp_path,
        '{"call_id":"a","attempt":1,"outcome":"success"}\n'
        '{"call_id":"a","attempt":5,"outcome":"error"}')
    assert validate(trace, policy)["findings"] == [
        {"line": 2, "kind": "after_success"},
        {"line": 2, "kind": "limit"},
        {"line": 2, "kind": "sequence"},
    ]


@pytest.mark.parametrize("raw", [
    b"\xff", b"\n", b'{"call_id":"a","attempt":1,"outcome":"error"}\n\n',
    b'{"call_id":"a","attempt":1,"outcome":"error","x":0}',
    b'{"call_id":"a","attempt":1,"attempt":1,"outcome":"error"}',
    b'{"call_id":"a","attempt":1,"outcome":"NaN"}',
    b'{"call_id":"a","attempt":1.0,"outcome":"success"}',
    b'{"call_id":"a","attempt":1,"outcome":"success"}\v',
])
def test_strict_trace_rejections(tmp_path, raw):
    trace, policy = write(tmp_path, raw)
    with pytest.raises(InputError):
        validate(trace, policy)


@pytest.mark.parametrize("policy", [
    '{"max_attempts":true}', '{"max_attempts":0}', '{"max_attempts":1.2}',
    '{"max_attempts":1,"extra":0}', '{"max_attempts":2,"max_attempts":3}',
    '{"max_attempts":NaN}', '[]',
])
def test_strict_policy_rejections(tmp_path, policy):
    trace, policy_path = write(tmp_path, "", policy)
    with pytest.raises(InputError):
        validate(trace, policy_path)


def test_empty_trace_is_valid(tmp_path):
    trace, policy = write(tmp_path, "")
    assert validate(trace, policy) == {
        "status": "valid", "call_count": 0, "record_count": 0, "findings": []}


def test_invalid_input_has_exact_stdout_no_stderr_or_echo(tmp_path):
    trace, policy = write(tmp_path,
        '{"call_id":"private-secret","attempt":true,"outcome":"success"}')
    proc = subprocess.run([sys.executable, "-m", "retry_trace_check.cli", str(trace), str(policy)],
                          capture_output=True, text=True)
    assert proc.returncode == 2
    assert proc.stdout == '{"status":"invalid_input"}\n'
    assert proc.stderr == ""
    assert "private-secret" not in proc.stdout + proc.stderr


def test_help():
    proc = subprocess.run([sys.executable, "-m", "retry_trace_check.cli", "--help"],
                          capture_output=True, text=True)
    assert proc.returncode == 0
    assert "usage:" in proc.stdout


def test_cli_violations_exit_code_and_no_ids(tmp_path):
    trace, policy = write(tmp_path, '{"call_id":"secret","attempt":2,"outcome":"error"}')
    proc = subprocess.run([sys.executable, "-m", "retry_trace_check.cli", str(trace), str(policy)],
                          capture_output=True, text=True)
    assert proc.returncode == 1
    assert json.loads(proc.stdout)["findings"] == [{"line": 1, "kind": "sequence"}]
    assert "secret" not in proc.stdout + proc.stderr
