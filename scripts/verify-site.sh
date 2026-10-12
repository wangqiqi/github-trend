#!/usr/bin/env bash
# scripts/verify-site.sh — 站点验收：生成内容 → VitePress 构建 → 产物断言
#
# 用法: bash scripts/verify-site.sh
# 退出码: 0 = 全绿; 非 0 = 有阻断项（CI 应据此失败）
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

DIST="docs/.vitepress/dist"
BASE_PREFIX="/github-trend/"

if [[ ! -d node_modules ]]; then
  echo "FAIL: 未安装站点依赖 —— 先执行: npm install" >&2
  exit 2
fi

echo "==> [1/3] 生成站点内容"
if [[ -f scripts/build_site_content.mjs ]]; then
  node scripts/build_site_content.mjs
else
  echo "  (暂无内容生成器，先构建骨架)"
fi

echo "==> [2/3] 构建 VitePress"
npx vitepress build docs

echo "==> [3/3] 产物断言"
fail=0

if [[ ! -f "$DIST/index.html" ]]; then
  echo "FAIL: 产物缺少 index.html" >&2
  fail=1
fi

# base 前缀必须生效，否则挂到 znza.top/github-trend/ 后资源全 404
if ! grep -q -- "$BASE_PREFIX" "$DIST/index.html"; then
  echo "FAIL: 首页未带 base 前缀 $BASE_PREFIX" >&2
  fail=1
fi

pages="$(find "$DIST" -name '*.html' | wc -l | tr -d ' ')"
if [[ "$pages" -lt 2 ]]; then
  echo "FAIL: 产物页面数异常（$pages）" >&2
  fail=1
fi

# 骨架阶段只保证首页与数据说明存在；逐日页面由内容生成器负责（TASK-004 起）
for required in index.html about.html; do
  if [[ ! -f "$DIST/$required" ]]; then
    echo "FAIL: 缺少页面 $required" >&2
    fail=1
  fi
done

if [[ "$fail" -ne 0 ]]; then
  exit 1
fi

echo "  页面数: $pages · 产物体积: $(du -sh "$DIST" | cut -f1)"
echo "==> 站点验收通过"
