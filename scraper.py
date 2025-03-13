# coding:utf-8

import datetime
import codecs
import requests
import os
import time
import json
from pyquery import PyQuery as pq


def git_add_commit_push(date, filename):
    """Git 提交并推送更改"""
    cmd_git_add = 'git add {filename}'.format(filename=filename)
    cmd_git_commit = 'git commit -m "{date}"'.format(date=date)
    cmd_git_push = 'git push -u origin master'

    os.system(cmd_git_add)
    os.system(cmd_git_commit)
    os.system(cmd_git_push)


def get_headers():
    """获取通用请求头"""
    return {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8'
    }


def get_file_path(is_timestamp=False):
    """获取文件路径，可选是否添加时间戳"""
    # 使用 YYYYMMDD 格式作为基本文件名
    date_str = datetime.datetime.now().strftime('%Y%m%d')
    year_month = datetime.datetime.now().strftime('%Y/%m')
    
    # 创建年月目录
    directory = f"data/{year_month}"
    if not os.path.exists(directory):
        os.makedirs(directory)
    
    # 如果需要时间戳，则添加小时和分钟
    if is_timestamp:
        time_str = datetime.datetime.now().strftime('%H%M')
        filename = f"{directory}/{date_str}_{time_str}.md"
    else:
        filename = f"{directory}/{date_str}.md"
    
    return filename, date_str


def check_file_exists(filename):
    """检查文件是否存在，如果存在则添加时间戳"""
    if os.path.exists(filename):
        # 文件已存在，使用带时间戳的文件名
        directory = os.path.dirname(filename)
        base_name = os.path.basename(filename)
        name_parts = os.path.splitext(base_name)
        time_str = datetime.datetime.now().strftime('%H%M')
        new_filename = f"{directory}/{name_parts[0]}_{time_str}{name_parts[1]}"
        return new_filename
    return filename


def createMarkdown(date, filename):
    """创建 Markdown 文件并写入标题"""
    # 确保目录存在
    directory = os.path.dirname(filename)
    if directory and not os.path.exists(directory):
        os.makedirs(directory)
    
    # 获取当前时间
    current_time = datetime.datetime.now().strftime('%H:%M:%S')
    
    with codecs.open(filename, 'w', 'utf-8') as f:
        f.write(f"# GitHub 热门榜单 {date} ({current_time})\n\n")
        f.write("## 目录\n\n")
        f.write("- [每日 Star 最多的仓库](#每日-star-最多的仓库)\n")
        f.write("- [每日 Fork 最多的仓库](#每日-fork-最多的仓库)\n")
        f.write("- [每日趋势榜](#每日趋势榜)\n")
        f.write("- [人工智能方向热榜](#人工智能方向热榜)\n")
        f.write("  - [Python](#python)\n")
        f.write("  - [Deep Learning](#deep-learning)\n")
        f.write("  - [Machine Learning](#machine-learning)\n\n")


def scrape_trending(language=None):
    """抓取 GitHub 趋势榜"""
    HEADERS = get_headers()

    url = 'https://github.com/trending'
    if language:
        url = f'{url}/{language}'

    r = requests.get(url, headers=HEADERS)
    assert r.status_code == 200
    
    d = pq(r.content)
    items = d('article.Box-row')

    repos = []
    for item in items[:10]:  # 只获取前10个
        i = pq(item)
        title = i("h2 a").text().strip().replace(' ', '')
        owner_repo = i("h2 a").attr("href").strip('/')
        description = i("p").text().strip()
        url = f"https://github.com/{owner_repo}"
        
        # 获取 stars 和 forks 信息
        stars_elem = i("div.f6 a[href$='stargazers']")
        stars = stars_elem.text().strip() if stars_elem else "N/A"
        
        forks_elem = i("div.f6 a[href$='forks']")
        forks = forks_elem.text().strip() if forks_elem else "N/A"
        
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


def scrape_most_starred():
    """抓取每日 Star 最多的仓库"""
    HEADERS = get_headers()

    # 使用 GitHub API 获取最近创建的、按 star 数排序的仓库
    # 动态计算一年前的日期
    one_year_ago = (datetime.datetime.now() - datetime.timedelta(days=365)).strftime('%Y-%m-%d')
    url = f'https://api.github.com/search/repositories?q=created:>{one_year_ago}&sort=stars&order=desc&per_page=10'
    
    r = requests.get(url, headers=HEADERS)
    data = r.json()
    
    repos = []
    for item in data.get('items', [])[:10]:
        repos.append({
            "title": item['full_name'],
            "url": item['html_url'],
            "description": item['description'] or "No description",
            "stars": str(item['stargazers_count']),
            "forks": str(item['forks_count']),
            "language": item['language'] or "N/A"
        })
    
    return repos


