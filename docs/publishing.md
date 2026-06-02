# Releasing `alloc-context`

Releases follow a **release-PR** flow. A version bump is reviewed as a normal
pull request; merging it to `main` automatically tags the version and runs the
release (PyPI, MCP Registry, VPS deploy). Production always runs what is on
`main`, and every `vX.Y.Z` tag points at a real `main` commit.

## How it works

Two workflows:

| Workflow | Trigger | Does |
|----------|---------|------|
| **release-pr** | `workflow_dispatch` | Bumps version files, opens `release/vX.Y.Z` PR to `main`. No publish. |
| **release** | push to `main` | If the current version has **no tag yet**: test → PyPI → MCP Registry + VPS → tag + GitHub release. |

The release workflow keys off "version on `main` has no matching tag". Normal
pushes (no version change) see the tag already exists and exit immediately.
Because the tag is created **after** publish and deploy succeed — in the same
run that the merge triggered — there is no reliance on tag-push events (which a
`GITHUB_TOKEN`-pushed tag cannot trigger).

Pipeline order: **check** (untagged version?) → **test** → **publish-pypi** →
**publish-mcp-registry** + **deploy** (parallel) → **finalize** (tag + release).

**publish-mcp-registry** waits for PyPI to index the new release (30s initial
delay, then polls until wheel + sdist artifacts appear for the version twice
in a row) before calling `mcp-publisher`. Re-run the **release** job if registry
publish still races PyPI propagation.

Registry publish polls PyPI until the new version is indexed (avoids a race
right after upload).

## Prerequisites

One-time setup:

| Item | Details |
|------|---------|
| **Version files** | Kept in sync by `scripts/bump_version.py` |
| **PyPI trusted publisher** | Owner `AllocContext`, repo `alloc-context`, workflow `release.yml`, environment *(blank)* |
| **VPS secrets** | `VPS_SSH_KEY`, `VPS_HOST` — see [self-hosting.md](self-hosting.md) |
| **Workflow permissions** | Repo Settings → Actions → General → **Read and write** for `GITHUB_TOKEN` |
| **Actions can open PRs** | Repo Settings → Actions → General → enable **Allow GitHub Actions to create and approve pull requests** (required for **release-pr**) |

Version files updated by the bump script:

- `pyproject.toml`
- `server.json` (top-level and `packages[0].version`)
- `alloccontext/__init__.py` (`__version__`)

## Cut a release

1. Actions → **release-pr** → **Run workflow**.

   | Mode | Inputs |
   |------|--------|
   | **Patch / minor / major** | `bump` = increment; leave `exact_version` empty |
   | **Exact version** | `exact_version` = e.g. `0.2.0` (overrides `bump`) |

2. Review the opened **`release/vX.Y.Z`** PR; wait for **ci** to pass.
3. **Merge to `main`.** The **release** workflow runs automatically: test →
   PyPI → MCP Registry + VPS deploy → tag `vX.Y.Z` + GitHub release.

Concurrency: one **release** run at a time per repository.

## Branch protection on `main`

The release PR is the human gate. The **release** workflow never pushes commits
to `main` — it only pushes the `vX.Y.Z` tag after a successful publish and
deploy, so no branch-protection bypass is required.

## Re-running a failed release

If a release fails before tagging (e.g. PyPI hiccup), `main` stays untagged.
**Re-run the failed `release` run** — `check` re-evaluates, PyPI publish uses
`skip-existing`, the registry publish is idempotent, and the VPS deploy is
repeatable, so a re-run completes safely.

## Verify PyPI

```bash
pip install alloc-context==0.1.1
alloc-context --help
pip install "alloc-context[mcp]"
alloc-context mcp --help
```

Confirm the [PyPI project page](https://pypi.org/project/alloc-context/) shows
README, keywords, and **MCP Server** URL.

## Manual local tag (optional)

For a signed tag or offline bump, push the bump to `main` via PR as usual; the
**release** workflow tags it. To tag entirely by hand instead:

```bash
cd alloc-context
git checkout main && git pull
python3 scripts/bump_version.py --check "$(python3 scripts/bump_version.py --current)"
git tag -s "v$(python3 scripts/bump_version.py --current)" -m "Release"
git push origin "v$(python3 scripts/bump_version.py --current)"
```

Dry-run bump: `python3 scripts/bump_version.py --bump minor` (omit `--write`).

Verify sync: `python3 scripts/bump_version.py --check 0.1.1`

## Break-glass

| Situation | Action |
|-----------|--------|
| CI publish failed | Re-run the **release** run, or manual `twine upload` below |
| VPS-only hotfix | `deploy/rsync-to-vps.sh` — [self-hosting.md](self-hosting.md) |
| Registry-only publish | Actions → **publish-mcp-registry** → Run workflow |

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
