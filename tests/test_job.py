"""TASK-003 失败语义与原子写盘测试。

核心断言：抓不全就不落盘；落盘必须原子；CLI 失败必须给非零退出码。
"""

from pathlib import Path

import pytest
import requests

import scraper

REPOS = [{
    "title": "a/b",
    "url": "https://github.com/a/b",
    "description": "demo",
    "stars": "1",
    "forks": "2",
    "language": "Python",
}]


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    """把工作目录挪到临时目录，避免测试污染真实 data/。"""
    monkeypatch.chdir(tmp_path)
    return tmp_path


def patch_sources(monkeypatch, star=None, fork=None, trending=None, python=None):
    """按需替换四个抓取源；不传（None）则返回正常数据。"""
    def pick(value):
        return list(REPOS) if value is None else value

    monkeypatch.setattr(scraper, "scrape_most_starred", lambda session=None: pick(star))
    monkeypatch.setattr(scraper, "scrape_most_forked", lambda session=None: pick(fork))

    def fake_trending(language=None, session=None):
        return pick(python) if language == "python" else pick(trending)

    monkeypatch.setattr(scraper, "scrape_trending", fake_trending)


def md_files(root: Path):
    return list(root.rglob("*.md"))


def tmp_files(root: Path):
    return list(root.rglob(".tmp-*"))


# --- 成功路径 -------------------------------------------------------------

def test_scrape_all_writes_complete_document(sandbox, monkeypatch):
    patch_sources(monkeypatch)
    filename, date = scraper.scrape_all()

    path = Path(filename)
    assert path.exists()
    content = path.read_text(encoding="utf-8")
    for section in ("## 每日 Star 最多的仓库", "## 每日 Fork 最多的仓库", "## 每日趋势榜", "## Python"):
        assert section in content
    assert "人工智能方向热榜" not in content  # TASK-007：空段落已移除
    assert content.count("| [a/b](") == 4
    assert tmp_files(sandbox) == []


def test_job_returns_true_and_writes_file(sandbox, monkeypatch):
    patch_sources(monkeypatch)
    assert scraper.job() is True
    assert len(md_files(sandbox)) == 1


# --- 失败路径：不落盘 -----------------------------------------------------

def test_scrape_all_raises_when_star_is_empty(sandbox, monkeypatch):
    patch_sources(monkeypatch, star=[])
    with pytest.raises(scraper.ScrapeError):
        scraper.scrape_all()
    assert md_files(sandbox) == []
    assert tmp_files(sandbox) == []


def test_scrape_all_raises_when_trending_is_empty(sandbox, monkeypatch):
    patch_sources(monkeypatch, trending=[])
    with pytest.raises(scraper.ScrapeError):
        scraper.scrape_all()
    assert md_files(sandbox) == []


def test_scrape_all_raises_when_python_is_empty(sandbox, monkeypatch):
    patch_sources(monkeypatch, python=[])
    with pytest.raises(scraper.ScrapeError):
        scraper.scrape_all()
    assert md_files(sandbox) == []


def test_failure_after_earlier_success_writes_nothing(sandbox, monkeypatch):
    """前半段抓到了也不能先落盘 —— 这正是旧实现「先建文件」的坑。"""
    patch_sources(monkeypatch, fork=[])
    with pytest.raises(scraper.ScrapeError):
        scraper.scrape_all()
    assert md_files(sandbox) == []


def test_job_returns_false_on_scrape_error(sandbox, monkeypatch):
    patch_sources(monkeypatch, star=[])
    assert scraper.job() is False
    assert md_files(sandbox) == []


def test_job_returns_false_on_network_error(sandbox, monkeypatch):
    def boom(session=None):
        raise requests.exceptions.ConnectionError("network down")

    monkeypatch.setattr(scraper, "scrape_most_starred", boom)
    assert scraper.job() is False
    assert md_files(sandbox) == []


# --- CLI 退出码 -----------------------------------------------------------

def test_main_maps_success_to_zero(monkeypatch):
    monkeypatch.setattr(scraper, "job", lambda **kwargs: True)
    assert scraper.main() == 0


def test_main_maps_failure_to_nonzero(monkeypatch):
    """CI 就靠这个码判断成败：旧代码 __main__ 里没有 sys.exit。"""
    monkeypatch.setattr(scraper, "job", lambda **kwargs: False)
    assert scraper.main() == 1


# --- 原子写盘 -------------------------------------------------------------

def test_write_atomic_overwrites_and_leaves_no_temp(sandbox):
    target = sandbox / "data" / "x.md"
    scraper.write_atomic(str(target), "第一版")
    assert target.read_text(encoding="utf-8") == "第一版"

    scraper.write_atomic(str(target), "第二版")
    assert target.read_text(encoding="utf-8") == "第二版"
    assert tmp_files(sandbox) == []


def test_write_atomic_cleans_temp_on_failure(sandbox):
    target = sandbox / "data" / "x.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("原有内容", encoding="utf-8")

    with pytest.raises(TypeError):
        scraper.write_atomic(str(target), object())  # 故意传非字符串

    assert target.read_text(encoding="utf-8") == "原有内容"
    assert tmp_files(sandbox) == []
