"""TASK-007 段落集合测试。

「人工智能方向热榜」从建仓起 577/579 个文件都是空的，用户决定直接移除。
这里锁住新产物的段落集合，并确认 README 不再承诺不存在的段落。
"""

import re
from pathlib import Path

import pytest

import scraper

REPO_ROOT = Path(__file__).resolve().parents[1]

REPOS = [{
    "title": "a/b", "url": "https://github.com/a/b",
    "description": "demo", "stars": "1", "forks": "2", "language": "Python",
}]

EXPECTED_SECTIONS = ("每日 Star 最多的仓库", "每日 Fork 最多的仓库", "每日趋势榜", "Python")


@pytest.fixture
def rendered(tmp_path, monkeypatch):
    """在临时目录里渲染一份完整文档，返回其内容。"""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(scraper, "scrape_most_starred", lambda session=None: [dict(REPOS[0])])
    monkeypatch.setattr(scraper, "scrape_most_forked", lambda session=None: [dict(REPOS[0])])
    monkeypatch.setattr(scraper, "scrape_trending", lambda language=None, session=None: [dict(REPOS[0])])

    filename, _ = scraper.scrape_all()
    return Path(filename).read_text(encoding="utf-8")


def heading_anchors(text):
    """把 `## 标题` 转成 GitHub 风格锚点。"""
    anchors = []
    for line in text.splitlines():
        match = re.match(r"^(#{2,3})\s+(.+)$", line)
        if match:
            anchors.append(match.group(2).strip().lower().replace(" ", "-"))
    return anchors


def toc_links(text):
    return re.findall(r"^- \[.+?\]\(#(.+?)\)$", text, flags=re.MULTILINE)


# --- 新产物段落集合 -------------------------------------------------------

def test_ai_section_is_gone(rendered):
    assert "人工智能方向热榜" not in rendered


def test_expected_sections_present(rendered):
    for title in EXPECTED_SECTIONS:
        assert f"## {title}" in rendered, title


def test_no_subsections_left(rendered):
    """Python 原先是挂在 AI 段下的 ###，现在应是一级段落。"""
    assert "### " not in rendered
    assert "## Python" in rendered


def test_exactly_four_top_level_sections(rendered):
    headings = re.findall(r"^## (.+)$", rendered, flags=re.MULTILINE)
    assert headings == ["目录", *EXPECTED_SECTIONS]


def test_toc_matches_rendered_sections(rendered):
    """目录里的锚点必须都能在正文里找到 —— 旧目录就指向了不存在的段落。"""
    anchors = set(heading_anchors(rendered))
    for link in toc_links(rendered):
        assert link in anchors, f"目录锚点 #{link} 没有对应段落"


def test_python_section_has_its_own_table(rendered):
    python_part = rendered.split("## Python", 1)[1]
    assert "| 序号 | 名称 | 描述 | 语言 | Stars | Forks |" in python_part
    assert "| [a/b](" in python_part


# --- README 不再承诺不存在的段落 -----------------------------------------

@pytest.mark.parametrize("readme", ["README.md", "README_EN.md"])
def test_readme_does_not_advertise_removed_sections(readme):
    text = (REPO_ROOT / readme).read_text(encoding="utf-8")
    for phrase in ("人工智能方向热榜", "人工智能方向的热榜", "AI-related", "Deep Learning", "Machine Learning"):
        assert phrase not in text, f"{readme} 仍在承诺已移除的 {phrase}"


@pytest.mark.parametrize("readme", ["README.md", "README_EN.md"])
def test_readme_still_documents_real_sections(readme):
    text = (REPO_ROOT / readme).read_text(encoding="utf-8")
    assert "Python" in text
    assert "趋势榜" in text or "Trending" in text
