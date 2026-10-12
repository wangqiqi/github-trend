#!/usr/bin/env python3
"""生成 data/index.json：把散落的每日 md 汇总成一份可程序消费的索引。

设计取向：索引是数据树的**纯函数** —— 不含生成时刻，所以数据没变时重复运行
产出的字节完全一致，不会给 CI 制造无意义的 diff。
"""

import json
import os
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data"
INDEX_FILENAME = "index.json"

# YYYYMMDD.md、YYYYMMDD_120000.md（秒级）、YYYYMMDD_1234.md（早期分钟级）、
# YYYYMMDD_01.md（避让序号）—— 历史上三种后缀都出现过，都得算进去
DATE_PATTERN = re.compile(r'^(\d{8})(?:_\d{2,6})?\.md$')


def display_path(path):
    """优先给仓库相对路径；临时目录之类给绝对路径。"""
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def collect_files(data_dir=DATA_DIR):
    """按日期收集每日数据文件（含同日多份），并标注是否有机器可读快照。"""
    entries = []
    for path in sorted(Path(data_dir).rglob("*.md")):
        match = DATE_PATTERN.match(path.name)
        if not match:
            continue
        sibling_json = path.with_suffix(".json")
        entries.append({
            "date": match.group(1),
            "markdown": display_path(path),
            "json": display_path(sibling_json) if sibling_json.exists() else None,
        })
    return entries


def build_index(data_dir=DATA_DIR):
    entries = collect_files(data_dir)
    dates = sorted({entry["date"] for entry in entries})
    return {
        "total_files": len(entries),
        "total_days": len(dates),
        "first_date": dates[0] if dates else None,
        "last_date": dates[-1] if dates else None,
        "files": entries,
    }


def write_index(index, data_dir=DATA_DIR):
    """原子写：tmp + os.replace，避免半截索引被提交。"""
    target = Path(data_dir) / INDEX_FILENAME
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(INDEX_FILENAME + ".tmp")
    tmp.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, target)
    return target


def main():
    if not Path(DATA_DIR).exists():
        print(f"FAIL: 数据目录不存在: {DATA_DIR}", file=sys.stderr)
        return 1

    index = build_index()
    if index["total_files"] == 0:
        print("FAIL: data/ 下没有找到任何每日数据文件", file=sys.stderr)
        return 1

    target = write_index(index)
    print(
        f"已写入 {display_path(target)}：{index['total_files']} 个文件 / "
        f"{index['total_days']} 天（{index['first_date']} ~ {index['last_date']}）"
    )
    return 0


if __name__ == '__main__':
    sys.exit(main())
