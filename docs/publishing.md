# Releasing `alloc-context`

Releases follow a **release-PR** flow. A version bump is reviewed as a normal
pull request; merging it to `main` automatically tags the version and runs the
release (PyPI + self-host MCP Registry listing). Production VPS deploy and
hosted MCP advertising have been **removed**.

## How it works

| Workflow | Trigger | Does |
|----------|---------|------|
| **release-pr** | `workflow_dispatch` | Bumps version files, opens `release/vX.Y.Z` PR to `main`. No publish. |
| **release** | push to `main` | If the current version has **no tag yet**: test → PyPI → MCP Registry (stdio package) → tag + GitHub release. |
| **publish-mcp-registry** | `workflow_dispatch` | Re-publish `server.json` only (no PyPI upload). |

The **release** registry step lists the **PyPI stdio package** for self-host
install — not a hosted URL. See [distribution.md](distribution.md).

The release workflow keys off "version on `main` has no matching tag". Normal
pushes (no version change) see the tag already exists and exit immediately.
Because the tag is created **after** publish steps succeed — in the same run
that the merge triggered — there is no reliance on tag-push events (which a
`GITHUB_TOKEN`-pushed tag cannot trigger).

Pipeline order: **check** (untagged version?) → **test** → **publish-pypi** →
**publish-mcp-registry** → **finalize** (tag + release).

**publish-mcp-registry** waits for PyPI to index the new release before calling
`mcp-publisher`. Re-run the **release** job if registry publish races PyPI
propagation. Use the standalone **publish-mcp-registry** workflow for
registry-only republish without a version bump.

## Prerequisites

One-time setup:

| Item | Details |
|------|---------|
| **Version files** | Kept in sync by `scripts/bump_version.py` |
| **PyPI trusted publisher** | Owner `AllocContext`, repo `alloc-context`, workflow `release.yml`, environment *(blank)* |
| **Workflow permissions** | Repo Settings → Actions → General → **Read and write** for `GITHUB_TOKEN` |
| **Actions can open PRs** | Org **and** repo: Settings → Actions → General → **Read and write permissions** + **Allow GitHub Actions to create and approve pull requests** (required for **release-pr**). Org first: [AllocContext Actions settings](https://github.com/organizations/AllocContext/settings/actions); then [repo Actions settings](https://github.com/AllocContext/alloc-context/settings/actions). |
| **RELEASE_PR_TOKEN** *(optional)* | Repo secret — PAT with `repo` scope used when `GITHUB_TOKEN` cannot open PRs. Workflow falls back to `github.token` when unset. |

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
   PyPI → MCP Registry (self-host stdio listing) → tag `vX.Y.Z` + GitHub release.

Concurrency: one **release** run at a time per repository.

## Branch protection on `main`

The release PR is the human gate. The **release** workflow never pushes commits
to `main` — it only pushes the `vX.Y.Z` tag after a successful publish, so no
branch-protection bypass is required.

## Troubleshooting **release-pr**

| Symptom | Fix |
|---------|-----|
| `GitHub Actions is not permitted to create or approve pull requests` | Enable **Allow GitHub Actions to create and approve pull requests** on the **org** and **repo** (see prerequisites). Re-run **release-pr** — it reuses `release/vX.Y.Z` if the branch was already pushed. |
| Branch pushed, no PR | Open PR manually from the branch, or add `RELEASE_PR_TOKEN` and re-run. |
| `Tag vX.Y.Z already exists` | Version already released; bump again only after shipping the prior tag. |

Current repo check (needs `admin:repo` PAT): `gh api repos/AllocContext/alloc-context/actions/permissions/workflow` — `can_approve_pull_request_reviews` must be `true`.

## Re-running a failed release

If a release fails before tagging (e.g. PyPI hiccup), `main` stays untagged.
**Re-run the failed `release` run** — `check` re-evaluates, PyPI publish uses
`skip-existing`, and registry publish is idempotent, so a re-run completes safely.

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
| VPS-only hotfix | `deploy/rsync-to-vps.sh` — historical; see [self-hosting.md](self-hosting.md) |
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
