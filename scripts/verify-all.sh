#!/usr/bin/env bash
# scripts/verify-all.sh — SPRINT-02 的全量验收入口（Python 套件 + 站点构建）
#
# plan.md 的 <!-- VERIFY --> 指向本脚本。
# 需要两套工具链：python3 + pytest，node + vitepress（node_modules 已安装）。
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "=== [1/2] Python 套件 ==="
bash scripts/verify.sh

echo
echo "=== [2/2] 站点构建与产物断言 ==="
bash scripts/verify-site.sh

echo
echo "==> 全量验收通过（Python + 站点）"
