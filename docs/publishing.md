# Publishing `alloc-context` to PyPI

Production releases use a single GitHub Actions **release** workflow. One run
bumps versions (optional), publishes to PyPI, deploys to the VPS, and creates
the `vX.Y.Z` tag **after** success. Pushes to `main` run tests only (no deploy).

The operator repo (`alloc-context-operator`) still deploys on every `main` push.

## Architecture

| Trigger | Use case |
|---------|----------|
| **workflow_dispatch** | Normal releases from GitHub Actions UI |
| **Tag push** `vX.Y.Z` | Manual local tag (break-glass or signed tags) |

The automated path does **not** rely on tag pushes to start another workflow
(which fails when the tag is pushed by `GITHUB_TOKEN`). Tagging happens in the
same run after PyPI publish and VPS deploy succeed.

Pipeline order: **gate** (green `main` CI) → **test** → **prepare** (bump) →
**validate-version** → **publish-pypi** → **deploy** → **finalize-tag**.

## Prerequisites

One-time setup:

| Item | Details |
|------|---------|
| **Version files** | Kept in sync by `scripts/bump_version.py` |
| **PyPI trusted publisher** | Owner `negillett`, repo `alloc-context`, workflow `release.yml`, environment *(blank)* |
| **VPS secrets** | `VPS_SSH_KEY`, `VPS_HOST` — see [self-hosting.md](self-hosting.md) |
| **Workflow permissions** | Repo Settings → Actions → General → **Read and write** for `GITHUB_TOKEN` |

Version files updated by the bump script:

- `pyproject.toml`
- `server.json` (top-level and `packages[0].version`)
- `alloccontext/__init__.py` (`__version__`)

## Release from GitHub Actions (recommended)

1. Merge changes to `main`; wait for **ci** to pass.
2. Actions → **release** → **Run workflow** (branch: `main`).
3. Choose one mode:

| Mode | Inputs |
|------|--------|
| **Patch / minor / major** | `bump` = increment; leave `exact_version` empty; `tag_only` = false |
| **Exact version** | `exact_version` = e.g. `0.2.0`; `tag_only` = false |
| **First release / no bump** | `tag_only` = true (releases current version, e.g. `0.1.0`) |

4. Watch the run: test → bump commit (if any) → PyPI → VPS smoke/x402 → tag.

Concurrency: only one **release** run at a time per repository.

## First release (`v0.1.0`)

When version files are already `0.1.0` and no tag exists:

1. Configure PyPI trusted publisher.
2. Run **release** with **`tag_only` = true**.
3. Workflow validates files, publishes, deploys, then pushes `v0.1.0`.

## Manual local tag (optional)

For a signed tag or offline bump:

```bash
cd alloc-context
python3 scripts/bump_version.py --bump patch --write
git add pyproject.toml server.json alloccontext/__init__.py
git commit -m "Bump version to 0.1.1."
git tag -s v0.1.1 -m "Release 0.1.1"
git push origin main && git push origin v0.1.1
```

A local tag push triggers **release** (validate → PyPI → deploy). No
`finalize-tag` job — the tag already exists.

Dry-run bump: `python3 scripts/bump_version.py --bump minor` (omit `--write`).

Verify sync: `python3 scripts/bump_version.py --check 0.1.0`

## Verify PyPI

```bash
pip install alloc-context==0.1.0
alloc-context --help
pip install "alloc-context[mcp]"
alloc-context mcp --help
```

Confirm the [PyPI project page](https://pypi.org/project/alloc-context/) shows
README, keywords, and **MCP Server** URL.

## After PyPI publish

1. Publish or refresh the MCP Registry entry — see [distribution.md](distribution.md).
2. Wait for directory mirrors or submit manually.

## Break-glass

| Situation | Action |
|-----------|--------|
| CI publish failed | Manual `twine upload` — see below |
| VPS-only hotfix | `deploy/rsync-to-vps.sh` — [self-hosting.md](self-hosting.md) |
| Re-run failed release | Fix root cause; re-run **release** (`tag_only` if bump already on `main`) |

Manual PyPI upload:

```bash
cd alloc-context
python3.11 -m venv .venv && source .venv/bin/activate
pip install -U build twine
rm -rf dist/
python -m build
twine check dist/*
twine upload dist/*
```

Use username `__token__` and a PyPI API token as the password.
