"""TASK-001 冒烟测试：仓库骨架、入口模块可导入、verify 脚本就位。

这些用例不访问网络，也不写盘 —— 只保证「基础盘」在。
"""

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_repo_skeleton_present():
    """核心文件必须存在，避免 verify 在残缺检出上给出假绿。"""
    for rel in ("scraper.py", "requirements.txt", "scripts/verify.sh", "README.md"):
        assert (REPO_ROOT / rel).exists(), f"缺少 {rel}"


def test_verify_script_is_executable():
    """verify.sh 必须可直接执行（acceptance 就是 ./scripts/verify.sh）。"""
    verify = REPO_ROOT / "scripts" / "verify.sh"
    assert verify.stat().st_mode & 0o111, "scripts/verify.sh 没有执行位"


def test_scraper_entrypoints_importable():
    """scraper 的公开入口存在且可调用（pyquery 未装时跳过，不误报）。"""
    pytest.importorskip("pyquery", reason="未安装运行时依赖，先 pip install -r requirements.txt")
    import scraper

    for name in ("scrape_trending", "scrape_most_starred", "scrape_most_forked", "scrape_all", "job"):
        assert callable(getattr(scraper, name)), f"scraper.{name} 不可调用"


def test_data_tree_is_readable():
    """历史数据目录必须可读且非空（索引类 TASK 依赖它）。"""
    files = sorted((REPO_ROOT / "data").rglob("*.md"))
    assert files, "data/ 下没有任何 md 数据文件"


def test_latest_data_file_has_expected_sections():
    """抽查最新一份数据：三个常驻段落必须在，Python 段落按世代二选一。

    TASK-007 之前的历史文件把 Python 放在「人工智能方向热榜」下的 `### Python`；
    新产物是顶层 `## Python` 且不再有 AI 段。两种世代都得能过 ——
    早期版本硬断言 AI 段存在，CI 机器人一生成新格式文件就把自己测红了。
    """
    files = sorted((REPO_ROOT / "data").rglob("*.md"))
    latest = files[-1].read_text(encoding="utf-8")
    for section in ("## 每日 Star 最多的仓库", "## 每日 Fork 最多的仓库", "## 每日趋势榜"):
        assert section in latest, f"最新数据缺少段落 {section}"
    assert "## Python" in latest or "### Python" in latest, "最新数据缺少 Python 段落"


def test_every_data_file_has_core_sections():
    """全量校验：每个历史文件都不能缺核心段落（比只看最新一份更结实）。"""
    files = sorted((REPO_ROOT / "data").rglob("*.md"))
    assert len(files) > 500, f"数据文件数量异常: {len(files)}"

    missing = []
    for path in files:
        text = path.read_text(encoding="utf-8")
        for section in ("每日 Star 最多的仓库", "每日 Fork 最多的仓库", "每日趋势榜"):
            if section not in text:
                missing.append(f"{path.name}: {section}")
    assert missing == []
