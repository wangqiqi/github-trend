"""TASK-005 git 操作测试。

用真实的临时 git 仓库跑（git 本身很快），断言的是行为而不是「调用了什么函数」。
关键回归：参数不再经过 shell；push 不再硬编码 master；只提交指定文件。
"""

import subprocess
from pathlib import Path

import pytest

import gitops
import scraper


@pytest.fixture
def repo(tmp_path):
    """初始化一个带身份配置的临时 git 仓库（分支 main，证明不再写死 master）。"""
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True)
    return tmp_path


def log_subjects(repo: Path):
    result = subprocess.run(
        ["git", "log", "--format=%s"], cwd=repo, capture_output=True, text=True, check=False
    )
    return [line for line in result.stdout.splitlines() if line]


# --- 基本提交行为 ---------------------------------------------------------

def test_add_commit_push_commits_selected_file(repo):
    target = repo / "data.md"
    target.write_text("content", encoding="utf-8")

    assert gitops.add_commit_push(str(target), "feat: data", cwd=repo, push=False) is True
    assert log_subjects(repo) == ["feat: data"]


def test_second_call_without_changes_returns_false(repo):
    target = repo / "data.md"
    target.write_text("content", encoding="utf-8")
    gitops.add_commit_push(str(target), "first", cwd=repo, push=False)

    assert gitops.add_commit_push(str(target), "second", cwd=repo, push=False) is False
    assert log_subjects(repo) == ["first"]


def test_only_listed_paths_are_committed(repo):
    """定向 add：同目录下的其它改动不能被顺带提交。"""
    wanted = repo / "wanted.md"
    unwanted = repo / "unwanted.md"
    wanted.write_text("a", encoding="utf-8")
    unwanted.write_text("b", encoding="utf-8")

    gitops.add_commit_push(str(wanted), "only wanted", cwd=repo, push=False)

    tracked = subprocess.run(
        ["git", "ls-tree", "--name-only", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.split()
    assert tracked == ["wanted.md"]
    assert unwanted.exists()


def test_branch_is_detected_not_hardcoded(repo):
    """旧代码 `git push -u origin master` 在 main 分支上必然失败。"""
    assert gitops.current_branch(cwd=repo) == "main"


def test_push_disabled_does_not_touch_remotes(repo):
    """没有远端却传 push=True 会报错；push=False 必须完全不动远端。"""
    target = repo / "d.md"
    target.write_text("x", encoding="utf-8")
    gitops.add_commit_push(str(target), "no push", cwd=repo, push=False)

    remotes = subprocess.run(
        ["git", "remote"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()
    assert remotes == ""


# --- 注入面与错误语义 -----------------------------------------------------

def test_shell_metacharacters_in_message_are_not_executed(repo):
    target = repo / "d.md"
    target.write_text("x", encoding="utf-8")
    marker = repo / "pwned"
    message = f'fix: "; touch {marker}; echo "'

    gitops.add_commit_push(str(target), message, cwd=repo, push=False)

    assert not marker.exists(), "消息里的 shell 元字符被执行了"
    assert log_subjects(repo) == [message]


def test_shell_metacharacters_in_path_are_not_executed(repo):
    """恶意文件名不会被当成命令拼接执行。"""
    marker = repo / "pwned"
    weird = repo / f'x; touch {marker.name}'
    weird.write_text("x", encoding="utf-8")

    gitops.add_commit_push(str(weird), "weird path", cwd=repo, push=False)

    assert not marker.exists()


def test_git_failure_raises_git_error(repo):
    with pytest.raises(gitops.GitError) as excinfo:
        gitops.run_git("rev-parse", "--verify", "no-such-ref", cwd=repo)
    assert "exit" in str(excinfo.value)


def test_check_false_returns_result_instead_of_raising(repo):
    result = gitops.run_git("rev-parse", "--verify", "no-such-ref", cwd=repo, check=False)
    assert result.returncode != 0


# --- scraper 侧的收敛 -----------------------------------------------------

def test_scraper_delegates_to_gitops(repo, monkeypatch):
    """scraper 只保留一个薄封装，实现只有 gitops 一份。"""
    calls = {}

    def fake(paths, message, **kwargs):
        calls["paths"] = paths
        calls["message"] = message
        return True

    monkeypatch.setattr(scraper, "add_commit_push", fake)
    assert scraper.git_add_commit_push("20261012", "data/2026/10/20261012.md") is True
    assert calls["paths"] == "data/2026/10/20261012.md"
    assert "20261012" in calls["message"]


def test_no_os_system_anywhere():
    """整个仓库都不该再有 os.system 拼命令（用 AST 查调用，注释与文档串不算）。"""
    import ast

    root = Path(__file__).resolve().parents[1]
    offenders = []
    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if (
                isinstance(func, ast.Attribute)
                and func.attr == "system"
                and isinstance(func.value, ast.Name)
                and func.value.id == "os"
            ):
                offenders.append(f"{path.relative_to(root)}:{node.lineno}")
    assert offenders == []
