# Security and quality CI

GitHub Actions runs three parallel gates on every push and pull request to
`main`:

| Job | Tool | Purpose |
|-----|------|---------|
| `test` | [pytest-cov](https://pytest-cov.readthedocs.io/) | Unit tests plus line coverage (minimum 75%) |
| `bandit` | [Bandit](https://bandit.readthedocs.io/) | Python SAST — fails on medium+ after documented skips |
| `pip-audit` | [pip-audit](https://pypi.org/project/pip-audit/) | Dependency vulnerability scan (OSV database) |

## Local parity

From the repo root:

```bash
pip install -e ".[dev]"
pytest -q --cov=alloccontext --cov-report=term-missing:skip-covered
bandit -r alloccontext -c .bandit.yaml -ll
pip-audit
```

Or from the workspace root:

```bash
scripts/run-quality-gates.sh alloc-context
```

## Bandit skips

False-positive skips live in [`.bandit.yaml`](../.bandit.yaml) with inline
comments. Do not add skips without documenting why the pattern is safe.

## Coverage

Threshold is configured in `pyproject.toml` under `[tool.coverage.report]`.
CI uploads `coverage.xml` as a workflow artifact for 14 days.
