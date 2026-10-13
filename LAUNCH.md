# Launch note

## v0.1.0

Install with `python -m pip install .`; run `retry-trace-check TRACE.jsonl POLICY.json`. This release validates strict UTF-8 input, observed per-call attempt order, inclusive maximum attempt limits, and records after success. Exit codes: 0 valid, 1 violations, 2 invalid input.

This is an offline shape checker for synthetic or otherwise authorized records. It does not execute retry behavior, establish provenance, or assess runtime safety. Results do not establish that recorded outcomes are true.
