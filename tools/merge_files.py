#!/usr/bin/env python3
"""把同一天的多个数据文件合并成一份（一次性维护脚本，已归档到 tools/）。

历史背景：早期用「每 6 小时 + 文件名时间戳」跑，同一天会攒下多份文件。
本脚本把它们按标题合并，默认「后面的文件覆盖前面的同名段落」。

用法:
    python tools/merge_files.py 20250424            # 演练（默认不写盘、不删除）
    python tools/merge_files.py 20250424 --apply    # 真合并，原文件移到 backups/

修复的历史 bug：旧实现用 `re.split(r'##\\s+', content)` 切分段落，
`### Python` 也会被命中（'##' 后面正好是空白），于是切出一个孤立的 '#'
并把 ### 降级成 ##，合并结果标题层级直接坏掉。现在按行解析标题层级。
"""

import argparse
import os
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gitops import add_commit_push  # noqa: E402  (需先补 sys.path)
from tools.common import DATA_DIR, backup_files  # noqa: E402

HEADING_PATTERN = re.compile(r'^(#{2,3})\s+(.+?)\s*$', re.MULTILINE)


def anchor(title):
    """GitHub 风格锚点：小写、空格转连字符。"""
    return title.strip().lower().replace(' ', '-')


def split_sections(content):
    """按 ##/### 标题切分，返回 [{level, title, body}, ...]。"""
    matches = list(HEADING_PATTERN.finditer(content))
    sections = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(content)
        sections.append({
            "level": len(match.group(1)),
            "title": match.group(2).strip(),
            "body": content[start:end].strip('\n'),
        })
    return sections


def find_files_for_date(date, data_dir=DATA_DIR):
    """YYYYMMDD 对应的全部文件（含 _HHMM / _HHMMSS / _NN 后缀）。

    返回顺序即「新旧顺序」，后面的覆盖前面的。规则：带时间戳的按时间戳升序，
    不带后缀的基础文件视为最新（与 tools/cleanup.py 保留基础文件一致）。
    """
    year_month = Path(data_dir) / date[:4] / date[4:6]
    if not year_month.exists():
        return []

    pattern = re.compile(rf'^{date}(?:_(\d{{2,6}}))?\.md$')

    def sort_key(path):
        match = pattern.match(path.name)
        suffix = match.group(1) if match else None
        # 无后缀（基础文件）排最后 = 最新
        return (1 if suffix is None else 0, suffix or '', path.name)

    return sorted((path for path in year_month.iterdir() if pattern.match(path.name)), key=sort_key)


def merge_sections(files):
    """按标题合并：后出现的同名段落覆盖先出现的（保持原语义）。"""
    merged = {}
    order = []
    for path in files:
        for section in split_sections(path.read_text(encoding="utf-8")):
            key = (section["level"], section["title"])
            if key not in merged:
                order.append(key)
            merged[key] = section
    return [merged[key] for key in order]


TOC_TITLE = '目录'


def render_merged(date, sections):
    """重建整份文档：标题 + 目录 + 各段落（保留原层级）。

    `目录` 本身是脚手架：老文件里它也是一段，如果照抄就会渲染出第二个目录
    （真实案例：坏脚本写的 20250424.md 里有两个 `## 目录`）。
    这里按内容段落重新生成目录，不再照抄。
    """
    content_sections = [
        section for section in sections
        if not (section["level"] == 2 and section["title"] == TOC_TITLE)
    ]

    lines = [
        f"# GitHub 热门榜单 {date} ({datetime.now().strftime('%H:%M:%S')})",
        "",
        f"## {TOC_TITLE}",
        "",
    ]

    top_level = [s for s in content_sections if s["level"] == 2]
    for section in top_level:
        lines.append(f"- [{section['title']}](#{anchor(section['title'])})")
        for subsection in content_sections:
            if subsection["level"] == 3 and _belongs_under(content_sections, subsection, section):
                lines.append(f"  - [{subsection['title']}](#{anchor(subsection['title'])})")
    lines.append("")

    for section in content_sections:
        lines.append(f"{'#' * section['level']} {section['title']}")
        lines.append("")
        if section["body"]:
            lines.append(section["body"])
            lines.append("")

    return "\n".join(lines).rstrip("\n") + "\n"


def _belongs_under(sections, subsection, parent):
    """### 段落归属它前面最近的那个 ## 段落。"""
    subsection_index = sections.index(subsection)
    for section in reversed(sections[:subsection_index]):
        if section["level"] == 2:
            return section is parent
    return False


def merge_date(date, data_dir=DATA_DIR, apply=False, force=False):
    """合并指定日期；返回合并后的路径。apply=False 时只汇报。

    force=True 时即使只有 1 个文件也原地重排 —— 用于修历史上被坏脚本写坏的文件
    （典型症状：同一份文档里出现两个 `## 目录`）。
    """
    files = find_files_for_date(date, data_dir)
    if not files:
        print(f"{date}: 没有找到数据文件")
        return None
    if len(files) < 2 and not force:
        print(f"{date}: 只有 {len(files)} 个文件，无需合并（要原地重排请加 --force）")
        return None

    sections = merge_sections(files)
    content = render_merged(date, sections)
    base_file = Path(data_dir) / date[:4] / date[4:6] / f"{date}.md"

    action = "重排" if len(files) == 1 else "合并"
    print(f"{date}: {len(files)} 个文件 → {base_file.name}（{action}为 {len(sections)} 个段落）")
    for path in files:
        print(f"  - {path.name}")

    if not apply:
        print(f"  [dry-run] 未写盘；加 --apply 才真正{action}（原文件会移入 backups/）")
        return base_file

    # 先把内容写到临时文件，再移走原文件，最后落位：中途失败不会两边都没有
    staging = base_file.with_suffix('.md.merging')
    staging.write_text(content, encoding="utf-8")
    backup_files(files, date)
    os.replace(staging, base_file)
    print(f"  [apply] 已{action}为 {base_file.name}，原文件备份到 backups/{date}/")
    return base_file


def main(argv=None):
    parser = argparse.ArgumentParser(description="合并同一天的多份数据文件（默认 dry-run）")
    parser.add_argument("date", nargs="?", default=datetime.now().strftime('%Y%m%d'),
                        help="日期 YYYYMMDD，默认今天")
    parser.add_argument("--apply", action="store_true", help="真正写盘并备份原文件")
    parser.add_argument("--force", action="store_true",
                        help="即使只有 1 个文件也原地重排（修历史坏格式，如重复的目录段落）")
    parser.add_argument("--commit", action="store_true", help="合并后提交（需在 git 仓库内）")
    args = parser.parse_args(argv)

    merged = merge_date(args.date, apply=args.apply, force=args.force)
    if merged and args.commit and args.apply:
        add_commit_push(str(merged), f"chore(data): 合并 {args.date} 的多份数据文件")
    return 0


if __name__ == '__main__':
    sys.exit(main())
