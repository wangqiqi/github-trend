# coding:utf-8

import datetime
import os
import re
import sys
import tempfile
import time

import requests
from pyquery import PyQuery as pq

from gitops import add_commit_push


def git_add_commit_push(date, filename):
    """Git 提交并推送更改：定向 add 指定文件，失败会抛 GitError 而不是静默。"""
    message = f"Update trending repositories: {date}"
    return add_commit_push(filename, message)


# --- 网络层 ---------------------------------------------------------------
# (connect, read) 超时：没有它，CI 遇到黑洞连接会一直挂到 6 小时上限。
DEFAULT_TIMEOUT = (5, 20)
MAX_ATTEMPTS = 3
BACKOFF_BASE = 1.0
MAX_BACKOFF = 30.0
# 只有这些状态码值得重试：403/429 是限流，5xx 是服务端抖动。
# 404/401 之类重试多少次都一样，直接失败更快。
RETRY_STATUSES = frozenset({403, 429, 500, 502, 503, 504})
API_ACCEPT = 'application/vnd.github.v3+json'
HTML_ACCEPT = 'text/html,application/xhtml+xml'

# 纯数字，或合法的千分位分组，可带小数（配合 k/m 后缀）
COUNT_PATTERN = re.compile(r'^(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d+)?$')

# 便于测试注入，避免用例里真的睡 1s/2s
_sleep = time.sleep
_session = None


def get_token():
    """CI 里由 GitHub Actions 注入 GITHUB_TOKEN，用于绕开未认证的 10 次/分限流。"""
    return os.environ.get('GITHUB_TOKEN') or os.environ.get('GH_TOKEN') or None