def scrape_most_forked():
    """抓取每日 Fork 最多的仓库"""
    HEADERS = get_headers()

    # 使用 GitHub API 获取最近更新的、按 forks 数排序的仓库
    # 动态计算一年前的日期
    one_year_ago = (datetime.datetime.now() - datetime.timedelta(days=365)).strftime('%Y-%m-%d')
    url = f'https://api.github.com/search/repositories?q=pushed:>{one_year_ago}&sort=forks&order=desc&per_page=10'
    
    r = requests.get(url, headers=HEADERS)
    data = r.json()
    
    repos = []
    for item in data.get('items', [])[:10]:
        repos.append({
            "title": item['full_name'],
            "url": item['html_url'],
            "description": item['description'] or "No description",
            "stars": str(item['stargazers_count']),
            "forks": str(item['forks_count']),
            "language": item['language'] or "N/A"
        })
    
    return repos


def write_repos_to_markdown(filename, section_title, repos, is_subsection=False):
    """将仓库信息以表格方式写入 Markdown 文件"""
    with codecs.open(filename, "a", "utf-8") as f:
        if is_subsection:
            f.write(f'### {section_title}\n\n')
        else:
            f.write(f'## {section_title}\n\n')
        
        if not repos:
            f.write("*暂无数据*\n\n")
            return
        
        # 写入表格头部
        f.write("| 序号 | 名称 | 描述 | 语言 | Stars | Forks |\n")
        f.write("| --- | --- | --- | --- | --- | --- |\n")
        
        # 写入表格内容
        for i, repo in enumerate(repos):
            # 处理描述中可能存在的 | 符号，避免破坏表格结构
            description = repo['description'].replace('|', '\\|').replace('\n', ' ')
            # 限制描述长度，避免表格过宽
            if len(description) > 100:
                description = description[:97] + "..."
                
            f.write(f"| {i+1} | [{repo['title']}]({repo['url']}) | {description} | {repo['language']} | {repo['stars']} | {repo['forks']} |\n")
        
        f.write("\n")


def scrape_all(use_timestamp=False):
    """执行所有抓取任务"""
    # 获取文件路径
    filename, date_str = get_file_path(use_timestamp)
    
    # 检查文件是否存在，如果存在则添加时间戳
    if not use_timestamp:
        filename = check_file_exists(filename)
    
    # 创建 markdown 文件
    display_date = datetime.datetime.now().strftime('%Y-%m-%d')
    createMarkdown(display_date, filename)
    
    # 抓取每日 Star 最多的仓库
    most_starred_repos = scrape_most_starred()
    write_repos_to_markdown(filename, "每日 Star 最多的仓库", most_starred_repos)
    
    # 抓取每日 Fork 最多的仓库
    most_forked_repos = scrape_most_forked()
    write_repos_to_markdown(filename, "每日 Fork 最多的仓库", most_forked_repos)
    
    # 抓取每日趋势榜
    trending_repos = scrape_trending()
    write_repos_to_markdown(filename, "每日趋势榜", trending_repos)
    
    # 抓取人工智能方向热榜
    f = codecs.open(filename, "a", "utf-8")
    f.write("## 人工智能方向热榜\n\n")
    f.close()
    
    # Python 热榜
    python_repos = scrape_trending("python")
    write_repos_to_markdown(filename, "Python", python_repos, True)
    
    # Deep Learning 热榜
    dl_repos = scrape_trending("deep-learning")
    write_repos_to_markdown(filename, "Deep Learning", dl_repos, True)
    
    # Machine Learning 热榜
    ml_repos = scrape_trending("machine-learning")
    write_repos_to_markdown(filename, "Machine Learning", ml_repos, True)
    
    return filename, display_date


def job(use_git=False, use_timestamp=False):
    """主函数，执行抓取任务"""
    try:
        filename, display_date = scrape_all(use_timestamp)
        
        # 如果需要，执行 git 操作
        if use_git:
            git_add_commit_push(display_date, filename)
        
        print(f"已完成抓取并保存到 {filename}")
        return True
    except Exception as e:
        print(f"抓取失败: {str(e)}")
        return False


if __name__ == '__main__':
    job()