from pathlib import Path

import yaml

WORKFLOW = Path(__file__).parent.parent / ".github" / "workflows" / "update-data.yml"


def load():
    doc = yaml.safe_load(WORKFLOW.read_text())
    doc["triggers"] = doc.get("on", doc.get(True))      # PyYAML czyta klucz "on" jako True
    return doc


def steps():
    return load()["jobs"]["update"]["steps"]


def test_triggers_manual_and_both_schedules():
    triggers = load()["triggers"]
    assert "workflow_dispatch" in triggers
    assert {s["cron"] for s in triggers["schedule"]} == {"0 */6 * * *", "*/30 * * * 5,6,0"}


def test_can_push_data_commits():
    assert load()["permissions"] == {"contents": "write"}


def test_runs_pipeline_into_public_data():
    runs = [s.get("run", "") for s in steps()]
    assert any("python data-pipeline/run.py --out public/data" in r for r in runs)
    assert any("git push" in r and "git diff --staged --quiet" in r for r in runs)   # commit tylko przy zmianie


def test_python_312_and_persistent_jolpica_cache():
    setup = next(s for s in steps() if s.get("uses", "").startswith("actions/setup-python"))
    assert setup["with"]["python-version"] == "3.12"
    cache = next(s for s in steps() if s.get("uses", "").startswith("actions/cache"))
    assert cache["with"]["path"] == ".cache/jolpica"
    assert cache["with"]["restore-keys"].startswith("jolpica-")
