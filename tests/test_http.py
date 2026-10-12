"""TASK-002 网络层测试：超时、重试退避、鉴权头、状态码语义。

全部用假 Session，绝不发真实请求，也不真的 sleep。
"""

import pytest
import requests

import scraper


class FakeResponse:
    def __init__(self, status_code=200, payload=None, headers=None, content=b"<html></html>"):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.headers = headers or {}
        self.content = content

    @property
    def text(self):
        return self.content.decode("utf-8", "replace")

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(f"HTTP {self.status_code}", response=self)


class FakeSession:
    """按顺序吐出预设响应/异常，并记录每次调用的参数。"""

    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = []

    def get(self, url, headers=None, timeout=None):
        self.calls.append({"url": url, "headers": headers, "timeout": timeout})
        if not self.outcomes:
            raise AssertionError("FakeSession 收到的请求次数超出预期")
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


@pytest.fixture(autouse=True)
def no_real_sleep(monkeypatch):
    """把退避 sleep 换成记录器，让重试用例瞬间跑完。"""
    slept = []
    monkeypatch.setattr(scraper, "_sleep", slept.append)
    return slept


# --- 超时 -----------------------------------------------------------------

def test_fetch_always_sets_timeout():
    session = FakeSession([FakeResponse()])
    scraper.fetch("https://api.github.com/x", session=session)
    assert session.calls[0]["timeout"] == scraper.DEFAULT_TIMEOUT
    assert session.calls[0]["timeout"] is not None


# --- 鉴权 -----------------------------------------------------------------

def test_headers_include_token_when_env_present(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "ghs_fake")
    headers = scraper.get_headers()
    assert headers["Authorization"] == "Bearer ghs_fake"


def test_headers_omit_authorization_without_token(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    assert "Authorization" not in scraper.get_headers()


def test_headers_never_claim_brotli():
    """声明 br 但没装 brotli 会拿到乱码，这里锁死这个回归。"""
    assert "br" not in scraper.get_headers()["Accept-Encoding"]


# --- 重试退避 -------------------------------------------------------------

def test_retries_rate_limit_then_succeeds(no_real_sleep):
    session = FakeSession([FakeResponse(429), FakeResponse(200, {"items": []})])
    response = scraper.fetch("https://api.github.com/x", session=session)
    assert response.status_code == 200
    assert len(session.calls) == 2
    assert len(no_real_sleep) == 1


def test_retries_server_error_then_succeeds(no_real_sleep):
    session = FakeSession([FakeResponse(503), FakeResponse(503), FakeResponse(200)])
    assert scraper.fetch("https://api.github.com/x", session=session).status_code == 200
    assert len(session.calls) == 3


def test_retries_connection_error_then_succeeds(no_real_sleep):
    session = FakeSession([requests.exceptions.ConnectionError("boom"), FakeResponse(200)])
    assert scraper.fetch("https://api.github.com/x", session=session).status_code == 200
    assert len(no_real_sleep) == 1


def test_gives_up_after_max_attempts(no_real_sleep):
    session = FakeSession([FakeResponse(500) for _ in range(scraper.MAX_ATTEMPTS)])
    with pytest.raises(requests.exceptions.HTTPError):
        scraper.fetch("https://api.github.com/x", session=session)
    assert len(session.calls) == scraper.MAX_ATTEMPTS


def test_does_not_retry_client_error(no_real_sleep):
    """404 重试也没用，直接失败，别浪费 CI 时间。"""
    session = FakeSession([FakeResponse(404), FakeResponse(200)])
    with pytest.raises(requests.exceptions.HTTPError):
        scraper.fetch("https://api.github.com/x", session=session)
    assert len(session.calls) == 1
    assert no_real_sleep == []


def test_honours_retry_after_header(no_real_sleep):
    session = FakeSession([FakeResponse(429, headers={"Retry-After": "7"}), FakeResponse(200)])
    scraper.fetch("https://api.github.com/x", session=session)
    assert no_real_sleep == [7.0]


def test_backoff_is_capped():
    assert scraper._backoff(9) <= scraper.MAX_BACKOFF
    huge = FakeResponse(429, headers={"Retry-After": "9999"})
    assert scraper._backoff(1, huge) == scraper.MAX_BACKOFF


# --- 调用方语义 -----------------------------------------------------------

TRENDING_HTML = b"""
<html><body>
<article class="Box-row">
  <h2><a href="/owner/repo">owner / repo</a></h2>
  <p>Some description</p>
  <div class="f6">
    <a href="/owner/repo/stargazers">1,234</a>
    <a href="/owner/repo/forks">56</a>
    <span itemprop="programmingLanguage">Python</span>
  </div>
</article>
</body></html>
"""


def test_scrape_trending_requests_html_accept_and_parses():
    session = FakeSession([FakeResponse(200, content=TRENDING_HTML)])
    repos = scraper.scrape_trending(session=session)
    assert session.calls[0]["headers"]["Accept"] == scraper.HTML_ACCEPT
    assert repos[0]["title"] == "owner/repo"
    assert repos[0]["url"] == "https://github.com/owner/repo"
    assert repos[0]["stars"] == "1,234"
    assert repos[0]["language"] == "Python"


def test_scrape_trending_language_path():
    session = FakeSession([FakeResponse(200, content=TRENDING_HTML)])
    scraper.scrape_trending("python", session=session)
    assert session.calls[0]["url"] == "https://github.com/trending/python"


def test_scrape_most_starred_maps_api_fields():
    payload = {"items": [{
        "full_name": "owner/repo",
        "html_url": "https://github.com/owner/repo",
        "description": None,
        "stargazers_count": 12,
        "forks_count": 3,
        "language": None,
    }]}
    session = FakeSession([FakeResponse(200, payload)])
    repos = scraper.scrape_most_starred(session=session)
    assert repos == [{
        "title": "owner/repo",
        "url": "https://github.com/owner/repo",
        "description": "No description",
        "stars": "12",
        "forks": "3",
        "language": "N/A",
    }]


def test_scrape_most_forked_returns_empty_on_http_error(no_real_sleep):
    session = FakeSession([FakeResponse(500) for _ in range(scraper.MAX_ATTEMPTS)])
    assert scraper.scrape_most_forked(session=session) == []


def test_scrape_most_starred_returns_empty_on_api_error_message():
    session = FakeSession([FakeResponse(200, {"message": "API rate limit exceeded"})])
    assert scraper.scrape_most_starred(session=session) == []
