#!/usr/bin/env python3
"""清理同一天的多份数据文件，只保留一份（一次性维护脚本，已归档到 tools/）。

历史背景：旧实现把月份硬编码成 `2025/03` 与 `2025/04`，跑过一次就再没生效，
所以 20250424 那天一直留着 4 个文件。现在扫描整个 data/，也可用 --month 限定。

用法:
    python tools/cleanup.py                              # 演练：只报告要删什么
    python tools/cleanup.py --apply                      # 执行（多余文件先移入 backups/）
    python tools/cleanup.py --month 2025/04 --apply
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.common import (  # noqa: E402  (需先补 sys.path)
    DATA_DIR,
    DATE_FILE_PATTERN,
    NOON_FILE_PATTERN,
    backup_files,
    with_siblings,
)


def group_by_date(month_dir):
    """{date: [files...]}，只认每日数据文件，忽略 index.json 之类。"""
    groups = {}
    for path in sorted(Path(month_dir).glob("*.md")):
        match = DATE_FILE_PATTERN.match(path.name)
        if match:
            groups.setdefault(match.group(1), []).append(path)
    return groups


def pick_keeper(date, files):
    """选保留哪一份：基础文件 > 中午 12 点那份 > 字典序最后的（最新）。"""
    base = [path for path in files if path.name == f"{date}.md"]
    if base:
        return base[0], "base"

    noon = sorted(path for path in files if NOON_FILE_PATTERN.match(path.name))
    if noon:
        return noon[-1], "noon"

    return sorted(files)[-1], "latest"


def plan_cleanup(data_dir=DATA_DIR, month=None):
    """返回 [(date, keeper, reason, [多余文件...]), ...]，只做规划不落盘。"""
    root = Path(data_dir)
    month_dirs = sorted(path for path in root.glob("*/*") if path.is_dir())
    if month:
        month_dirs = [path for path in month_dirs if f"{path.parent.name}/{path.name}" == month]

    plan = []
    for month_dir in month_dirs:
        for date, files in sorted(group_by_date(month_dir).items()):
            if len(files) < 2:
                continue
            keeper, reason = pick_keeper(date, files)
            extras = [path for path in files if path != keeper]
            plan.append((date, keeper, reason, extras))
    return plan


def run_cleanup(data_dir=DATA_DIR, month=None, apply=False):
    plan = plan_cleanup(data_dir, month)
    if not plan:
        print("没有发现同一天的多份数据文件，无需清理")
        return 0

    removed = 0
    for date, keeper, reason, extras in plan:
        print(f"{date}: 保留 {keeper.name}（依据 {reason}），多余 {len(extras)} 份")
        for path in extras:
            print(f"  - {path.name}")
        if apply:
            # 同名 .json 快照跟着一起走，否则会留下无主的孤儿文件
            backup_files(with_siblings(extras), date)
            removed += len(extras)

    if not apply:
        print(f"[dry-run] 共 {len(plan)} 天、{sum(len(p[3]) for p in plan)} 个文件待清理；加 --apply 才执行（会先备份到 backups/）")
    else:
        print(f"[apply] 已清理 {len(plan)} 天、{removed} 个文件（原文件在 backups/<date>/）")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="清理同日多份数据文件（默认 dry-run）")
    parser.add_argument("--month", help="限定月份，格式 YYYY/MM，默认扫描整个 data/")
    parser.add_argument("--apply", action="store_true", help="真正删除（先备份到 backups/）")
    args = parser.parse_args(argv)
    return run_cleanup(month=args.month, apply=args.apply)


if __name__ == '__main__':
    sys.exit(main())
