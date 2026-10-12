"""TASK-002 趋势计算测试。

趋势产物要能进站点、还要能被人引用，所以重点锁两件事：**口径正确**且**可复现**。
"""

import json
from pathlib import Path

import pytest

from scripts import build_trends

REPO_ROOT = Path(__file__).resolve().parents[1]


def make_repo(name, stars, rank=1, language="Python"):
    return {
        "rank": rank,
        "name": name,
        "url": f"https://github.com/{name}",
        "description": f"{name} desc",
        "language": language,
        "stars": stars,
        "forks": 1,
    }


def write_day(root: Path, date: str, sections):
    """sections: [(section_id, [repo, ...]), ...]"""
    directory = root / "data" / date[:4] / date[4:6]
    directory.mkdir(parents=True, exist_ok=True)
    payload = {
        "date": date,
        "generated_at": None,
        "source": "test",
        "sections": [{"id": sid, "title": sid, "repos": repos} for sid, repos in sections],
    }
    (directory / f"{date}.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


@pytest.fixture
def sandbox(tmp_path):
    return tmp_path


def three_day_dataset(root: Path):
    write_day(root, "20260101", [("trending", [make_repo("a/a", 100), make_repo("b/b", 50, rank=2)])])
    write_day(root, "20260102", [("trending", [make_repo("a/a", 130), make_repo("b/b", 50, rank=2)])])
    write_day(root, "20260103", [("trending", [make_repo("a/a", 200), make_repo("c/c", 10, rank=2)])])


# --- 汇总口径 -------------------------------------------------------------

def test_build_series_takes_max_stars_for_same_day_duplicates(sandbox):
    write_day(sandbox, "20260101", [
        ("trending", [make_repo("a/a", 100)]),
        ("python", [make_repo("a/a", 120)]),   # 同一仓库、同一天、来源不同
    ])
    series = build_trends.build_series(build_trends.load_days(sandbox / "data"))
    assert series["a/a"]["points"] == {"20260101": 120}


def test_summarize_computes_gain_and_rate(sandbox):
    three_day_dataset(sandbox)
    series = build_trends.build_series(build_trends.load_days(sandbox / "data"))
    record = build_trends.summarize("a/a", series["a/a"])

    assert record["appearances"] == 3
    assert (record["first_date"], record["last_date"]) == ("20260101", "20260103")
    assert (record["first_stars"], record["last_stars"]) == (100, 200)
    assert record["gain"] == 100
    assert record["gain_per_day"] == 50.0
    assert record["best_rank"] == 1


def test_summarize_without_stars_reports_nulls(sandbox):
    write_day(sandbox, "20260101", [("trending", [make_repo("a/a", None)])])
    series = build_trends.build_series(build_trends.load_days(sandbox / "data"))
    record = build_trends.summarize("a/a", series["a/a"])

    assert record["appearances"] == 1
    assert record["first_stars"] is None and record["last_stars"] is None
    assert record["gain"] is None and record["gain_per_day"] is None


def test_thresholds_filters_thin_history(sandbox):
    """只上榜 1 天的仓库不该进增速榜/常青榜（口径 min_appearances=3）。"""
    three_day_dataset(sandbox)
    trends = build_trends.build_trends(sandbox / "data")

    for board in ("gain", "evergreen"):
        names = [r["name"] for r in trends["leaders"][board]]
        assert "c/c" not in names, board


def test_newcomers_only_recent_first_appearance(sandbox):
    """窗口是相对最后一天的 30 天，所以数据集必须跨过窗口才区分得出来。"""
    write_day(sandbox, "20260101", [("trending", [make_repo("old/old", 100)])])
    write_day(sandbox, "20260210", [("trending", [make_repo("old/old", 150)])])
    write_day(sandbox, "20260215", [("trending", [
        make_repo("old/old", 180),
        make_repo("new/new", 90, rank=2),
    ])])

    trends = build_trends.build_trends(sandbox / "data")
    newcomers = [r["name"] for r in trends["leaders"]["newcomers"]]

    assert "new/new" in newcomers          # 20260215 首次出现
    assert "old/old" not in newcomers      # 20260101 首次出现，早于窗口
    assert trends["thresholds"]["newcomer_window_start"] == "20260116"   # 20260215 - 30 天


def test_gain_board_sorted_descending(sandbox):
    three_day_dataset(sandbox)
    trends = build_trends.build_trends(sandbox / "data")
    gains = [r["gain"] for r in trends["leaders"]["gain"]]
    assert gains == sorted(gains, reverse=True)


def test_output_records_thresholds_and_span(sandbox):
    three_day_dataset(sandbox)
    trends = build_trends.build_trends(sandbox / "data")
    assert trends["total_days"] == 3
    assert (trends["first_date"], trends["last_date"]) == ("20260101", "20260103")
    assert trends["thresholds"]["min_appearances"] == build_trends.MIN_APPEARANCES
    assert trends["repo_count"] == 3


# --- 可复现与写盘 ---------------------------------------------------------

def test_build_is_deterministic(sandbox):
    three_day_dataset(sandbox)
    first = json.dumps(build_trends.build_trends(sandbox / "data"), ensure_ascii=False, sort_keys=True)
    second = json.dumps(build_trends.build_trends(sandbox / "data"), ensure_ascii=False, sort_keys=True)
    assert first == second


def test_write_trends_is_atomic(sandbox):
    three_day_dataset(sandbox)
    trends = build_trends.build_trends(sandbox / "data")
    path = build_trends.write_trends(trends, sandbox / "data" / "trends.json")

    assert json.loads(path.read_text(encoding="utf-8"))["total_days"] == 3
    assert list((sandbox / "data").glob("*.tmp")) == []


def test_missing_days_fail_loudly(sandbox):
    (sandbox / "data").mkdir()
    with pytest.raises(RuntimeError):
        build_trends.build_trends(sandbox / "data")


# --- 真实数据 -------------------------------------------------------------

def test_real_data_produces_all_three_boards():
    trends = build_trends.build_trends()
    assert trends["total_days"] > 500
    assert trends["repo_count"] > 300
    for board in ("gain", "evergreen", "newcomers"):
        assert len(trends["leaders"][board]) > 0, board
    for record in trends["leaders"]["gain"]:
        assert record["gain"] is not None
        assert record["appearances"] >= build_trends.MIN_APPEARANCES
        assert isinstance(record["gain"], int)


def test_committed_trends_file_is_up_to_date():
    path = REPO_ROOT / "data" / "trends.json"
    if not path.exists():
        pytest.skip("trends.json 尚未生成")
    assert json.loads(path.read_text(encoding="utf-8")) == build_trends.build_trends()
