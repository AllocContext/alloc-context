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


def test_ci_deploys_to_vps_on_main_push():
    workflow = _load_workflow("ci.yml")
    deploy = workflow["jobs"]["deploy"]
    assert deploy["needs"] in (["test"], "test")
    assert "github.ref == 'refs/heads/main'" in deploy["if"]
    assert "github.event_name == 'push'" in deploy["if"]
    steps = _job_steps(workflow, "deploy")
    names = [step.get("name", "") for step in steps]
    assert "Rsync to VPS" in names
    assert "Install on VPS" in names
    install = next(step for step in steps if step.get("name") == "Install on VPS")
    assert "deploy/remote-install.sh" in install["run"]
