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

# 首页必须展示最新一天的榜单（Done-when 明确要求，别让生成器哪天悄悄丢了）
latest="$(node --input-type=module -e "import fs from 'node:fs'; const i = JSON.parse(fs.readFileSync('data/index.json','utf8')); const d = i.files.map((f) => f.date).sort(); console.log(d[d.length - 1])")"
latest_fmt="${latest:0:4}-${latest:4:2}-${latest:6:2}"
grep -q "$latest_fmt" "$DIST/index.html" || fail_msg "首页没有最新一天（$latest_fmt）的榜单"
grep -q '<table' "$DIST/index.html" || fail_msg "首页没有榜单表格"

# 日历守门：可点日期数必须等于数据天数，且每个链接目标页真实存在
node_years() {
  node --input-type=module -e "import fs from 'node:fs'; const i = JSON.parse(fs.readFileSync('data/index.json','utf8')); console.log([...new Set(i.files.map((f) => f.date.slice(0, 4)))].sort().join(' '))"
}
node_days_in_year() {
  node --input-type=module -e "import fs from 'node:fs'; const i = JSON.parse(fs.readFileSync('data/index.json','utf8')); console.log(new Set(i.files.filter((f) => f.date.startsWith('$1')).map((f) => f.date)).size)"
}
for year in $(node_years); do
  page="$DIST/calendar/$year.html"
  [[ -f "$page" ]] || { fail_msg "缺少 $year 年日历页"; continue; }

  expected="$(node_days_in_year "$year")"
  links="$(grep -o "${BASE_PREFIX}daily/$year/[0-9]*/[0-9]*" "$page" | sort -u)"
  link_count="$(printf '%s\n' "$links" | grep -c . || true)"
  [[ "$link_count" -eq "$expected" ]] || fail_msg "$year 年日历可点日期 $link_count 个，数据里有 $expected 天"

  # 逐条验证链接目标存在（Markdown 链接已被 VitePress 检查，这里是第二道防线）
  while IFS= read -r target; do
    [[ -z "$target" ]] && continue
    [[ -f "$DIST/${target#"$BASE_PREFIX"}.html" ]] || fail_msg "日历链接目标不存在: $target"
  done <<< "$links"
done

# 发布面脱敏：产物里不得出现凭据形状（严格形态，误报率极低）
if grep -rEq 'ghp_[A-Za-z0-9]{36}|ghs_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{22,}|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----' "$DIST" 2>/dev/null; then
  fail_msg "构建产物里出现凭据形状的字符串"
fi

[[ "$fail" -ne 0 ]] && exit 1

echo "  页面数: $pages（逐日 $daily_pages/$days）· 最大逐日页 ${worst_kb}KB · 产物体积: $(du -sh "$DIST" | cut -f1)"
echo "==> 站点验收通过"
