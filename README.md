# retry-trace-check

An offline Python 3.10+ standard-library CLI for checking the observed shape of retry traces. It validates strict UTF-8 JSONL and a JSON attempt limit, then reports sequence gaps, attempts over the limit, and records after a call has succeeded.

It does not run retries or assess timing, backoff, idempotency, safety, or whether an outcome is truthful. IDs and input contents are never included in results.

## Install and run

```console
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: . .venv/bin/activate
python -m pip install .
retry-trace-check examples/valid.jsonl examples/policy.json
```

Exit status is `0` for valid, `1` for violations, and `2` for invalid input. Invalid input prints exactly `{"status":"invalid_input"}`. Run `retry-trace-check --help` for usage.

## Examples

See [`examples/`](examples/) for truthful synthetic cases, including valid, violating, invalid, and adversarial inputs. The tool checks observed records only; an error-only sequence is allowed even when fewer than the configured maximum attempts are present.

## Development

```console
python -m pip install -e '.[test]'
python -m pytest
```

The runtime has no third-party dependencies.