def get_headers(accept=API_ACCEPT):
    """获取请求头；有 token 就带上鉴权。

    注意不再声明 br：requests 未装 brotli 时无法解压 br 响应，会拿到乱码。
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': accept,
        'Accept-Encoding': 'gzip, deflate',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    }
    token = get_token()
    if token:
        headers['Authorization'] = f'Bearer {token}'
    return headers


def get_session():
    """进程内复用一个 Session：连接池复用 + 少一次 TLS 握手。"""
    global _session
    if _session is None:
        _session = requests.Session()
    return _session


def _backoff(attempt, response=None):
    """退避秒数：优先听服务端 Retry-After，否则指数退避。"""
    if response is not None:
        retry_after = response.headers.get('Retry-After')
        if retry_after and retry_after.isdigit():
            return min(float(retry_after), MAX_BACKOFF)
    return min(BACKOFF_BASE * (2 ** (attempt - 1)), MAX_BACKOFF)


def fetch(url, accept=API_ACCEPT, session=None, max_attempts=MAX_ATTEMPTS):
    """带超时与退避重试的 GET。

    返回 2xx 响应；重试耗尽后抛 requests 异常 —— 由调用方决定
    「返回空」还是「整体失败」，本函数不吞异常。
    """
    session = session or get_session()
    headers = get_headers(accept)
    last_error = None

    for attempt in range(1, max_attempts + 1):
        try:
            response = session.get(url, headers=headers, timeout=DEFAULT_TIMEOUT)
            if response.status_code in RETRY_STATUSES and attempt < max_attempts:
                delay = _backoff(attempt, response)
                print(f"HTTP {response.status_code}，{delay:.1f}s 后重试 ({attempt}/{max_attempts - 1}): {url}")
                _sleep(delay)
                continue
            response.raise_for_status()
            return response
        except requests.exceptions.HTTPError as exc:
            status = getattr(getattr(exc, 'response', None), 'status_code', None)
            if status not in RETRY_STATUSES or attempt >= max_attempts:
                raise
            last_error = exc
        except requests.exceptions.RequestException as exc:
            if attempt >= max_attempts:
                raise
            last_error = exc

        delay = _backoff(attempt)
        print(f"请求失败，{delay:.1f}s 后重试 ({attempt}/{max_attempts - 1}): {last_error}")
        _sleep(delay)

    raise last_error if last_error is not None else RuntimeError('unreachable: fetch retry loop')


def get_file_path(is_timestamp=False):
    """获取文件路径，可选是否添加时间戳"""
    # 使用 YYYYMMDD 格式作为基本文件名
    date_str = datetime.datetime.now().strftime('%Y%m%d')
    year_month = datetime.datetime.now().strftime('%Y/%m')
    
    # 创建年月目录
    directory = f"data/{year_month}"
    if not os.path.exists(directory):
        os.makedirs(directory)
    
    # 需要时间戳时精确到秒：分钟粒度会让同分钟的两次抓取互相覆盖
    if is_timestamp:
        time_str = datetime.datetime.now().strftime('%H%M%S')
        filename = f"{directory}/{date_str}_{time_str}.md"
    else:
        filename = f"{directory}/{date_str}.md"
    
    return filename, date_str


def check_file_exists(filename):
    """目标已存在时追加序号，绝不覆盖既有数据。

    旧实现用「到分钟的时间戳」避让：同一分钟内第二次抓取会直接覆盖前一次。
    """
    if not os.path.exists(filename):
        return filename

    directory = os.path.dirname(filename)
    base_name, extension = os.path.splitext(os.path.basename(filename))

    index = 1
    while True:
        candidate = os.path.join(directory, f"{base_name}_{index:02d}{extension}")
        if not os.path.exists(candidate):
            return candidate
        index += 1


def normalize_count(value):
    """把 star/fork 数统一成纯整数字符串，无法解析时返回空串。

    趋势页给的是 '150,148'，API 给的是 150148，同一份文档里两种写法没法排序统计。
    顺带兼容 '12.3k' 这类紧凑写法；千分位必须是合法分组，否则宁可留空。
    """
    if value is None:
        return ''

    text = str(value).strip().replace(' ', '')
    if not text:
        return ''

    multiplier = 1
    suffix = text[-1]
    if suffix in 'kK':
        multiplier, text = 1000, text[:-1]
    elif suffix in 'mM':
        multiplier, text = 1_000_000, text[:-1]

    if not COUNT_PATTERN.match(text):
        return ''

    number = float(text.replace(',', ''))
    return str(int(round(number * multiplier)))


def truncate_description(text, limit=100):
    """转义表格分隔符并按词边界截断，返回长度不超过 limit 的描述。"""
    text = (text or '').replace('|', '\\|').replace('\n', ' ').replace('\r', ' ').strip()
    if len(text) <= limit:
        return text

    cut = text[:limit - 3]
    space = cut.rfind(' ')
    if space > 0:
        cut = cut[:space]
    return cut.rstrip() + '...'


def escape_link_text(text):
    """中括号会破坏 [标题](链接) 结构，转义掉。"""
    return (text or '').replace('[', '\\[').replace(']', '\\]')


def render_header(date):
    """渲染文档头部（标题 + 目录），纯函数，不碰磁盘。"""
    current_time = datetime.datetime.now().strftime('%H:%M:%S')
    return (
        f"# GitHub 热门榜单 {date} ({current_time})\n\n"
        "## 目录\n\n"
        "- [每日 Star 最多的仓库](#每日-star-最多的仓库)\n"
        "- [每日 Fork 最多的仓库](#每日-fork-最多的仓库)\n"
        "- [每日趋势榜](#每日趋势榜)\n"
        "- [Python](#python)\n\n"
    )


def scrape_trending(language=None, session=None):
    """抓取 GitHub 趋势榜"""
    url = 'https://github.com/trending'
    if language:
        url = f'{url}/{language}'

    r = fetch(url, accept=HTML_ACCEPT, session=session)

    d = pq(r.content)
    items = d('article.Box-row')

    repos = []
    for item in items[:10]:  # 只获取前10个
        i = pq(item)
        title = i("h2 a").text().strip().replace(' ', '')
        owner_repo = i("h2 a").attr("href").strip('/')
        description = i("p").text().strip()
        url = f"https://github.com/{owner_repo}"
        
        # 获取 stars 和 forks 信息（趋势页带千分位，统一成纯整数）
        stars_elem = i("div.f6 a[href$='stargazers']")
        stars = normalize_count(stars_elem.text()) if stars_elem else ''
        
        forks_elem = i("div.f6 a[href$='forks']")
        forks = normalize_count(forks_elem.text()) if forks_elem else ''
        
        language_elem = i("div.f6 span[itemprop='programmingLanguage']")
        lang = language_elem.text().strip() if language_elem else "N/A"
        
        repos.append({
            "title": title,
            "url": url,
            "description": description,
            "stars": stars,
            "forks": forks,
            "language": lang
        })
    
    return repos


def scrape_most_starred(session=None):
    """抓取每日 Star 最多的仓库"""
    try:
        # 使用 GitHub API 获取最近创建的、按 star 数排序的仓库
        one_year_ago = (datetime.datetime.now() - datetime.timedelta(days=365)).strftime('%Y-%m-%d')
        url = f'https://api.github.com/search/repositories?q=created:>{one_year_ago}&sort=stars&order=desc&per_page=10'

        r = fetch(url, session=session)
        data = r.json()
        
        if 'items' not in data:
            print(f"GitHub API 响应异常: {data.get('message', '未知错误')}")
            return []
        
        repos = []
        for item in data.get('items', [])[:10]:
            repos.append({
                "title": item['full_name'],
                "url": item['html_url'],
                "description": item['description'] or "No description",
                "stars": normalize_count(item['stargazers_count']),
                "forks": normalize_count(item['forks_count']),
                "language": item['language'] or "N/A"
            })
        
        if not repos:
            print("未获取到任何仓库数据 (Star)")
        return repos
    except requests.exceptions.RequestException as e:
        print(f"请求 GitHub API 失败 (Star): {str(e)}")
        return []
    except Exception as e:
        print(f"处理数据失败 (Star): {str(e)}")
        return []


def scrape_most_forked(session=None):
    """抓取每日 Fork 最多的仓库"""
    try:
        # 使用 GitHub API 获取最近更新的、按 forks 数排序的仓库
        one_year_ago = (datetime.datetime.now() - datetime.timedelta(days=365)).strftime('%Y-%m-%d')
        url = f'https://api.github.com/search/repositories?q=pushed:>{one_year_ago}&sort=forks&order=desc&per_page=10'

        r = fetch(url, session=session)
        data = r.json()
        
        if 'items' not in data:
            print(f"GitHub API 响应异常: {data.get('message', '未知错误')}")
            return []
        
        repos = []
        for item in data.get('items', [])[:10]:
            repos.append({
                "title": item['full_name'],
                "url": item['html_url'],
                "description": item['description'] or "No description",
                "stars": normalize_count(item['stargazers_count']),
                "forks": normalize_count(item['forks_count']),
                "language": item['language'] or "N/A"
            })
        
        if not repos:
            print("未获取到任何仓库数据 (Fork)")
        return repos
    except requests.exceptions.RequestException as e:
        print(f"请求 GitHub API 失败 (Fork): {str(e)}")
        return []
    except Exception as e:
        print(f"处理数据失败 (Fork): {str(e)}")
        return []


class ScrapeError(RuntimeError):
    """抓取阶段的确定性失败：某一段没拿到数据，不允许产出半成品文档。"""


def write_atomic(filename, content):
    """先写同目录临时文件再 os.replace —— 崩溃或中断不会留下半截文件。"""
    directory = os.path.dirname(filename) or '.'
    if not os.path.exists(directory):
        os.makedirs(directory)

    fd, tmp_path = tempfile.mkstemp(dir=directory, prefix='.tmp-', suffix='.md')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            handle.write(content)
        os.replace(tmp_path, filename)
    except BaseException:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise


def render_section(section_title, repos, is_subsection=False):
    """把仓库列表渲染成 Markdown 段落（返回字符串，不写盘）。"""
    lines = [f"{'###' if is_subsection else '##'} {section_title}", ""]

    if not repos:
        lines += ["*暂无数据*", ""]
        return "\n".join(lines) + "\n"

    # 写入表格头部
    lines += [
        "| 序号 | 名称 | 描述 | 语言 | Stars | Forks |",
        "| --- | --- | --- | --- | --- | --- |",
    ]

    # 写入表格内容
    for i, repo in enumerate(repos):
        # 描述里可能含 | 与换行，会破坏表格结构；过长则按词边界截断
        description = truncate_description(repo['description'])
        title = escape_link_text(repo['title'])

        lines.append(
            f"| {i+1} | [{title}]({repo['url']}) | {description} | {repo['language']} | {repo['stars']} | {repo['forks']} |"
        )

    lines.append("")
    return "\n".join(lines) + "\n"


def scrape_all(use_timestamp=False, session=None):
    """抓取所有数据并原子写入文件。

    先全部抓完、全部校验，再一次性落盘：任一段为空就抛 ScrapeError，
    绝不留下「文件已建、段落是暂无数据」的半成品让 CI 提交出去。
    """
    filename, date = get_file_path(use_timestamp)
    filename = check_file_exists(filename)

    sections = []

    # 抓取每日 Star 最多的仓库
    star_repos = scrape_most_starred(session=session)
    if not star_repos:
        raise ScrapeError("每日 Star 最多的仓库：未获取到数据")
    sections.append(("每日 Star 最多的仓库", star_repos, False))

    # 抓取每日 Fork 最多的仓库
    fork_repos = scrape_most_forked(session=session)
    if not fork_repos:
        raise ScrapeError("每日 Fork 最多的仓库：未获取到数据")
    sections.append(("每日 Fork 最多的仓库", fork_repos, False))

    # 抓取每日趋势榜
    trending_repos = scrape_trending(session=session)
    if not trending_repos:
        raise ScrapeError("每日趋势榜：未获取到数据")
    sections.append(("每日趋势榜", trending_repos, False))

    # 抓取 Python 趋势榜（原先挂在「人工智能方向热榜」下的子段落，
    # 那一段从 2025-03 建仓到 2026-10 从未拿到过数据，已整段移除）
    python_repos = scrape_trending("python", session=session)
    if not python_repos:
        raise ScrapeError("Python 趋势榜：未获取到数据")
    sections.append(("Python", python_repos, False))

    content = render_header(date) + "".join(
        render_section(title, repos, is_subsection)
        for title, repos, is_subsection in sections
    )
    write_atomic(filename, content)

    return filename, date


def job(use_git=False, use_timestamp=False, session=None):
    """主函数，执行抓取任务；返回是否成功。"""
    try:
        print("开始抓取数据...")
        filename, display_date = scrape_all(use_timestamp, session=session)

        # 如果需要，执行 git 操作
        if use_git:
            print("执行 Git 操作...")
            git_add_commit_push(display_date, filename)

        print(f"已完成抓取并保存到 {filename}")
        return True
    except ScrapeError as e:
        print(f"抓取失败: {e}")
        return False
    except requests.exceptions.RequestException as e:
        print(f"网络请求失败: {str(e)}")
        return False
    except Exception as e:
        import traceback
        print(f"抓取失败: {str(e)}")
        print("详细错误信息:")
        print(traceback.format_exc())
        return False


def main():
    """CLI 入口：失败必须给非零退出码，否则 CI 会把脏数据当成功提交。"""
    return 0 if job() else 1


if __name__ == '__main__':
    sys.exit(main())