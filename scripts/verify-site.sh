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

fail_msg() { echo "FAIL: $1" >&2; fail=1; }

[[ -f "$DIST/index.html" ]] || fail_msg "产物缺少 index.html"

# base 前缀必须生效，否则挂到 znza.top/github-trend/ 后资源全 404
grep -q -- "$BASE_PREFIX" "$DIST/index.html" || fail_msg "首页未带 base 前缀 $BASE_PREFIX"

pages="$(find "$DIST" -name '*.html' | wc -l | tr -d ' ')"
[[ "$pages" -ge 2 ]] || fail_msg "产物页面数异常（$pages）"

for required in index.html about.html daily/index.html trends/index.html; do
  [[ -f "$DIST/$required" ]] || fail_msg "缺少页面 $required"
done

# 逐日页必须覆盖 data/index.json 里的全部天数
days="$(node --input-type=module -e "import fs from 'node:fs'; console.log(JSON.parse(fs.readFileSync('data/index.json','utf8')).total_days)")"
daily_pages="$(find "$DIST/daily" -name '*.html' 2>/dev/null | wc -l | tr -d ' ')"
[[ "$daily_pages" -ge "$days" ]] || fail_msg "逐日页只有 $daily_pages 个，少于数据里的 $days 天"

# 体积守门：SPIKE-001 证明逐日侧边栏会把单页从 55KB 撑到 280KB
worst_bytes="$(find "$DIST/daily" -name '*.html' -printf '%s\n' | sort -rn | head -1)"
worst_kb=$(( worst_bytes / 1024 ))
[[ "$worst_kb" -lt 100 ]] || fail_msg "逐日页最大 ${worst_kb}KB，超过 100KB 守门线（侧边栏是不是退回逐日条目了？）"

# 趋势页要带上口径说明，免得榜单脱离口径被误读
grep -q '上榜至少' "$DIST/trends/index.html" || fail_msg "趋势页缺少口径说明"

[[ "$fail" -ne 0 ]] && exit 1

echo "  页面数: $pages（逐日 $daily_pages/$days）· 最大逐日页 ${worst_kb}KB · 产物体积: $(du -sh "$DIST" | cut -f1)"
echo "==> 站点验收通过"
