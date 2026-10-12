"""TASK-009 维护脚本测试。

重点回归：merge 的 ### 分割 bug（旧实现会把 `### Python` 切成孤立的 '#'），
以及 cleanup 只认得 2025/03-04 两个硬编码月份的问题。
"""

import re
from pathlib import Path

import pytest

from tools import cleanup as cleanup_tool
from tools import common
from tools import merge_files as merge_tool

FILE_A = """# GitHub 热门榜单 20250424 (07:51:00)

## 目录

- [每日趋势榜](#每日趋势榜)

## 每日趋势榜

| 1 | old-repo |

## 人工智能方向热榜

*暂无数据*

### Python

| 1 | old-python |
"""

FILE_B = """# GitHub 热门榜单 20250424 (12:25:00)

## 目录

- [每日趋势榜](#每日趋势榜)

## 每日趋势榜

| 1 | new-repo |

## 人工智能方向热榜

*暂无数据*

### Python

| 1 | new-python |
"""


@pytest.fixture
def backups(tmp_path, monkeypatch):
    """把备份目录指到临时目录，别污染真实仓库。"""
    target = tmp_path / "backups"
    monkeypatch.setattr(common, "BACKUP_DIR", target)
    return target


def make_month(tmp_path, date="20250424", names=("20250424_0751.md", "20250424.md")):
    """建一个日期目录；_0751 那份是旧内容，基础文件是新内容。"""
    directory = tmp_path / "data" / date[:4] / date[4:6]
    directory.mkdir(parents=True)
    for index, name in enumerate(names):
        content = FILE_A if name.endswith("0751.md") else FILE_B
        (directory / name).write_text(content, encoding="utf-8")
    return directory


# --- 标题层级解析（历史 bug） --------------------------------------------

def test_split_sections_keeps_heading_levels():
    sections = merge_tool.split_sections(FILE_A)
    assert [(s["level"], s["title"]) for s in sections] == [
        (2, "目录"),
        (2, "每日趋势榜"),
        (2, "人工智能方向热榜"),
        (3, "Python"),
    ]


def test_split_sections_never_yields_stray_hash():
    """旧实现会在 `### Python` 处切出一个孤立的 '#' 标题。"""
    for section in merge_tool.split_sections(FILE_A):
        assert not section["title"].startswith("#")


def test_split_sections_keeps_bodies():
    sections = {s["title"]: s for s in merge_tool.split_sections(FILE_A)}
    assert "| 1 | old-repo |" in sections["每日趋势榜"]["body"]
    assert "| 1 | old-python |" in sections["Python"]["body"]


def test_render_merged_preserves_levels():
    merged = merge_tool.render_merged("20250424", merge_tool.split_sections(FILE_A))
    assert "### Python" in merged
    assert "#### " not in merged
    assert not re.search(r'^#\s*$', merged, flags=re.MULTILINE), "出现了孤立的 # 标题"


def test_render_merged_builds_toc_with_subsection():
    merged = merge_tool.render_merged("20250424", merge_tool.split_sections(FILE_A))
    assert "- [每日趋势榜](#每日趋势榜)" in merged
    assert "  - [Python](#python)" in merged


def test_render_merged_regenerates_toc_without_self_reference():
    """目录是脚手架：不能照抄老文件里的目录段，否则会渲染出第二个 `## 目录`。"""
    merged = merge_tool.render_merged("20250424", merge_tool.split_sections(FILE_A))
    assert merged.count("## 目录") == 1
    assert "- [目录](#目录)" not in merged


# --- 合并行为 -------------------------------------------------------------

def test_find_files_for_date_matches_all_suffix_styles(tmp_path):
    directory = tmp_path / "data" / "2025" / "04"
    directory.mkdir(parents=True)
    for name in ("20250424.md", "20250424_0751.md", "20250424_120000.md", "20250424_01.md", "20250425.md"):
        (directory / name).write_text("x", encoding="utf-8")

    found = [path.name for path in merge_tool.find_files_for_date("20250424", tmp_path / "data")]
    # 基础文件排最后 = 最新，会覆盖前面的时间戳文件
    assert found == ["20250424_01.md", "20250424_0751.md", "20250424_120000.md", "20250424.md"]


def test_merge_sections_latest_wins(tmp_path):
    first = tmp_path / "a.md"
    second = tmp_path / "b.md"
    first.write_text(FILE_A, encoding="utf-8")
    second.write_text(FILE_B, encoding="utf-8")

    merged = {s["title"]: s for s in merge_tool.merge_sections([first, second])}
    assert "new-repo" in merged["每日趋势榜"]["body"]
    assert "new-python" in merged["Python"]["body"]


