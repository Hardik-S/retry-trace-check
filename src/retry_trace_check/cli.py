"""Command line entry point for retry-trace-check."""

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path


class InputError(Exception):
    """An input file does not satisfy the strict format contract."""


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise InputError()
        result[key] = value
    return result


def _reject_constant(_value):
    raise InputError()


def _decode_json(raw):
    try:
        return json.loads(raw, object_pairs_hook=_unique_object,
                          parse_constant=_reject_constant)
    except (ValueError, TypeError, RecursionError):
        raise InputError() from None


def _read_policy(path):
    try:
        raw = Path(path).read_bytes().decode("utf-8", errors="strict")
    except (OSError, UnicodeError):
        raise InputError() from None
    policy = _decode_json(raw)
    if (not isinstance(policy, dict) or set(policy) != {"max_attempts"}
            or isinstance(policy["max_attempts"], bool)
            or not isinstance(policy["max_attempts"], int)
            or policy["max_attempts"] <= 0):
        raise InputError()
    return policy["max_attempts"]


def _read_trace(path):
    try:
        raw = Path(path).read_bytes().decode("utf-8", errors="strict")
    except (OSError, UnicodeError):
        raise InputError() from None
    rows = []
    if raw == "":
        return rows
    # splitlines() accepts several Unicode separators outside the contract.
    lines = re.split(r"\r\n|\r|\n", raw)
    if lines[-1] == "":
        lines.pop()  # A single final line terminator is not an empty record.
    for line_no, line in enumerate(lines, 1):
        if line == "":
            raise InputError()
        row = _decode_json(line)
        if (not isinstance(row, dict) or set(row) != {"call_id", "attempt", "outcome"}
                or not isinstance(row["call_id"], str) or not row["call_id"]
                or isinstance(row["attempt"], bool) or not isinstance(row["attempt"], int)
                or row["attempt"] <= 0 or row["outcome"] not in ("success", "error")
                or not isinstance(row["outcome"], str)):
            raise InputError()
        rows.append((line_no, row["call_id"], row["attempt"], row["outcome"]))
    return rows


def validate(trace_path, policy_path):
    """Read and validate both files, returning the public result object."""
    max_attempts = _read_policy(policy_path)
    rows = _read_trace(trace_path)
    per_call = defaultdict(int)
    succeeded = set()
    findings = []
    for line, call_id, attempt, outcome in rows:
        per_call[call_id] += 1
        kinds = []
        if attempt != per_call[call_id]:
            kinds.append("sequence")
        if attempt > max_attempts:
            kinds.append("limit")
        if call_id in succeeded:
            kinds.append("after_success")
        findings.extend({"line": line, "kind": kind} for kind in kinds)
        if outcome == "success":
            succeeded.add(call_id)
    findings.sort(key=lambda finding: (finding["line"], finding["kind"]))
    return {
        "status": "violations" if findings else "valid",
        "call_count": len(per_call),
        "record_count": len(rows),
        "findings": findings,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(prog="retry-trace-check")
    parser.add_argument("trace", help="UTF-8 JSONL retry trace")
    parser.add_argument("policy", help="UTF-8 JSON policy")
    args = parser.parse_args(argv)
    try:
        result = validate(args.trace, args.policy)
    except InputError:
        result = {"status": "invalid_input"}
        code = 2
    else:
        code = 1 if result["status"] == "violations" else 0
    sys.stdout.write(json.dumps(result, ensure_ascii=False, separators=(",", ":")) + "\n")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
