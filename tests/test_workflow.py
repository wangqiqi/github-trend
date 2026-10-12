"""TASK-004 CI 与依赖加固测试。

用 YAML 解析而不是 grep：断言的是「配置真的生效」，不是「文本里出现过」。
"""

import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = REPO_ROOT / ".github" / "workflows"


def load_yaml(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def action_major(uses: str) -> int:
    """从 `actions/checkout@v4` 里取大版本号；取不到返回 -1。"""
    match = re.search(r"@v(\d+)", uses)
    return int(match.group(1)) if match else -1


def triggers(doc):
    """PyYAML 按 YAML 1.1 把裸 `on` 解析成布尔 True，这里两种都认。"""
    return doc.get("on", doc.get(True))


def steps_of(doc):
    return doc["jobs"]["update-trending"]["steps"]


def test_all_workflows_are_valid_yaml():
    files = sorted(WORKFLOWS.glob("*.yml"))
    assert files, "没有找到任何 workflow"
    for path in files:
        assert isinstance(load_yaml(path), dict), f"{path.name} 不是合法 YAML 映射"


# --- 抓取 workflow ---------------------------------------------------------

def test_update_workflow_has_concurrency():
    doc = load_yaml(WORKFLOWS / "update-trending.yml")
    assert "concurrency" in doc
    assert doc["concurrency"]["group"], "concurrency group 不能为空"
    assert doc["concurrency"]["cancel-in-progress"] is False


def test_update_workflow_has_timeout():
    doc = load_yaml(WORKFLOWS / "update-trending.yml")
    assert doc["jobs"]["update-trending"]["timeout-minutes"] > 0


def test_update_workflow_uses_current_action_versions():
    """只禁止回退到旧大版本，不锁死当前版本 —— 否则 dependabot 升版必红。"""
    doc = load_yaml(WORKFLOWS / "update-trending.yml")
    uses = [step.get("uses", "") for step in steps_of(doc)]

    checkout = next(u for u in uses if u.startswith("actions/checkout@"))
    setup = next(u for u in uses if u.startswith("actions/setup-python@"))
    assert action_major(checkout) >= 4, uses
    assert action_major(setup) >= 5, uses


def test_ci_workflow_uses_current_action_versions():
    doc = load_yaml(WORKFLOWS / "ci.yml")
    uses = [step.get("uses", "") for step in doc["jobs"]["verify"]["steps"]]

    checkout = next(u for u in uses if u.startswith("actions/checkout@"))
    setup = next(u for u in uses if u.startswith("actions/setup-python@"))
    assert action_major(checkout) >= 4, uses
    assert action_major(setup) >= 5, uses


def test_update_workflow_caches_pip():
    doc = load_yaml(WORKFLOWS / "update-trending.yml")
    setup = next(s for s in steps_of(doc) if s.get("uses", "").startswith("actions/setup-python@"))
    assert setup["with"]["cache"] == "pip"


def test_update_workflow_ignores_own_data_commits():
    """机器人提交 data/** 后不能反过来再触发自己。"""
    doc = load_yaml(WORKFLOWS / "update-trending.yml")
    paths_ignore = triggers(doc)["push"]["paths-ignore"]
    assert "data/**" in paths_ignore
    assert ".dsh/**" in paths_ignore


def test_update_workflow_passes_token_to_scraper():
    doc = load_yaml(WORKFLOWS / "update-trending.yml")
    run_step = next(s for s in steps_of(doc) if s.get("run", "").strip() == "python scraper.py")
    assert "GITHUB_TOKEN" in run_step["env"]


def test_update_workflow_commits_only_data_directory():
    doc = load_yaml(WORKFLOWS / "update-trending.yml")
    script_lines = []
    for step in steps_of(doc):
        for line in step.get("run", "").splitlines():
            if not line.strip().startswith("#"):  # 注释里提到旧写法不算违规
                script_lines.append(line)
    script = "\n".join(script_lines)
    assert "git add data/" in script
    assert "git add -A" not in script


# --- 代码 CI workflow ------------------------------------------------------

def test_ci_workflow_runs_verify():
    doc = load_yaml(WORKFLOWS / "ci.yml")
    script = "\n".join(s.get("run", "") for s in doc["jobs"]["verify"]["steps"])
    assert "./scripts/verify.sh" in script


def test_ci_workflow_triggers_on_pull_request():
    doc = load_yaml(WORKFLOWS / "ci.yml")
    assert "pull_request" in triggers(doc)


def test_ci_workflow_has_timeout_and_concurrency():
    doc = load_yaml(WORKFLOWS / "ci.yml")
    assert doc["jobs"]["verify"]["timeout-minutes"] > 0
    assert doc["concurrency"]["cancel-in-progress"] is True


# --- Dependabot 与依赖上界 -------------------------------------------------

def test_dependabot_covers_pip_and_actions():
    doc = load_yaml(REPO_ROOT / ".github" / "dependabot.yml")
    ecosystems = {u["package-ecosystem"] for u in doc["updates"]}
    assert {"pip", "github-actions"} <= ecosystems


@pytest.mark.parametrize("req_file", ["requirements.txt", "requirements-dev.txt"])
def test_requirements_have_upper_bounds(req_file):
    """只有下界的话，某天上游出大版本会直接把 CI 打挂。"""
    for line in (REPO_ROOT / req_file).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-r "):
            continue
        assert "<" in line, f"{req_file}: `{line}` 缺少上界约束"


def test_requirements_dev_pulls_runtime_deps():
    text = (REPO_ROOT / "requirements-dev.txt").read_text(encoding="utf-8")
    assert "-r requirements.txt" in text
    assert "PyYAML" in text
