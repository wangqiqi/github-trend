#!/usr/bin/env python3
"""把全部 per-day JSON 汇总成趋势榜 `data/trends.json`。

服务的三个榜单：
  * **gain**       Star 增速榜（首末 Star 差 / 跨度天）
  * **evergreen**  常青榜（上榜天数最多）
  * **newcomers**  新晋榜（最近窗口内首次出现）

设计约束：**可复现**。产物不含任何时间戳，排序全部确定（同分按名称），
口径阈值写成模块常量并随产物输出，因此同样的数据每次运行字节一致。

用法:
    python scripts/build_trends.py            # 生成 data/trends.json
    python scripts/build_trends.py --dry-run  # 只打印摘要
"""

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data"
TRENDS_PATH = DATA_DIR / "trends.json"

DATE_FILE_PATTERN = re.compile(r'^(\d{8})(?:_\d{2,6})?\.json$')

# --- 口径常量（改这里就是改口径，产物里会带上）-----------------------------
MIN_APPEARANCES = 3          # 至少上榜这么多天才进增速/常青榜
NEWCOMER_WINDOW_DAYS = 30    # 「新晋」的时间窗口
LEADER_LIMIT = 20            # 每个榜取前多少名
DATE_FORMAT = "%Y%m%d"


def load_days(data_dir=DATA_DIR):
    """读取全部 per-day JSON，按日期升序返回 [(date, payload), ...]。"""
    days = []
    for path in sorted(Path(data_dir).rglob("*.json")):
        match = DATE_FILE_PATTERN.match(path.name)
        if not match:
            continue  # index.json / trends.json 之类
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"  跳过无法解析的文件 {path.name}: {exc}", file=sys.stderr)
            continue
        days.append((match.group(1), payload))
    days.sort(key=lambda item: item[0])
    return days


def _star_value(repo):
    stars = repo.get("stars")
    return stars if isinstance(stars, int) else None


def build_series(days):
    """[{date, sections}] → {name: {url, language, points: {date: stars}, best_rank}}。

    同一天同一仓库可能同时出现在「趋势榜」和「Python」两个段落，Star 数未必相同
    （页面抓的与 API 给的来源不同），这里取当天最大值，保证确定性。
    """
    series = {}
    for date, payload in days:
        for section in payload.get("sections", []):
            for repo in section.get("repos", []):
                name = repo.get("name")
                if not name:
                    continue
                info = series.setdefault(name, {
                    "url": repo.get("url") or "",
                    "language": repo.get("language") or "N/A",
                    "points": {},
                    "best_rank": None,
                })
                if repo.get("url"):
                    info["url"] = repo["url"]
                if repo.get("language") and repo["language"] != "N/A":
                    info["language"] = repo["language"]

                stars = _star_value(repo)
                if stars is not None:
                    known = info["points"].get(date)
                    info["points"][date] = stars if known is None else max(known, stars)
                elif date not in info["points"]:
                    info["points"][date] = None  # 上榜了但 Star 未知

                rank = repo.get("rank")
                if isinstance(rank, int):
                    info["best_rank"] = rank if info["best_rank"] is None else min(info["best_rank"], rank)
    return series


def summarize(name, info):
    """单个仓库的汇总记录；Star 缺失时相关字段为 None，不编造数字。"""
    dated = sorted(info["points"].items())
    known = [(date, stars) for date, stars in dated if stars is not None]
    first_date, last_date = dated[0][0], dated[-1][0]

    first_stars = known[0][1] if known else None
    last_stars = known[-1][1] if known else None
    gain = None
    gain_per_day = None
    if first_stars is not None and last_stars is not None:
        gain = last_stars - first_stars
        span = (datetime.strptime(known[-1][0], DATE_FORMAT) - datetime.strptime(known[0][0], DATE_FORMAT)).days
        gain_per_day = round(gain / span, 2) if span > 0 else None

    return {
        "name": name,
        "url": info["url"],
        "language": info["language"],
        "appearances": len(dated),
        "first_date": first_date,
        "last_date": last_date,
        "first_stars": first_stars,
        "last_stars": last_stars,
        "gain": gain,
        "gain_per_day": gain_per_day,
        "best_rank": info["best_rank"],
    }


def _days_between(left, right):
    return (datetime.strptime(right, DATE_FORMAT) - datetime.strptime(left, DATE_FORMAT)).days


def build_trends(data_dir=DATA_DIR):
    """生成趋势产物（纯函数：同样输入 → 同样输出，无时间戳）。"""
    days = load_days(data_dir)
    if not days:
        raise RuntimeError(f"{data_dir} 下没有可用的 per-day JSON")

    series = build_series(days)
    records = [summarize(name, info) for name, info in series.items()]
    first_date, last_date = days[0][0], days[-1][0]
    window_start = (datetime.strptime(last_date, DATE_FORMAT) - timedelta(days=NEWCOMER_WINDOW_DAYS)).strftime(DATE_FORMAT)

    eligible = [r for r in records if r["appearances"] >= MIN_APPEARANCES]
    gain_leaders = sorted(
        (r for r in eligible if r["gain"] is not None),
        key=lambda r: (-r["gain"], r["name"]),
    )[:LEADER_LIMIT]
    evergreen = sorted(eligible, key=lambda r: (-r["appearances"], r["name"]))[:LEADER_LIMIT]
    newcomers = sorted(
        (r for r in records if r["first_date"] >= window_start and r["last_stars"] is not None),
        key=lambda r: (-r["last_stars"], r["name"]),
    )[:LEADER_LIMIT]

    return {
        "generated_from": "data/**/*.json",
        "total_days": len(days),
        "first_date": first_date,
        "last_date": last_date,
        "repo_count": len(records),
        "thresholds": {
            "min_appearances": MIN_APPEARANCES,
            "newcomer_window_days": NEWCOMER_WINDOW_DAYS,
            "leader_limit": LEADER_LIMIT,
            "newcomer_window_start": window_start,
        },
        "leaders": {
            "gain": gain_leaders,
            "evergreen": evergreen,
            "newcomers": newcomers,
        },
    }


def write_trends(trends, path=TRENDS_PATH):
    """原子写盘。"""
    path = Path(path)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(trends, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    return path


def main(argv=None):
    parser = argparse.ArgumentParser(description="由 per-day JSON 生成趋势榜")
    parser.add_argument("--dry-run", action="store_true", help="只打印摘要，不写盘")
    args = parser.parse_args(argv)

    if not DATA_DIR.exists():
        print(f"FAIL: 数据目录不存在: {DATA_DIR}", file=sys.stderr)
        return 1

    try:
        trends = build_trends()
    except RuntimeError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    leaders = trends["leaders"]
    print(f"{trends['total_days']} 天（{trends['first_date']} ~ {trends['last_date']}）· "
          f"仓库 {trends['repo_count']} 个 · 增速榜 {len(leaders['gain'])} / 常青榜 {len(leaders['evergreen'])} "
          f"/ 新晋榜 {len(leaders['newcomers'])}")
    for record in leaders["gain"][:5]:
        print(f"  {record['name']:40s} +{record['gain']:>8} stars / {record['appearances']} 天")

    if args.dry_run:
        print("[dry-run] 未写盘")
        return 0

    path = write_trends(trends)
    print(f"已写入 {path.relative_to(REPO_ROOT)}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
