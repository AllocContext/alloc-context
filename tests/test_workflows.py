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


def test_release_workflow_unified_pipeline():
    workflow = _load_workflow("release.yml")
    on = _workflow_on(workflow)
    assert "workflow_dispatch" in on
    inputs = on["workflow_dispatch"]["inputs"]
    assert "bump" in inputs
    assert "exact_version" in inputs
    assert "tag_only" in inputs
    assert on["push"]["tags"] == ["v[0-9]+.[0-9]+.[0-9]+"]
    assert workflow["concurrency"]["group"].startswith("release-")

    jobs = workflow["jobs"]
    assert jobs["deploy"]["needs"] == ["validate-version", "publish-pypi"]
    assert jobs["finalize-tag"]["needs"] == [
        "prepare",
        "validate-version",
        "publish-pypi",
        "deploy",
    ]

    prepare_runs = [step.get("run", "") for step in _job_steps(workflow, "prepare")]
    assert any("scripts/bump_version.py" in run for run in prepare_runs)

    validate_runs = [
        step.get("run", "") for step in _job_steps(workflow, "validate-version")
    ]
    assert any("scripts/bump_version.py --check" in run for run in validate_runs)

    deploy_steps = _job_steps(workflow, "deploy")
    names = [step.get("name", "") for step in deploy_steps]
    assert "Rsync to VPS" in names
    assert "Install on VPS" in names
    install = next(step for step in deploy_steps if step.get("name") == "Install on VPS")
    assert "deploy/remote-install.sh" in install["run"]

    publish_steps = _job_steps(workflow, "publish-pypi")
    publish_runs = [step.get("run", "") for step in publish_steps]
    assert any("python -m build" in run for run in publish_runs)
    assert any(
        step.get("uses", "").startswith("pypa/gh-action-pypi-publish")
        for step in publish_steps
    )

    finalize_runs = [step.get("run", "") for step in _job_steps(workflow, "finalize-tag")]
    assert any("git push origin" in run and "TAG" in run for run in finalize_runs)
