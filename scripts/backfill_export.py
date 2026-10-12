#!/usr/bin/env python3
"""从历史 Markdown 表格反向生成 per-day JSON（一次性回填 + 可重复运行）。

背景：per-day JSON 是 2026-10-12（SPRINT-01 TASK-008）才加进抓取流程的，
在此之前 577 天的数据只有 Markdown。趋势分析与第三方消费需要结构化输入，
所以这里把 md 表格反向解析成与 `scraper.build_export` **同一套 schema**。

已知保真度限制：md 里的描述是抓取时按表格宽度截断并转义过的
（`truncate_description`），因此回填出的 `description` 是截断版，
其余字段（name / url / language / stars / forks / rank）为原值。

用法:
    python scripts/backfill_export.py                 # 演练：只统计，不写盘
    python scripts/backfill_export.py --apply         # 真写盘（跳过已存在的 JSON）
    python scripts/backfill_export.py --apply --force # 连已存在的一起重写
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from scraper import count_or_none  # noqa: E402  (复用同一套数字归一语义)

DATA_DIR = REPO_ROOT / "data"
# YYYYMMDD.md · YYYYMMDD_1234.md · YYYYMMDD_120000.md · YYYYMMDD_01.md
DATE_FILE_PATTERN = re.compile(r'^(\d{8})(?:_\d{2,6})?\.md$')
HEADING_PATTERN = re.compile(r'^(#{2,3})\s+(.+?)\s*$', re.MULTILINE)
LINK_PATTERN = re.compile(r'^\[(.+)\]\((.+)\)$')
PIPE_PLACEHOLDER = "\x00"

# 标题 → schema 里的段落 id（含历史版本的 AI 子段落）
SECTION_IDS = {
    "每日 Star 最多的仓库": "most-starred",
    "每日 Fork 最多的仓库": "most-forked",
    "每日趋势榜": "trending",
    "Python": "python",
    "Deep Learning": "deep-learning",
    "Machine Learning": "machine-learning",
    "人工智能方向热榜": "ai",
}


def split_sections(text):
    """按 ##/### 标题切分，返回 [{level, title, body}, ...]。"""
    matches = list(HEADING_PATTERN.finditer(text))
    sections = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections.append({
            "level": len(match.group(1)),
            "title": match.group(2).strip(),
            "body": text[start:end],
        })
    return sections


def split_row(line):
    """按 `|` 切表格行，但尊重转义后的 `\\|`（描述里可能真的有管道符）。"""
    cleaned = line.replace('\\|', PIPE_PLACEHOLDER)
    cells = [cell.strip() for cell in cleaned.strip().strip('|').split('|')]
    return [cell.replace(PIPE_PLACEHOLDER, '|') for cell in cells]


def unescape_link_text(text):
    return text.replace('\\[', '[').replace('\\]', ']')


def parse_repos(body):
    """解析段落里的表格行；非数据行（表头/分隔/暂无数据）自动跳过。"""
    repos = []
    for line in body.splitlines():
        line = line.strip()
        if not line.startswith('|'):
            continue
        cells = split_row(line)
        if len(cells) != 6:
            continue
        rank, name_cell, description, language, stars, forks = cells
        if not rank.isdigit():
            continue  # 表头 / `| --- |` 分隔行
        link = LINK_PATTERN.match(name_cell)
        if not link:
            continue
        repos.append({
            "rank": int(rank),
            "name": unescape_link_text(link.group(1)),
            "url": link.group(2),
            "description": description,
            "language": language,
            "stars": count_or_none(stars),
            "forks": count_or_none(forks),
        })
    return repos


def parse_day(path):
    """单个 md → per-day JSON 结构（与 scraper.build_export 同 schema）。"""
    text = Path(path).read_text(encoding="utf-8")
    match = DATE_FILE_PATTERN.match(Path(path).name)
    date = match.group(1) if match else Path(path).stem

    sections = []
    for section in split_sections(text):
        title = section["title"]
        if title == "目录":
            continue
        section_id = SECTION_IDS.get(title)
        if section_id is None:
            continue
        repos = parse_repos(section["body"])
        if not repos:
            continue  # 「*暂无数据*」之类的空段落不入 schema
        sections.append({"id": section_id, "title": title, "repos": repos})

    return {
        "date": date,
        "generated_at": None,           # 回填产物没有真实抓取时刻，宁可为 null
        "source": "backfill:markdown",
        "sections": sections,
    }


def find_data_files(data_dir=DATA_DIR):
    files = []
    for path in sorted(Path(data_dir).rglob("*.md")):
        if DATE_FILE_PATTERN.match(path.name):
            files.append(path)
    return files


def backfill(data_dir=DATA_DIR, apply=False, force=False, rebuild_index=True):
    """返回统计字典；apply=False 时只统计不写盘。"""
    files = find_data_files(data_dir)
    stats = {"total": len(files), "written": 0, "skipped": 0, "empty": 0, "failed": 0}

    for path in files:
        target = path.with_suffix(".json")
        if target.exists() and not force:
            stats["skipped"] += 1
            continue

        try:
            payload = parse_day(path)
        except Exception as exc:  # 单个坏文件不该毁掉整次回填
            stats["failed"] += 1
            print(f"  解析失败 {path.name}: {exc}")
            continue

        if not payload["sections"]:
            stats["empty"] += 1
            continue

        if apply:
            tmp = target.with_name(target.name + ".tmp")
            tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            os.replace(tmp, target)
        stats["written"] += 1

    if apply and rebuild_index and stats["written"]:
        from scripts import build_index  # 延迟导入，避免无谓依赖
        index = build_index.build_index(data_dir)
        build_index.write_index(index, data_dir)
        stats["index_files"] = index["total_files"]

    return stats


def main(argv=None):
    parser = argparse.ArgumentParser(description="从历史 Markdown 回填 per-day JSON（默认 dry-run）")
    parser.add_argument("--apply", action="store_true", help="真正写盘")
    parser.add_argument("--force", action="store_true", help="已存在的 JSON 也重写")
    args = parser.parse_args(argv)

    if not DATA_DIR.exists():
        print(f"FAIL: 数据目录不存在: {DATA_DIR}", file=sys.stderr)
        return 1

    stats = backfill(apply=args.apply, force=args.force)
    mode = "apply" if args.apply else "dry-run"
    print(f"[{mode}] 扫描 {stats['total']} 个 md · 待写 {stats['written']} · 已存在跳过 {stats['skipped']} "
          f"· 无有效段落 {stats['empty']} · 解析失败 {stats['failed']}")
    if args.apply:
        print(f"索引已重建：{stats.get('index_files', '未变更')} 个文件")
    else:
        print("演练模式未写盘；加 --apply 执行（已存在的 JSON 默认跳过，--force 可重写）")
    return 1 if stats["failed"] else 0


if __name__ == '__main__':
    sys.exit(main())
