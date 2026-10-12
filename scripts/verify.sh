#!/usr/bin/env bash
# scripts/verify.sh — SPRINT-01 的全量验收入口（plan.md 的 <!-- VERIFY --> 指向本脚本）
#
# 用法:
#   ./scripts/verify.sh                     # 语法编译检查 + 全部单测
#   ./scripts/verify.sh tests/test_http.py  # 只跑指定测试（任务级验收）
#   ./scripts/verify.sh --with-deps         # 先安装 requirements-dev.txt 再验收
#
# 退出码: 0 = 全绿; 非 0 = 有阻断项（CI 应据此失败）
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PYTHON="${PYTHON:-python3}"
WITH_DEPS=false
PYTEST_TARGETS=()
for arg in "$@"; do
  case "$arg" in
    --with-deps) WITH_DEPS=true ;;
    -h|--help) sed -n '2,10p' "${BASH_SOURCE[0]}"; exit 0 ;;
    -*) echo "未知参数: $arg（可用: --with-deps [测试路径...]）" >&2; exit 2 ;;
    *) PYTEST_TARGETS+=("$arg") ;;
  esac
done

if ! command -v "$PYTHON" >/dev/null 2>&1; then
  echo "FAIL: 找不到解释器 $PYTHON" >&2
  exit 2
fi

if [[ "$WITH_DEPS" == true ]]; then
  echo "==> 安装开发依赖 (requirements-dev.txt)"
  "$PYTHON" -m pip install --quiet -r requirements-dev.txt
fi

echo "==> [1/2] 语法编译检查 (compileall)"
"$PYTHON" -m compileall -q -x '(\.git|data|\.venv|venv|node_modules)' "$ROOT"

echo "==> [2/2] 单元测试 (pytest)"
if ! "$PYTHON" -m pytest --version >/dev/null 2>&1; then
  echo "FAIL: 未安装 pytest —— 先执行: $PYTHON -m pip install -r requirements-dev.txt" >&2
  exit 2
fi
if [[ ${#PYTEST_TARGETS[@]} -gt 0 ]]; then
  "$PYTHON" -m pytest -q "${PYTEST_TARGETS[@]}"
else
  "$PYTHON" -m pytest -q tests
fi

echo "==> VERIFY 全绿"
