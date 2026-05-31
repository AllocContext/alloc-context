# Contributing

Thank you for your interest in AllocContext.

## Issues

Please open a GitHub Issue for:

- Bugs or incorrect rollup / context output
- ContextBundle schema feedback
- MCP tool and x402 integration feedback
- Documentation gaps

## Pull requests

This repository is maintained as a focused product codebase. **Unsolicited
external pull requests are not solicited.** If you want to propose a substantial
change, open an issue first so we can align on scope.

## Development setup

```bash
pip install -e ".[dev]"
pytest -q --cov=alloccontext --cov-report=term-missing:skip-covered
bandit -r alloccontext -c .bandit.yaml -ll
pip-audit
```

See [docs/security-ci.md](docs/security-ci.md) for CI parity details.

Do not commit secrets, `config/config.yaml`, or local `state/` databases.

## Code of conduct

Be constructive and respectful. No harassment or spam.
