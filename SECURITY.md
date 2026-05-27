# Security

## Reporting vulnerabilities

If you believe you have found a security issue, please **open a private
security advisory** on GitHub (Security → Advisories → New draft) rather than
filing a public issue.

Include steps to reproduce, affected components, and impact if known.

## Secrets

Never commit API keys, exchange credentials, or `.env` files. The repository
ignores `config/config.yaml`, `state/`, and `*.db`.

## Scope

AllocContext uses **read-only** exchange credentials when configured. It does
not place orders. Self-hosted deployments are your responsibility — restrict
file permissions on environment files and use least-privilege API keys.
