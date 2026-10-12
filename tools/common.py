# coding:utf-8
"""tools/ 下维护脚本的共用小工具。"""

import re
import shutil
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data"
BACKUP_DIR = REPO_ROOT / "backups"

# YYYYMMDD.md、YYYYMMDD_1234.md（早期分钟级）、YYYYMMDD_120000.md（秒级）、
# YYYYMMDD_01.md（避让序号）
DATE_FILE_PATTERN = re.compile(r'^(\d{8})(?:_\d{2,6})?\.md$')
# 历史上「保留中午 12 点那份」的策略留下的命名
NOON_FILE_PATTERN = re.compile(r'^\d{8}_12\d{2}(?:\d{2})?\.md$')


def backup_files(files, label):
    """把文件移入 backups/<label>/，而不是直接删除。"""
    target = BACKUP_DIR / label
    target.mkdir(parents=True, exist_ok=True)
    moved = []
    for path in files:
        destination = target / path.name
        shutil.move(str(path), str(destination))
        moved.append(destination)
    return moved


def with_siblings(paths, suffix=".json"):
    """把每日数据的同名快照（.json）一并纳入。

    否则清理/合并只搬走 .md，会留下一堆无主的 `YYYYMMDD_01.json`：
    索引里没人引用它们，删又删不掉，纯垃圾。
    """
    result = list(paths)
    for path in paths:
        sibling = path.with_suffix(suffix)
        if sibling.exists():
            result.append(sibling)
    return result
