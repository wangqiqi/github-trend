"""TASK-006 跨仓库联动防漂移。

本站与博客站（`vitepress-blog-source`）只通过 URL 外链关联，**构建上互不依赖**：
   * `github-trend` 仓库自带 GitHub Pages（项目站点）→ 自动落在 znza.top/github-trend/
   * 博客仓库的「项目站」菜单里挂它的 URL

这种「松耦合」最容易漂：改了站点路径、挪了仓库、或者博客那边误删条目，两边都不会报错。
所以这里在**兄弟仓库存在时**做真校验，不存在（CI 上没有）就 skip。
"""

import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
BLOG_REPO = REPO_ROOT.parent / "vitepress-blog-source"
HOMEPAGES = BLOG_REPO / "docs" / ".vitepress" / "data" / "project-homepages.json"

SITE_URL = "https://znza.top/github-trend/"
SLUG = "github-trend"

requires_blog = pytest.mark.skipif(
    not HOMEPAGES.exists(), reason="兄弟仓库 vitepress-blog-source 不在本机（CI 上正常）"
)


def blog_sites():
    return {site["slug"]: site for site in json.loads(HOMEPAGES.read_text(encoding="utf-8"))["sites"]}


@requires_blog
def test_blog_project_nav_lists_this_site():
    entries = blog_sites()
    assert SLUG in entries, "博客「项目站」菜单里没有 github-trend 条目"
    assert entries[SLUG]["url"] == SITE_URL


@requires_blog
def test_blog_entry_url_matches_site_base():
    """博客里挂的 URL 必须与站点 config 的 base 对得上，否则点过去 404。"""
    config = (REPO_ROOT / "docs" / ".vitepress" / "config.mts").read_text(encoding="utf-8")
    base = re.search(r"base:\s*'([^']+)'", config).group(1)
    assert SITE_URL.endswith(base), f"base={base} 与博客入口 {SITE_URL} 不一致"


@requires_blog
def test_blog_repo_is_deployed_independently():
    """博客靠自己的 workflow 部署，与本仓库没有构建依赖——不能出现交叉引用文件路径。"""
    blog_workflows = BLOG_REPO / ".github" / "workflows"
    if not blog_workflows.exists():
        pytest.skip("博客仓库没有 workflow 目录")

    text = "\n".join(p.read_text(encoding="utf-8") for p in blog_workflows.glob("*.yml"))
    assert "github-trend" not in text, "博客部署流程不应依赖本仓库（保持单向 URL 关联）"


def test_sync_chain_is_documented():
    """「抓取 → 提交 → 部署」链必须在文档里写清楚，尤其是 GITHUB_TOKEN 不触发 push 这件事。"""
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    about = (REPO_ROOT / "docs" / "about.md").read_text(encoding="utf-8")

    for text, name in ((readme, "README.md"), (about, "about.md")):
        assert "workflow_run" in text, f"{name} 没写清部署是靠 workflow_run 触发的"
        assert "GITHUB_TOKEN" in text, f"{name} 没写清 GITHUB_TOKEN 提交不触发 push 事件"
        assert "deploy-site.yml" in text or "deploy-site" in text, f"{name} 没提部署 workflow"


def test_readme_documents_two_repo_relationship():
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    assert "vitepress-blog-source" in readme
