"""TASK-010 文档对齐测试。

README 之所以会漂，是因为没人替它对账。这里让文档声明和真实配置互相锁死：
改了 workflow 的 cron 或换了远端仓库，README 不同步就会红。
"""

import re
import subprocess
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
README = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
README_EN = (REPO_ROOT / "README_EN.md").read_text(encoding="utf-8")
WORKFLOW = yaml.safe_load(
    (REPO_ROOT / ".github" / "workflows" / "update-trending.yml").read_text(encoding="utf-8")
)


def workflow_script():
    return "\n".join(step.get("run", "") for step in WORKFLOW["jobs"]["update-trending"]["steps"])


def workflow_cron():
    triggers = WORKFLOW.get("on", WORKFLOW.get(True))
    return triggers["schedule"][0]["cron"]


# --- 定时频率 -------------------------------------------------------------

def test_readme_schedule_matches_workflow_cron():
    assert workflow_cron() == "0 12 * * *"
    assert "12:00 UTC" in README
    assert "12:00 UTC" in README_EN


@pytest.mark.parametrize("text", [README, README_EN])
def test_readme_drops_stale_six_hourly_ci_claim(text):
    """旧 README 说 CI 每 6 小时跑（0/6/12/18 UTC），实际只有一天一次。"""
    assert "0:00, 6:00, 12:00, 18:00" not in text


def test_readme_distinguishes_local_scheduler_from_ci():
    """6 小时频率属于本地 scheduler.py，不属于 CI；两份说明都得分开讲。"""
    assert "scheduler.py" in README
    assert "scheduler.py" in README_EN


# --- 仓库地址 -------------------------------------------------------------

@pytest.mark.parametrize("text", [README, README_EN])
def test_readme_has_no_placeholder_url(text):
    assert "yourusername" not in text
    assert "github_treding" not in text


def test_readme_clone_url_matches_remote():
    result = subprocess.run(
        ["git", "config", "--get", "remote.origin.url"],
        cwd=REPO_ROOT, capture_output=True, text=True, check=False,
    )
    if result.returncode != 0 or not result.stdout.strip():
        pytest.skip("未配置 remote.origin.url")

    slug = re.sub(r"^.*github\.com[:/]", "", result.stdout.strip()).removesuffix(".git")
    assert slug in README, f"README 克隆地址与远端 {slug} 不一致"


# --- 产物与命令 -----------------------------------------------------------

@pytest.mark.parametrize("text", [README, README_EN])
def test_readme_documents_json_outputs(text):
    assert "index.json" in text
    assert ".json" in text


@pytest.mark.parametrize("text", [README, README_EN])
def test_readme_documents_verify_command(text):
    assert "./scripts/verify.sh" in text


@pytest.mark.parametrize("text", [README, README_EN])
def test_readme_documents_index_builder_and_tools(text):
    assert "scripts/build_index.py" in text
    assert "tools/cleanup.py" in text
    assert "tools/merge_files.py" in text


@pytest.mark.parametrize("text", [README, README_EN])
def test_readme_documents_token_usage(text):
    assert "GITHUB_TOKEN" in text


@pytest.mark.parametrize("text", [README, README_EN])
def test_readme_documents_dry_run_default(text):
    assert "--apply" in text
    assert "dry-run" in text.lower() or "default to dry-run" in text.lower()


@pytest.mark.parametrize("text", [README, README_EN])
def test_readme_mentions_ci_workflow(text):
    assert "ci.yml" in text


# --- 与 DOC 任务的互相印证 ------------------------------------------------

def test_readme_lists_the_four_real_sections():
    for title in ("每日 Star 最多的仓库", "每日 Fork 最多的仓库", "每日趋势榜", "Python"):
        assert title in README
    for title in ("Most Starred", "Most Forked", "Trending", "Python"):
        assert title in README_EN


# --- SPRINT-02：站点文档防漂移 --------------------------------------------

LIVE_URL = "https://znza.top/github-trend/"


@pytest.mark.parametrize("text", [README, README_EN])
def test_readme_points_to_live_site(text):
    assert LIVE_URL in text


@pytest.mark.parametrize("text", [README, README_EN])
def test_readme_documents_site_commands(text):
    assert "scripts/verify-all.sh" in text
    assert "scripts/verify-site.sh" in text
    assert "scripts/check-site.sh" in text
    assert "npm run docs:dev" in text


@pytest.mark.parametrize("text", [README, README_EN])
def test_readme_documents_deploy_workflow(text):
    assert "deploy-site.yml" in text
    assert "workflow_run" in text


def test_site_base_matches_published_url():
    """配置里的 base 必须和文档里的线上路径一致，否则挂上去资源全 404。"""
    config = (REPO_ROOT / "docs" / ".vitepress" / "config.mts").read_text(encoding="utf-8")
    assert f"base: '{LIVE_URL.split('znza.top')[1]}'" in config or "base: '/github-trend/'" in config
    assert LIVE_URL.rstrip("/").endswith("/github-trend")


def test_changelog_records_site_work():
    changelog = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "## [Unreleased]" in changelog
    assert "znza.top/github-trend" in changelog
    assert "trends.json" in changelog
