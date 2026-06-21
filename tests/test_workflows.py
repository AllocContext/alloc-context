from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"


def _load_workflow(name: str) -> dict:
    path = WORKFLOWS_DIR / name
    assert path.exists(), f"missing workflow {name}"
    with path.open() as handle:
        return yaml.safe_load(handle)


def _job_steps(workflow: dict, job_name: str | None = None) -> list[dict]:
    jobs = workflow["jobs"]
    if job_name is None:
        job_name = next(iter(jobs))
    return jobs[job_name]["steps"]


def _workflow_on(workflow: dict) -> dict:
    # PyYAML may parse bare `on:` as boolean True.
    return workflow.get("on") or workflow[True]


def test_ci_runs_pytest():
    workflow = _load_workflow("ci.yml")
    steps = _job_steps(workflow, "test")
    pytest_steps = [
        step for step in steps if step.get("run", "").strip().startswith("pytest")
    ]
    assert pytest_steps, "ci workflow must run pytest"


def test_ci_runs_actionlint_from_workspace_binary():
    workflow = _load_workflow("ci.yml")
    steps = _job_steps(workflow, "test")
    lint_steps = [step for step in steps if "actionlint" in step.get("run", "")]
    assert lint_steps, "ci workflow must lint workflows"
    run_script = lint_steps[0]["run"]
    assert "./actionlint" in run_script
    assert "1.7.12" in run_script


def test_ci_has_no_deploy_job():
    workflow = _load_workflow("ci.yml")
    assert "deploy" not in workflow["jobs"]


def test_bump_release_workflow_removed():
    assert not (WORKFLOWS_DIR / "bump-release.yml").exists()


def test_release_pr_workflow_opens_pr():
    workflow = _load_workflow("release-pr.yml")
    on = _workflow_on(workflow)
    assert "workflow_dispatch" in on
    inputs = on["workflow_dispatch"]["inputs"]
    assert "bump" in inputs
    assert "exact_version" in inputs
    # Opening a release PR must not publish or deploy.
    assert "tag_only" not in inputs

    steps = _job_steps(workflow, "open-release-pr")
    runs = [step.get("run", "") for step in steps]
    assert any("scripts/bump_version.py" in run for run in runs)
    assert any("git push -u origin" in run and "release/v" in run for run in runs)
    assert any("gh pr create" in run for run in runs)


def test_release_workflow_triggers_on_main_push_only():
    workflow = _load_workflow("release.yml")
    on = _workflow_on(workflow)
    assert on["push"]["branches"] == ["main"]
    # No manual or tag trigger — releases are driven by merges to main.
    assert "workflow_dispatch" not in on
    assert "tags" not in on["push"]
    assert workflow["concurrency"]["group"].startswith("release-")


def test_release_workflow_gates_on_untagged_version():
    workflow = _load_workflow("release.yml")
    check = workflow["jobs"]["check"]
    assert check["outputs"]["release"]
    check_runs = [step.get("run", "") for step in _job_steps(workflow, "check")]
    assert any("--current" in run for run in check_runs)
    assert any("ls-remote --tags" in run for run in check_runs)
    # Every downstream job is conditioned on the release decision.
    for job_name in ("test", "publish-pypi", "publish-mcp-registry", "finalize"):
        cond = workflow["jobs"][job_name]["if"]
        assert "needs.check.outputs.release" in cond


def test_release_workflow_publishes_then_finalizes():
    workflow = _load_workflow("release.yml")
    jobs = workflow["jobs"]

    assert "deploy" not in jobs

    publish_steps = _job_steps(workflow, "publish-pypi")
    publish_runs = [step.get("run", "") for step in publish_steps]
    assert any("python -m build" in run for run in publish_runs)
    pypi_step = next(
        step
        for step in publish_steps
        if step.get("uses", "").startswith("pypa/gh-action-pypi-publish")
    )
    # Idempotent re-runs must not fail on an already-uploaded version.
    assert pypi_step["with"]["skip-existing"] is True

    registry_runs = [
        step.get("run", "") for step in _job_steps(workflow, "publish-mcp-registry")
    ]
    assert any("publish-mcp-registry.sh" in run for run in registry_runs)

    finalize = jobs["finalize"]
    assert set(finalize["needs"]) == {
        "check",
        "publish-pypi",
        "publish-mcp-registry",
    }
    finalize_runs = [step.get("run", "") for step in _job_steps(workflow, "finalize")]
    assert any("git tag" in run for run in finalize_runs)
    assert any("gh release create" in run for run in finalize_runs)


def test_release_workflow_drops_branch_juggling_jobs():
    workflow = _load_workflow("release.yml")
    jobs = workflow["jobs"]
    for removed in ("gate", "prepare", "validate-version", "finalize-tag", "sync-main"):
        assert removed not in jobs


def test_publish_mcp_registry_workflow_dispatch():
    workflow = _load_workflow("publish-mcp-registry.yml")
    on = _workflow_on(workflow)
    assert "workflow_dispatch" in on
    runs = [step.get("run", "") for step in _job_steps(workflow, "publish")]
    assert any("install-mcp-publisher" in run for run in runs)
    assert any("publish-mcp-registry.sh" in run for run in runs)


def test_publish_mcp_registry_waits_for_pypi():
    assert (REPO_ROOT / "scripts/wait-for-pypi.sh").exists()
    assert (REPO_ROOT / "scripts/check_pypi_release_json.py").exists()


def test_publish_mcp_registry_workflow_waits_before_publish():
    workflow = _load_workflow("publish-mcp-registry.yml")
    runs = [step.get("run", "") for step in _job_steps(workflow, "publish")]
    assert any("wait-for-pypi.sh" in run for run in runs)
    assert any("publish-mcp-registry.sh" in run for run in runs)


def test_release_publish_mcp_registry_waits_with_version_env():
    workflow = _load_workflow("release.yml")
    job = workflow["jobs"]["publish-mcp-registry"]
    assert job["env"]["PYPI_VERSION"] == "${{ needs.check.outputs.version }}"
    runs = [step.get("run", "") for step in _job_steps(workflow, "publish-mcp-registry")]
    assert any("wait-for-pypi.sh" in run for run in runs)


def test_paid_smoke_and_vps_x402_workflows_removed():
    assert not (WORKFLOWS_DIR / "paid-smoke.yml").exists()
    assert not (WORKFLOWS_DIR / "x402-check.yml").exists()