def test_merge_dry_run_changes_nothing(tmp_path, backups):
    directory = make_month(tmp_path)
    before = sorted(path.name for path in directory.iterdir())

    merge_tool.merge_date("20250424", data_dir=tmp_path / "data", apply=False)

    assert sorted(path.name for path in directory.iterdir()) == before
    assert not backups.exists()


def test_merge_apply_writes_one_file_and_backs_up_originals(tmp_path, backups):
    directory = make_month(tmp_path)

    merged = merge_tool.merge_date("20250424", data_dir=tmp_path / "data", apply=True)

    assert sorted(path.name for path in directory.iterdir()) == ["20250424.md"]
    content = (directory / "20250424.md").read_text(encoding="utf-8")
    assert "new-repo" in content  # 后一份文件生效
    assert "### Python" in content  # 层级没被压平

    backed_up = sorted(path.name for path in (backups / "20250424").iterdir())
    assert backed_up == ["20250424.md", "20250424_0751.md"]
    assert merged == directory / "20250424.md"


def test_merge_single_file_is_noop(tmp_path, backups):
    directory = make_month(tmp_path, names=("20250424.md",))
    assert merge_tool.merge_date("20250424", data_dir=tmp_path / "data", apply=True) is None
    assert [path.name for path in directory.iterdir()] == ["20250424.md"]


DUP_TOC_FILE = """# GitHub 热门榜单 20250424 (12:25:00)

## 目录

- [每日趋势榜](#每日趋势榜)

## 每日趋势榜

| 1 | repo |

## 目录

- [Python](#python)

### Python

| 1 | py |
"""


def test_force_rerenders_single_file_and_collapses_duplicate_toc(tmp_path, backups):
    """真实案例：坏 merge 脚本写出的文件里有两个 `## 目录`。"""
    directory = tmp_path / "data" / "2025" / "04"
    directory.mkdir(parents=True)
    base = directory / "20250424.md"
    base.write_text(DUP_TOC_FILE, encoding="utf-8")

    merged = merge_tool.merge_date("20250424", data_dir=tmp_path / "data", apply=True, force=True)

    content = base.read_text(encoding="utf-8")
    assert merged == base
    assert content.count("## 目录") == 1, "重复的目录没有收敛"
    assert "### Python" in content, "层级被压平了"
    assert "| 1 | repo |" in content and "| 1 | py |" in content, "数据行丢了"
    assert [path.name for path in (backups / "20250424").iterdir()] == ["20250424.md"]


def test_force_without_apply_changes_nothing(tmp_path, backups):
    directory = tmp_path / "data" / "2025" / "04"
    directory.mkdir(parents=True)
    base = directory / "20250424.md"
    base.write_text(DUP_TOC_FILE, encoding="utf-8")

    merge_tool.merge_date("20250424", data_dir=tmp_path / "data", apply=False, force=True)

    assert base.read_text(encoding="utf-8") == DUP_TOC_FILE
    assert not backups.exists()


def test_force_rerender_backs_up_stale_sibling_json(tmp_path, backups):
    """md 被重排后，同日的 .json 快照就过期了，不能留在数据目录里。"""
    directory = tmp_path / "data" / "2025" / "04"
    directory.mkdir(parents=True)
    base = directory / "20250424.md"
    base.write_text(DUP_TOC_FILE, encoding="utf-8")
    (directory / "20250424.json").write_text("{}", encoding="utf-8")

    merge_tool.merge_date("20250424", data_dir=tmp_path / "data", apply=True, force=True)

    assert [path.name for path in directory.iterdir()] == ["20250424.md"]
    assert sorted(path.name for path in (backups / "20250424").iterdir()) == [
        "20250424.json", "20250424.md",
    ]


# --- 清理脚本 -------------------------------------------------------------

def test_group_by_date_ignores_non_daily_files(tmp_path):
    directory = tmp_path / "data" / "2025" / "04"
    directory.mkdir(parents=True)
    (directory / "20250424.md").write_text("x", encoding="utf-8")
    (directory / "20250424_0751.md").write_text("x", encoding="utf-8")
    (directory / "README.md").write_text("x", encoding="utf-8")
    (directory / "index.json").write_text("{}", encoding="utf-8")

    groups = cleanup_tool.group_by_date(directory)
    assert list(groups) == ["20250424"]
    assert len(groups["20250424"]) == 2


