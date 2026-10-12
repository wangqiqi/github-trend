#!/usr/bin/env bash
# scripts/check-site.sh — 线上站点冒烟：确认 https://znza.top/github-trend/ 真的活着
#
# 本地验收（verify-site.sh）只能证明「构得出」，这个脚本证明「挂得上」。
# 用法: bash scripts/check-site.sh [base-url]
set -euo pipefail

BASE="${1:-${SITE_BASE:-https://znza.top/github-trend}}"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

fail=0
fail_msg() { echo "FAIL: $1" >&2; fail=1; }

fetch() {  # fetch <path> <name>
  local code
  code="$(curl -sS -L -o "$TMP/$2" -w '%{http_code}' --max-time 30 "$BASE/$1" || echo 000)"
  echo "  HTTP $code  $BASE/$1"
  [[ "$code" == "200" ]] || fail_msg "$1 返回 $code"
}

echo "==> 线上冒烟: $BASE"
fetch "" index.html
fetch "daily/" daily.html
fetch "trends/" trends.html
fetch "about" about.html

echo "==> 内容断言"
grep -q 'GitHub 热门榜单' "$TMP/index.html" 2>/dev/null || fail_msg "首页没有站点标题"
grep -q -- '/github-trend/assets' "$TMP/index.html" 2>/dev/null || fail_msg "首页资源未带 base 前缀（部署路径不对）"
grep -q '每日榜单归档' "$TMP/daily.html" 2>/dev/null || fail_msg "每日索引页内容不对"
grep -q '上榜至少' "$TMP/trends.html" 2>/dev/null || fail_msg "趋势页缺少口径说明"

[[ "$fail" -ne 0 ]] && exit 1
echo "==> 线上站点正常"
