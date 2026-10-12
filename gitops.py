# coding:utf-8
"""Git 操作封装。

TASK-005 之前，scraper.py 与 merge_files.py 各自用 os.system 拼字符串跑 git：
一是把参数当 shell 命令执行（注入面），二是失败完全静默，三是 push 目标硬编码
master。这里统一成 subprocess + 参数列表，只有一处实现。
"""

import os
import subprocess


class GitError(RuntimeError):
    """git 命令非零退出。"""


def run_git(*args, cwd=None, check=True):
    """执行 git 子命令；参数以列表传入，不经过 shell。"""
    result = subprocess.run(
        ['git', *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout or '').strip()
        raise GitError(f"git {' '.join(args)} 失败 (exit {result.returncode}): {detail}")
    return result


def current_branch(cwd=None):
    """当前分支名；detached HEAD 时返回 HEAD。

    仓库刚 init 还没有第一次提交时 `rev-parse HEAD` 会失败，
    所以优先用 symbolic-ref，它在「未出生」的分支上也能给出名字。
    """
    result = run_git('symbolic-ref', '--short', 'HEAD', cwd=cwd, check=False)
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip()
    result = run_git('rev-parse', '--abbrev-ref', 'HEAD', cwd=cwd, check=False)
    return result.stdout.strip() or 'HEAD'


def has_staged_changes(cwd=None):
    """暂存区是否有变更（git diff --cached --quiet 的退出码 1 表示有）。"""
    return run_git('diff', '--cached', '--quiet', cwd=cwd, check=False).returncode == 1


def add_commit_push(paths, message, cwd=None, push=True, remote='origin'):
    """定向 add → 有变更才 commit → 推送到**当前分支**。

    返回是否真的产生了提交（无变更返回 False，不当作错误）。
    """
    if isinstance(paths, (str, os.PathLike)):
        paths = [paths]
    paths = [str(p) for p in paths]

    # `--` 之后全按路径解释，避免文件名被当成参数
    run_git('add', '--', *paths, cwd=cwd)

    if not has_staged_changes(cwd=cwd):
        return False

    run_git('commit', '-m', message, cwd=cwd)

    if push:
        branch = current_branch(cwd=cwd)
        if branch and branch != 'HEAD':
            run_git('push', remote, branch, cwd=cwd)
        else:
            run_git('push', cwd=cwd)

    return True