def test_pick_keeper_prefers_base_file():
    files = [Path("20250424_0751.md"), Path("20250424.md")]
    keeper, reason = cleanup_tool.pick_keeper("20250424", files)
    assert keeper.name == "20250424.md"
    assert reason == "base"


def test_pick_keeper_prefers_noon_when_no_base():
    files = [Path("20250424_0751.md"), Path("20250424_1225.md")]
    keeper, reason = cleanup_tool.pick_keeper("20250424", files)
    assert keeper.name == "20250424_1225.md"
    assert reason == "noon"


def test_pick_keeper_falls_back_to_latest():
    files = [Path("20250424_0751.md"), Path("20250424_0754.md")]
    keeper, reason = cleanup_tool.pick_keeper("20250424", files)
    assert keeper.name == "20250424_0754.md"
    assert reason == "latest"


def test_plan_cleanup_works_on_any_month(tmp_path):
    """旧脚本把月份写死成 2025/03 与 2025/04，之后的新月份永远清不到。"""
    directory = tmp_path / "data" / "2026" / "10"
    directory.mkdir(parents=True)
    (directory / "20261012.md").write_text("x", encoding="utf-8")
    (directory / "20261012_01.md").write_text("x", encoding="utf-8")

    plan = cleanup_tool.plan_cleanup(tmp_path / "data")
    assert len(plan) == 1
    date, keeper, reason, extras = plan[0]
    assert date == "20261012"
    assert keeper.name == "20261012.md"
    assert [path.name for path in extras] == ["20261012_01.md"]


def test_plan_cleanup_month_filter(tmp_path):
    for month in ("2025/04", "2026/10"):
        directory = tmp_path / "data" / month
        directory.mkdir(parents=True)
        date = month.replace("/", "")
        (directory / f"{date}01.md").write_text("x", encoding="utf-8")
        (directory / f"{date}01_01.md").write_text("x", encoding="utf-8")

    plan = cleanup_tool.plan_cleanup(tmp_path / "data", month="2025/04")
    assert [entry[0] for entry in plan] == ["20250401"]


def test_cleanup_dry_run_keeps_everything(tmp_path, backups, capsys):
    directory = tmp_path / "data" / "2025" / "04"
    directory.mkdir(parents=True)
    (directory / "20250424.md").write_text("keep", encoding="utf-8")
    (directory / "20250424_0751.md").write_text("extra", encoding="utf-8")

    cleanup_tool.run_cleanup(data_dir=tmp_path / "data", apply=False)

    assert len(list(directory.iterdir())) == 2
    assert "dry-run" in capsys.readouterr().out


def test_cleanup_apply_moves_extras_to_backup(tmp_path, backups):
    directory = tmp_path / "data" / "2025" / "04"
    directory.mkdir(parents=True)
    (directory / "20250424.md").write_text("keep", encoding="utf-8")
    (directory / "20250424_0751.md").write_text("extra", encoding="utf-8")

    cleanup_tool.run_cleanup(data_dir=tmp_path / "data", apply=True)

    assert [path.name for path in directory.iterdir()] == ["20250424.md"]
    assert (directory / "20250424.md").read_text(encoding="utf-8") == "keep"
    assert [path.name for path in (backups / "20250424").iterdir()] == ["20250424_0751.md"]


def test_cleanup_moves_sibling_json_too(tmp_path, backups):
    """只搬 .md 会留下无主的 _01.json —— 索引里没人引用，纯垃圾。"""
    directory = tmp_path / "data" / "2025" / "04"
    directory.mkdir(parents=True)
    (directory / "20250424.md").write_text("keep", encoding="utf-8")
    (directory / "20250424_0751.md").write_text("extra", encoding="utf-8")
    (directory / "20250424_0751.json").write_text("{}", encoding="utf-8")

    cleanup_tool.run_cleanup(data_dir=tmp_path / "data", apply=True)

    assert [path.name for path in directory.iterdir()] == ["20250424.md"]
    assert sorted(path.name for path in (backups / "20250424").iterdir()) == [
        "20250424_0751.json", "20250424_0751.md",
    ]


def test_real_repo_plan_is_reportable():
    """真实数据上必须能跑出计划（测试不执行删除）。"""
    plan = cleanup_tool.plan_cleanup()
    assert isinstance(plan, list)
    for date, keeper, reason, extras in plan:
        assert len(extras) >= 1
        assert keeper not in extras
