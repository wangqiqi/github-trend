"""TASK-008 机器可读产物测试。

两条主线：抓取时同时产出 per-day JSON；build_index.py 能把历史数据汇总成索引。
"""

import json
import re
from pathlib import Path

import pytest

import scraper
from scripts import build_index as indexer

REPO_ROOT = Path(__file__).resolve().parents[1]

BASE_REPO = {
    "title": "a/b",
    "url": "https://github.com/a/b",
    "description": "a | b 的描述",
    "language": "Python",
    "stars": "150148",
    "forks": "8067",
}


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return tmp_path


def patch_sources(monkeypatch, repos=None):
    data = repos if repos is not None else [dict(BASE_REPO)]
    monkeypatch.setattr(scraper, "scrape_most_starred", lambda session=None: [dict(r) for r in data])
    monkeypatch.setattr(scraper, "scrape_most_forked", lambda session=None: [dict(r) for r in data])
    monkeypatch.setattr(scraper, "scrape_trending", lambda language=None, session=None: [dict(r) for r in data])


# --- per-day JSON ---------------------------------------------------------

def test_scrape_all_writes_json_next_to_markdown(sandbox, monkeypatch):
    patch_sources(monkeypatch)
    filename, date = scraper.scrape_all()

    markdown_path = Path(filename)
    json_path = markdown_path.with_suffix(".json")
    assert markdown_path.exists()
    assert json_path.exists()

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["date"] == date
    assert payload["source"] == "scraper.py"


def test_json_keeps_chinese_readable(sandbox, monkeypatch):
    patch_sources(monkeypatch)
    filename, _ = scraper.scrape_all()
    raw = Path(filename).with_suffix(".json").read_text(encoding="utf-8")
    assert "每日 Star 最多的仓库" in raw  # ensure_ascii=False


def test_json_sections_and_ranks(sandbox, monkeypatch):
    patch_sources(monkeypatch, repos=[dict(BASE_REPO), dict(BASE_REPO, title="c/d")])
    filename, _ = scraper.scrape_all()
    payload = json.loads(Path(filename).with_suffix(".json").read_text(encoding="utf-8"))

    assert [s["id"] for s in payload["sections"]] == ["most-starred", "most-forked", "trending", "python"]
    for section in payload["sections"]:
        assert [r["rank"] for r in section["repos"]] == [1, 2]


def test_json_counts_are_integers(sandbox, monkeypatch):
    patch_sources(monkeypatch)
    filename, _ = scraper.scrape_all()
    payload = json.loads(Path(filename).with_suffix(".json").read_text(encoding="utf-8"))
    repo = payload["sections"][0]["repos"][0]
    assert repo["stars"] == 150148
    assert repo["forks"] == 8067
    assert isinstance(repo["stars"], int)


def test_json_description_is_raw_while_markdown_escapes(sandbox, monkeypatch):
    patch_sources(monkeypatch, repos=[dict(BASE_REPO, description="a | b")])
    filename, _ = scraper.scrape_all()

    payload = json.loads(Path(filename).with_suffix(".json").read_text(encoding="utf-8"))
    assert payload["sections"][0]["repos"][0]["description"] == "a | b"  # JSON 保留原文

    markdown = Path(filename).read_text(encoding="utf-8")
    assert "a \\| b" in markdown  # md 里按表格规则转义


def test_json_description_is_not_truncated(sandbox, monkeypatch):
    long_text = "word " * 60
    patch_sources(monkeypatch, repos=[dict(BASE_REPO, description=long_text)])
    filename, _ = scraper.scrape_all()

    payload = json.loads(Path(filename).with_suffix(".json").read_text(encoding="utf-8"))
    assert payload["sections"][0]["repos"][0]["description"] == long_text

    markdown = Path(filename).read_text(encoding="utf-8")
    assert long_text.strip() not in markdown  # md 只放截断版
    assert "..." in markdown


def test_unknown_counts_become_null(sandbox, monkeypatch):
    patch_sources(monkeypatch, repos=[dict(BASE_REPO, stars="", forks="N/A")])
    filename, _ = scraper.scrape_all()
    repo = json.loads(Path(filename).with_suffix(".json").read_text(encoding="utf-8"))["sections"][0]["repos"][0]
    assert repo["stars"] is None
    assert repo["forks"] is None


