"""TASK-005 脱敏与发布面安全检查。

用户问「是否有脱敏处理」。答案是：**发布面结构上就不该有敏感信息**——
但这句话得能被自动化证明，而不是靠保证。这里做三件事：

1. 全仓库（含 data/）扫**严格 token 形态**：真实凭据形状的字符串一个都不许有；
2. 我手写的文件里扫**本地绝对路径**（data/ 是抓取内容，可能本身提到 /Users/ 之类，不参与）；
3. 盯住**发布面**：构建产物同样扫一遍，并确认备份目录没被跟踪。
"""

import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
DIST = REPO_ROOT / "docs" / ".vitepress" / "dist"

# 真实凭据形状（不是关键词）：随机串 + 固定前缀，误报率极低
SECRET_PATTERNS = {
    "GitHub PAT (ghp_)": re.compile(r'ghp_[A-Za-z0-9]{36}'),
    "GitHub App token (ghs_)": re.compile(r'ghs_[A-Za-z0-9]{36}'),
    "GitHub fine-grained PAT": re.compile(r'github_pat_[A-Za-z0-9_]{22,}'),
    "AWS access key id": re.compile(r'AKIA[0-9A-Z]{16}'),
    "私钥": re.compile(r'-----BEGIN [A-Z ]*PRIVATE KEY-----'),
    "Slack token": re.compile(r'xox[baprs]-[A-Za-z0-9-]{10,}'),
}

LOCAL_PATH_PATTERNS = {
    "本机用户目录": re.compile(r'/home/[a-z][a-z0-9_-]+/'),
    "macOS 用户目录": re.compile(r'/Users/[A-Za-z]'),
    "Windows 用户目录": re.compile(r'C:\\\\Users\\\\'),
}

# 抓取内容里出现这些词是正常的（比如讲 secrets 管理的仓库），所以 data/ 不参与路径扫描
DATA_PREFIX = "data/"
# 工具配置里会定义「路径模式」本身（例如 denylist 里的 Windows 用户目录写法），不是泄漏
CONFIG_PREFIXES = (".cursor/",)


def tracked_files():
    """git 跟踪的文件（相对路径，POSIX 分隔）——自动排除 node_modules / 生成物 / backups。"""
    out = subprocess.run(
        ["git", "ls-files", "-z"], cwd=REPO_ROOT, capture_output=True, check=True
    ).stdout.decode("utf-8")
    return [name for name in out.split("\0") if name]


def scan(paths, patterns):
    """返回 [(pattern_name, relpath, line_number, 摘要)]。"""
    hits = []
    for relpath in paths:
        path = REPO_ROOT / relpath
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for name, pattern in patterns.items():
            for match in pattern.finditer(text):
                line = text.count("\n", 0, match.start()) + 1
                hits.append((name, relpath, line, match.group(0)[:24]))
    return hits


# --- 1. 全仓库严格形态扫描 ------------------------------------------------

def test_no_secret_shapes_in_tracked_files():
    hits = scan(tracked_files(), SECRET_PATTERNS)
    assert hits == [], f"仓库里出现凭据形状的字符串: {hits[:5]}"


# --- 2. 手写文件里不能有本地绝对路径 --------------------------------------

def test_no_local_absolute_paths_in_authored_files():
    authored = [
        name for name in tracked_files()
        if not name.startswith(DATA_PREFIX) and not name.startswith(CONFIG_PREFIXES)
    ]
    hits = scan(authored, LOCAL_PATH_PATTERNS)
    assert hits == [], f"手写文件里出现本机绝对路径: {hits[:5]}"


# --- 3. 发布面（构建产物）同样要干净 --------------------------------------

def test_built_site_has_no_secrets_or_local_paths():
    if not DIST.exists():
        pytest.skip("尚未构建站点（先跑 bash scripts/verify-site.sh）")

    pages = [str(p.relative_to(REPO_ROOT)) for p in DIST.rglob("*") if p.is_file()]
    hits = scan(pages, {**SECRET_PATTERNS, **LOCAL_PATH_PATTERNS})
    assert hits == [], f"构建产物里出现敏感形状: {hits[:5]}"


# --- 4. 备份与凭据文件不得入库 --------------------------------------------

def test_backups_are_not_tracked():
    tracked = tracked_files()
    assert not [name for name in tracked if name.startswith("backups/")]

    result = subprocess.run(
        ["git", "check-ignore", "-q", "backups/"], cwd=REPO_ROOT, capture_output=True, check=False
    )
    assert result.returncode == 0, "backups/ 没有被 .gitignore 覆盖"


@pytest.mark.parametrize("name", [".env", ".env.local", "credentials.json", "id_rsa", "server.pem"])
def test_credential_files_are_not_tracked(name):
    assert name not in tracked_files()


# --- 5. workflow 不得回显凭据 ---------------------------------------------

def test_workflows_never_echo_secrets():
    workflows = (REPO_ROOT / ".github" / "workflows")
    offenders = []
    for path in workflows.glob("*.yml"):
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if re.search(r'(echo|print|cat)\b.*\$\{\{\s*secrets\.', stripped):
                offenders.append(f"{path.name}:{lineno}")
            if re.search(r'echo\s+.*\$\{?GITHUB_TOKEN', stripped):
                offenders.append(f"{path.name}:{lineno}")
    assert offenders == [], f"workflow 在回显凭据: {offenders}"


# --- 6. token 只允许出现在请求头 ------------------------------------------

def test_token_only_used_for_authorization_header():
    """token 从环境读、只进 Authorization 头；不得写文件、不得进日志。"""
    source = (REPO_ROOT / "scraper.py").read_text(encoding="utf-8")

    token_lines = [
        line.strip() for line in source.splitlines()
        if re.search(r'\btoken\b', line) and not line.strip().startswith("#")
    ]
    # 允许出现的三类：读取、判空、拼 Authorization / docstring 提及
    for line in token_lines:
        assert (
            "os.environ.get" in line
            or "Authorization" in line
            or "if token" in line
            or "= get_token()" in line
            or line.startswith('"""') or line.startswith('#')
            or "GITHUB_TOKEN" in line
        ), f"token 出现在了非预期位置: {line}"

    # 抓取结果与日志里不得出现 token 变量
    for forbidden in ("f.write(f\"{token}", "print(f\"{token}", "json.dumps(token"):
        assert forbidden not in source
