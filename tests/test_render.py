"""TASK-006 渲染统一测试。

三件事：数字格式统一、描述按词边界截断（且转义）、文件名避让不覆盖。
"""

import re
from pathlib import Path

import pytest

import scraper


# --- 数字归一 -------------------------------------------------------------

@pytest.mark.parametrize("raw,expected", [
    ("1,234", "1234"),
    ("150,148", "150148"),
    ("150148", "150148"),
    (" 1 000 ", "1000"),
    ("12.3k", "12300"),
    ("1.5M", "1500000"),
    ("0", "0"),
    (0, "0"),
    (12, "12"),
])
def test_normalize_count_parses_common_forms(raw, expected):
    assert scraper.normalize_count(raw) == expected


@pytest.mark.parametrize("raw", ["", "   ", "N/A", None, "abc", "-5", "1,2,3,4"])
def test_normalize_count_returns_empty_for_unparseable(raw):
    assert scraper.normalize_count(raw) == ""


def test_trending_stars_are_normalized():
    html = b"""
    <html><body><article class="Box-row">
      <h2><a href="/owner/repo">owner / repo</a></h2>
      <p>desc</p>
      <div class="f6">
        <a href="/owner/repo/stargazers">150,148</a>
        <a href="/owner/repo/forks">8,067</a>
        <span itemprop="programmingLanguage">Python</span>
      </div>
    </article></body></html>
    """

    class FakeSession:
        calls = []

        def get(self, url, headers=None, timeout=None):
            return type("R", (), {"status_code": 200, "content": html, "headers": {},
                                  "raise_for_status": lambda self: None})()

    repos = scraper.scrape_trending(session=FakeSession())
    assert repos[0]["stars"] == "150148"
    assert repos[0]["forks"] == "8067"


def test_api_counts_are_normalized():
    payload = {"items": [{
        "full_name": "a/b", "html_url": "https://github.com/a/b", "description": "d",
        "stargazers_count": 150148, "forks_count": 8067, "language": "Python",
    }]}

    class FakeSession:
        def get(self, url, headers=None, timeout=None):
            return type("R", (), {"status_code": 200, "headers": {},
                                  "raise_for_status": lambda self: None,
                                  "json": lambda self: payload})()

    repos = scraper.scrape_most_starred(session=FakeSession())
    assert repos[0]["stars"] == "150148"
    assert repos[0]["forks"] == "8067"


# --- 描述截断与转义 -------------------------------------------------------

def test_short_description_untouched():
    assert scraper.truncate_description("short text") == "short text"


def test_pipes_are_escaped():
    assert scraper.truncate_description("a | b") == "a \\| b"


def test_newlines_collapse_to_spaces():
    assert scraper.truncate_description("line1\nline2") == "line1 line2"


def test_long_description_cuts_on_word_boundary():
    text = "word " * 40
    result = scraper.truncate_description(text.strip(), limit=100)
    assert len(result) <= 100
    assert result.endswith("...")
    # 截断点前面必须是完整的词，不是半个
    assert not result[:-3].endswith("wor")


def test_long_single_token_still_bounded():
    result = scraper.truncate_description("x" * 500, limit=100)
    assert len(result) <= 100
    assert result.endswith("...")


def test_description_without_spaces_is_not_widened():
    assert len(scraper.truncate_description("a" * 99)) == 99


def test_link_text_brackets_escaped():
    assert scraper.escape_link_text("a[b]c") == "a\\[b\\]c"


def test_render_section_row_shape_is_stable():
    repos = [{
        "title": "a/b", "url": "https://github.com/a/b",
        "description": "d | e", "language": "Python", "stars": "1234", "forks": "56",
    }]
    rows = [line for line in scraper.render_section("T", repos).splitlines() if line.startswith("| ")]
    assert len(rows) == 3  # 表头 + 分隔行 + 1 条数据
    for row in rows:
        # 转义后的 \| 属于单元格内容，只数真正的分隔符
        separators = len(re.findall(r"(?<!\\)\|", row))
        assert separators == 7, row


def test_rendered_counts_are_all_digits():
    repos = [
        {"title": "a/b", "url": "u", "description": "d", "language": "Python", "stars": "150148", "forks": "8067"},
        {"title": "c/d", "url": "u", "description": "d", "language": "Go", "stars": "12", "forks": ""},
    ]
    body = scraper.render_section("T", repos)
    data_rows = [l for l in body.splitlines() if re.match(r"\| \d+ \|", l)]
    for row in data_rows:
        cells = [c.strip() for c in row.strip("|").split("|")]
        assert re.fullmatch(r"\d*", cells[4]), cells
        assert re.fullmatch(r"\d*", cells[5]), cells


# --- 文件名避让 -----------------------------------------------------------

def test_get_file_path_timestamp_has_seconds(sandbox_dir):
    import os
    os.chdir(sandbox_dir)
    filename, date = scraper.get_file_path(is_timestamp=True)
    assert re.search(r"\d{8}_\d{6}\.md$", filename), filename


def test_check_file_exists_returns_same_path_when_free(sandbox_dir):
    target = sandbox_dir / "data" / "2026" / "10" / "20261012.md"
    assert scraper.check_file_exists(str(target)) == str(target)


def test_check_file_exists_never_overwrites(sandbox_dir):
    directory = sandbox_dir / "data" / "2026" / "10"
    directory.mkdir(parents=True)
    base = directory / "20261012.md"
    base.write_text("原始数据", encoding="utf-8")

    first = scraper.check_file_exists(str(base))
    assert first != str(base)
    assert Path(first).name == "20261012_01.md"

    Path(first).write_text("第二次", encoding="utf-8")
    second = scraper.check_file_exists(str(base))
    assert second.endswith("20261012_02.md")

    # 原有内容必须还在
    assert base.read_text(encoding="utf-8") == "原始数据"


@pytest.fixture
def sandbox_dir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return tmp_path