def test_generated_at_is_iso8601_utc(sandbox, monkeypatch):
    patch_sources(monkeypatch)
    filename, _ = scraper.scrape_all()
    payload = json.loads(Path(filename).with_suffix(".json").read_text(encoding="utf-8"))
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", payload["generated_at"])


def test_failed_scrape_writes_no_json(sandbox, monkeypatch):
    patch_sources(monkeypatch, repos=[])
    with pytest.raises(scraper.ScrapeError):
        scraper.scrape_all()
    assert list(sandbox.rglob("*.json")) == []


# --- build_index ----------------------------------------------------------

def make_tree(root: Path):
    (root / "data" / "2025" / "03").mkdir(parents=True)
    (root / "data" / "2026" / "10").mkdir(parents=True)
    (root / "data" / "2025" / "03" / "20250313_124300.md").write_text("a", encoding="utf-8")
    (root / "data" / "2025" / "03" / "20250314.md").write_text("b", encoding="utf-8")
    (root / "data" / "2026" / "10" / "20261011.md").write_text("c", encoding="utf-8")
    (root / "data" / "2026" / "10" / "20261011.json").write_text("{}", encoding="utf-8")
    (root / "data" / "README.md").write_text("不是每日数据", encoding="utf-8")  # 不该进索引


def test_build_index_collects_daily_files(tmp_path):
    make_tree(tmp_path)
    index = indexer.build_index(tmp_path / "data")

    assert index["total_files"] == 3
    assert index["total_days"] == 3
    assert index["first_date"] == "20250313"
    assert index["last_date"] == "20261011"


def test_build_index_links_sibling_json(tmp_path):
    make_tree(tmp_path)
    entries = {e["date"]: e for e in indexer.build_index(tmp_path / "data")["files"]}
    assert entries["20261011"]["json"] is not None
    assert entries["20250314"]["json"] is None


def test_build_index_is_deterministic(tmp_path):
    """索引里不放生成时刻：数据不变则字节一致，CI 不会产生无意义 diff。"""
    make_tree(tmp_path)
    data_dir = tmp_path / "data"
    first = indexer.write_index(indexer.build_index(data_dir), data_dir).read_bytes()
    second = indexer.write_index(indexer.build_index(data_dir), data_dir).read_bytes()
    assert first == second


def test_write_index_leaves_no_temp_file(tmp_path):
    make_tree(tmp_path)
    data_dir = tmp_path / "data"
    indexer.write_index(indexer.build_index(data_dir), data_dir)
    assert not list(data_dir.glob("*.tmp"))


def test_build_index_handles_empty_tree(tmp_path):
    (tmp_path / "data").mkdir()
    index = indexer.build_index(tmp_path / "data")
    assert index["total_files"] == 0
    assert index["first_date"] is None


# --- 真实仓库 -------------------------------------------------------------

def test_real_repo_index_covers_all_history():
    """真实 data/ 目录必须全部被索引覆盖（Done when 的硬指标）。"""
    index = json.loads((REPO_ROOT / "data" / "index.json").read_text(encoding="utf-8"))
    markdown_files = [p for p in (REPO_ROOT / "data").rglob("*.md")]
    assert index["total_files"] == len(markdown_files)
    assert index["total_days"] > 500
    assert index["first_date"] == "20250313"


def test_real_index_is_up_to_date():
    """索引必须与当前数据树一致，改了数据忘了重建就会被这条拦下。"""
    on_disk = json.loads((REPO_ROOT / "data" / "index.json").read_text(encoding="utf-8"))
    assert indexer.build_index() == on_disk


def test_ci_rebuilds_index_after_scraping():
    """抓取 workflow 必须重建索引，否则 index.json 会悄悄过期。"""
    import yaml

    workflow = yaml.safe_load((REPO_ROOT / ".github" / "workflows" / "update-trending.yml").read_text(encoding="utf-8"))
    script = "\n".join(step.get("run", "") for step in workflow["jobs"]["update-trending"]["steps"])
    assert "scripts/build_index.py" in script
    assert "scripts/build_trends.py" in script
