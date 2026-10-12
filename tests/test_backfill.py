"""TASK-001 历史 JSON 回填测试。

回填是「一次性但可重复」的操作，重点锁三件事：
schema 与抓取产物一致、幂等（默认跳过已存在）、真实 577 个 md 全都能解析。
"""

import json
from pathlib import Path

import pytest

from scripts import backfill_export as backfill

REPO_ROOT = Path(__file__).resolve().parents[1]

LEGACY_MD = """# GitHub 热门榜单 20250424 (12:25:00)

## 目录

- [每日趋势榜](#每日趋势榜)
- [Python](#python)

## 每日 Star 最多的仓库

| 序号 | 名称 | 描述 | 语言 | Stars | Forks |
| --- | --- | --- | --- | --- | --- |
| 1 | [a/b](https://github.com/a/b) | 描述里有 \\| 管道符 | Python | 1,234 | 56 |
| 2 | [x\\[y\\]/z](https://github.com/xz) | second | Go | 12.3k | 7 |

## 人工智能方向热榜

*暂无数据*

### Python

| 序号 | 名称 | 描述 | 语言 | Stars | Forks |
| --- | --- | --- | --- | --- | --- |
| 1 | [c/d](https://github.com/c/d) | desc | Go | N/A | 7 |
"""


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return tmp_path


def write_day(root: Path, name="20250424_1225.md", content=LEGACY_MD):
    directory = root / "data" / "2025" / "04"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_text(content, encoding="utf-8")
    return path


# --- 解析正确性 -----------------------------------------------------------

def test_parse_day_schema_matches_scraper_export(sandbox):
    path = write_day(sandbox)
    payload = backfill.parse_day(path)

    assert set(payload) == {"date", "generated_at", "source", "sections"}
    assert payload["date"] == "20250424"
    assert payload["generated_at"] is None          # 回填没有真实抓取时刻
    assert payload["source"] == "backfill:markdown"
    assert [s["id"] for s in payload["sections"]] == ["most-starred", "python"]
    for section in payload["sections"]:
        assert set(section) == {"id", "title", "repos"}
        for repo in section["repos"]:
            assert set(repo) == {"rank", "name", "url", "description", "language", "stars", "forks"}


def test_escaped_pipe_in_description_is_restored(sandbox):
    payload = backfill.parse_day(write_day(sandbox))
    first = payload["sections"][0]["repos"][0]
    assert first["description"] == "描述里有 | 管道符"


def test_escaped_brackets_in_repo_name_are_restored(sandbox):
    payload = backfill.parse_day(write_day(sandbox))
    assert payload["sections"][0]["repos"][1]["name"] == "x[y]/z"


def test_counts_are_integers_or_null(sandbox):
    payload = backfill.parse_day(write_day(sandbox))
    star_repos = payload["sections"][0]["repos"]
    assert star_repos[0]["stars"] == 1234
    assert star_repos[0]["forks"] == 56
    assert star_repos[1]["stars"] == 12300       # 12.3k
    assert payload["sections"][1]["repos"][0]["stars"] is None   # N/A


def test_ranks_are_preserved(sandbox):
    payload = backfill.parse_day(write_day(sandbox))
    assert [r["rank"] for r in payload["sections"][0]["repos"]] == [1, 2]


def test_empty_sections_are_dropped(sandbox):
    """「人工智能方向热榜」在历史文件里是 `*暂无数据*`，不该进 schema。"""
    payload = backfill.parse_day(write_day(sandbox))
    assert "ai" not in [s["id"] for s in payload["sections"]]


# --- 幂等与 dry-run -------------------------------------------------------

def test_dry_run_writes_nothing(sandbox):
    path = write_day(sandbox)
    stats = backfill.backfill(data_dir=sandbox / "data")

    assert stats["written"] == 1          # 统计「待写」，但不落盘
    assert stats["total"] == 1
    assert not path.with_suffix(".json").exists()


def test_cli_dry_run_reports_mode(sandbox, monkeypatch, capsys):
    write_day(sandbox)
    monkeypatch.setattr(backfill, "DATA_DIR", sandbox / "data")
    assert backfill.main([]) == 0
    assert "dry-run" in capsys.readouterr().out


def test_apply_writes_and_skips_existing(sandbox):
    path = write_day(sandbox)
    target = path.with_suffix(".json")

    first = backfill.backfill(data_dir=sandbox / "data", apply=True, rebuild_index=False)
    assert first["written"] == 1 and target.exists()
    assert json.loads(target.read_text(encoding="utf-8"))["date"] == "20250424"

    second = backfill.backfill(data_dir=sandbox / "data", apply=True, rebuild_index=False)
    assert second["written"] == 0 and second["skipped"] == 1


def test_force_rewrites_existing(sandbox):
    path = write_day(sandbox)
    target = path.with_suffix(".json")
    target.write_text('{"stale": true}', encoding="utf-8")

    stats = backfill.backfill(data_dir=sandbox / "data", apply=True, force=True, rebuild_index=False)
    assert stats["written"] == 1
    assert json.loads(target.read_text(encoding="utf-8"))["source"] == "backfill:markdown"


def test_index_is_rebuilt_after_apply(sandbox):
    write_day(sandbox)
    backfill.backfill(data_dir=sandbox / "data", apply=True)
    index = json.loads((sandbox / "data" / "index.json").read_text(encoding="utf-8"))
    assert index["total_files"] == 1
    assert index["files"][0]["json"] is not None


# --- 真实数据 -------------------------------------------------------------

def test_real_history_coverage_is_stable():
    """历史覆盖率快照 —— 解析器一旦坏掉，这里的数字会立刻塌下来。

    真实现状（2026-10-12 实测，577 个文件）：
      * `trending` / `python` 99.8%：只有 20250901 缺两段，
        那是旧版「先建文件再逐段追加」半成品写入留下的疤（SPRINT-01 TASK-003 已修根因）
      * `most-starred` 95.7% / `most-forked` 95.0%：
        25~29 天是当年 GitHub API 失败，段内真的写着「暂无数据」
    """
    files = backfill.find_data_files()
    assert len(files) > 500

    ids_by_file = {p.name: {s["id"] for s in backfill.parse_day(p)["sections"]} for p in files}

    def missing(section):
        return sorted(name for name, ids in ids_by_file.items() if section not in ids)

    assert all(ids_by_file.values()), "有文件解析出了空段落集合"
    assert missing("trending") == ["20250901.md"]
    assert missing("python") == ["20250901.md"]
    assert len(missing("most-starred")) <= 30, missing("most-starred")
    assert len(missing("most-forked")) <= 30, missing("most-forked")


def test_real_newest_day_matches_scraper_export_shape():
    """抓取器产出的 JSON 与回填产出的 JSON，段落 id 必须一致。"""
    newest_md = sorted((REPO_ROOT / "data" / "2026" / "10").glob("2026101*.md"))[-1]
    scraper_json = newest_md.with_suffix(".json")
    if not scraper_json.exists():
        pytest.skip("该日没有抓取器产出的 JSON 可对照")

    from_scraper = json.loads(scraper_json.read_text(encoding="utf-8"))
    from_backfill = backfill.parse_day(newest_md)

    assert [s["id"] for s in from_backfill["sections"]] == [s["id"] for s in from_scraper["sections"]]
    for left, right in zip(from_backfill["sections"], from_scraper["sections"]):
        assert len(left["repos"]) == len(right["repos"])
        assert left["repos"][0]["name"] == right["repos"][0]["name"]
