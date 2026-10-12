#!/usr/bin/env node
/**
 * 站点内容生成器：把仓库里的 data/ 渲染成 VitePress 页面。
 *
 * 设计原则：
 *   1. **data/ 是唯一源头** —— 生成物全部 gitignore，每次构建现场重算，不存第二份真相。
 *   2. **侧边栏只到「年 → 月」** —— SPIKE-001 实测：577 条逐日侧边栏会把产物
 *      从 50MB 撑到 173MB、单页 HTML 从 55KB 涨到 280KB（VitePress 把主题配置
 *      序列化进每一页）。日期导航交给每日索引页、月度页与本地搜索。
 *   3. **链接一律写 `.md`** —— 交给 VitePress 解析与死链检查，不自己拼 URL。
 *
 * 产出：
 *   docs/daily/index.md                 全部日期索引（年 → 月）
 *   docs/daily/YYYY/MM/YYYYMMDD.md      逐日页面
 *   docs/month/YYYY-MM.md               月度页面
 *   docs/trends/index.md                三张趋势榜（来自 data/trends.json）
 *   docs/.vitepress/sidebar.generated.json
 */

import { existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..')
const DATA_DIR = join(ROOT, 'data')
const DOCS_DIR = join(ROOT, 'docs')
const REPO = 'wangqiqi/github-trend'
const RAW_BASE = `https://raw.githubusercontent.com/${REPO}/master`

const GENERATED_DIRS = [join(DOCS_DIR, 'daily'), join(DOCS_DIR, 'month'), join(DOCS_DIR, 'trends')]

// --- 小工具 ---------------------------------------------------------------

const fmtDate = (d) => `${d.slice(0, 4)}-${d.slice(4, 6)}-${d.slice(6, 8)}`
const readJson = (path) => JSON.parse(readFileSync(path, 'utf8'))
const write = (path, content) => {
  mkdirSync(dirname(path), { recursive: true })
  writeFileSync(path, content, 'utf8')
}

function writeIfChanged(path, content) {
  if (existsSync(path) && readFileSync(path, 'utf8') === content) return false
  write(path, content)
  return true
}

/** 去掉原始 md 的 H1 与「目录」段：站点已有页面标题与 VitePress 大纲，重复没意义。 */
function stripHeaderAndToc(markdown) {
  const kept = []
  let inToc = false
  for (const line of markdown.split('\n')) {
    if (/^#\s/.test(line)) continue                    // 文档 H1
    if (/^##\s+目录\s*$/.test(line)) { inToc = true; continue }
    if (inToc) {
      if (/^##\s/.test(line)) inToc = false
      else continue
    }
    kept.push(line)
  }
  return kept.join('\n').replace(/\n{3,}/g, '\n\n').trim()
}

const bar = (value, max, width = 12) => {
  if (!max || value <= 0) return ''
  return '▉'.repeat(Math.max(1, Math.round((value / max) * width)))
}

// --- 数据读取 -------------------------------------------------------------

function loadDays() {
  const indexPath = join(DATA_DIR, 'index.json')
  if (!existsSync(indexPath)) throw new Error(`缺少 ${indexPath}，先跑 python scripts/build_index.py`)

  const index = readJson(indexPath)
  const byDate = new Map()
  for (const entry of index.files) {
    // 同一天有多份历史文件时，优先基础文件（YYYYMMDD.md），否则取文件名最后的
    const current = byDate.get(entry.date)
    const isBase = entry.markdown.endsWith(`/${entry.date}.md`)
    if (!current || isBase || (!current.isBase && entry.markdown > current.markdown)) {
      byDate.set(entry.date, { ...entry, isBase })
    }
  }
  const days = [...byDate.values()].sort((a, b) => a.date.localeCompare(b.date))
  return { index, days }
}

// --- 页面渲染 -------------------------------------------------------------

function renderDailyPage(day, prev, next) {
  const source = readFileSync(join(ROOT, day.markdown), 'utf8')
  const body = stripHeaderAndToc(source)
  const date = fmtDate(day.date)
  const links = [`[Markdown](${RAW_BASE}/${day.markdown})`]
  if (day.json) links.push(`[JSON](${RAW_BASE}/${day.json})`)

  const neighbours = []
  if (prev) neighbours.push(`[← ${fmtDate(prev.date)}](/daily/${prev.date.slice(0, 4)}/${prev.date.slice(4, 6)}/${prev.date}.md)`)
  if (next) neighbours.push(`[${fmtDate(next.date)} →](/daily/${next.date.slice(0, 4)}/${next.date.slice(4, 6)}/${next.date}.md)`)

  return `---
title: ${date} 榜单
---

# ${date} 榜单

> 数据来源：GitHub Actions 每日抓取 · ${links.join(' · ')} · [数据说明](/about)

${body}

---

${neighbours.length ? `**相邻日期**：${neighbours.join(' · ')}` : ''}
`
}

function renderMonthPage(month, days) {
  const [year, mm] = [month.slice(0, 4), month.slice(4, 6)]
  const items = [...days].reverse().map((day) =>
    `- [${fmtDate(day.date)}](/daily/${day.date.slice(0, 4)}/${day.date.slice(4, 6)}/${day.date}.md)`
  )
  return `---
title: ${year}-${mm}
---

# ${year} 年 ${mm} 月

共 **${days.length}** 天。

${items.join('\n')}
`
}

function renderDailyIndex(daysByMonth) {
  const years = [...new Set([...daysByMonth.keys()].map((m) => m.slice(0, 4)))].sort().reverse()
  const total = [...daysByMonth.values()].reduce((sum, days) => sum + days.length, 0)
  const allDates = [...daysByMonth.values()].flat().map((d) => d.date).sort()

  const blocks = years.map((year) => {
    const rows = [...daysByMonth.keys()]
      .filter((m) => m.startsWith(year))
      .sort()
      .reverse()
      .map((m) => `| ${m.slice(4, 6)} 月 | ${daysByMonth.get(m).length} | [${m.slice(0, 4)}-${m.slice(4, 6)}](/month/${m.slice(0, 4)}-${m.slice(4, 6)}.md) |`)
    return `## ${year}\n\n| 月份 | 天数 | 归档 |\n| --- | --- | --- |\n${rows.join('\n')}`
  })

  return `---
title: 每日榜单归档
---

# 每日榜单归档

自 **${fmtDate(allDates[0])}** 起共 **${total}** 天，全部按天归档。用右上角搜索可直接跳到某一天（试试搜 \`2026-10-01\`）。

${blocks.join('\n\n')}
`
}

function renderTrends(trends) {
  const { leaders, thresholds } = trends

  const gainRows = leaders.gain.map((r, i) => {
    const max = leaders.gain[0]?.gain ?? 1
    return `| ${i + 1} | [${r.name}](https://github.com/${r.name}) | ${r.language} | +${r.gain.toLocaleString('en-US')} | ${bar(r.gain, max)} | ${r.gain_per_day ?? '—'} | ${r.appearances} |`
  }).join('\n')

  const evergreenRows = leaders.evergreen.map((r, i) =>
    `| ${i + 1} | [${r.name}](https://github.com/${r.name}) | ${r.language} | ${r.appearances} | ${r.last_stars?.toLocaleString('en-US') ?? '—'} |`
  ).join('\n')

  const newcomerRows = leaders.newcomers.map((r, i) =>
    `| ${i + 1} | [${r.name}](https://github.com/${r.name}) | ${r.language} | ${fmtDate(r.first_date)} | ${r.last_stars?.toLocaleString('en-US') ?? '—'} |`
  ).join('\n')

  return `---
title: 趋势榜
---

# 趋势榜

由仓库里全部每日快照聚合而成（\`scripts/build_trends.py\`），统计区间 **${fmtDate(trends.first_date)} ~ ${fmtDate(trends.last_date)}**，共 ${trends.total_days} 天、${trends.repo_count.toLocaleString('en-US')} 个仓库。

口径写在代码常量里、随产物一起输出，且**不含时间戳**：同样的数据每次运行结果一致。

- 增速榜：上榜至少 ${thresholds.min_appearances} 天，按「最后 Star − 首次 Star」排序
- 常青榜：上榜天数最多
- 新晋榜：首次出现在最后 ${thresholds.newcomer_window_days} 天窗口内（本次窗口起点 ${fmtDate(thresholds.newcomer_window_start)}）

## Star 增速榜

| # | 仓库 | 语言 | Star 增长 | 幅度 | 日均 | 上榜天数 |
| --- | --- | --- | --- | --- | --- | --- |
${gainRows}

## 常青榜

| # | 仓库 | 语言 | 上榜天数 | 当前 Star |
| --- | --- | --- | --- | --- |
${evergreenRows}

## 新晋榜

| # | 仓库 | 语言 | 首次出现 | 当前 Star |
| --- | --- | --- | --- | --- |
${newcomerRows}
`
}

function renderHome(days, latest) {
  const source = readFileSync(join(ROOT, latest.markdown), "utf8")
  const body = stripHeaderAndToc(source)
  const links = [`[Markdown](${RAW_BASE}/${latest.markdown})`]
  if (latest.json) links.push(`[JSON](${RAW_BASE}/${latest.json})`)
  const first = fmtDate(days[0].date)

  return `---
layout: home

hero:
  name: GitHub 热门榜单
  text: 每日热门仓库的归档与趋势
  tagline: 每天 12:00 UTC 自动抓取 · Star / Fork / 趋势榜 / Python · 全历史机器可读
  actions:
    - theme: brand
      text: 浏览每日榜单
      link: /daily/
    - theme: alt
      text: 趋势榜
      link: /trends/

features:
  - icon: 📅
    title: 每日四个榜单
    details: 每日 Star 最多 · 每日 Fork 最多 · 每日趋势榜 · Python 热榜，每天一份快照，同日不覆盖。
  - icon: 🔍
    title: 全历史可搜索
    details: 自 ${first} 起逐日归档，按年 / 月分目录，站内本地搜索直达任意一天。
  - icon: 🤖
    title: 机器可读
    details: 每个 Markdown 快照都配一份同 schema 的 JSON（Star / Fork 为整数），另有全量索引与三张趋势榜。
  - icon: 📈
    title: 趋势分析
    details: 由全历史数据计算 Star 增速榜、常青榜与新晋榜，口径固定、结果可复现。
---

## 最新榜单 · ${fmtDate(latest.date)}

> 数据来源：GitHub Actions 每日抓取 · ${links.join(' · ')} · 完整归档见 [每日榜单](/daily/)

${body}

---

共 **${days.length}** 天历史数据（自 ${first} 起），侧边栏按「年 → 月」归档；想找谁在涨请看[趋势榜](/trends/)。
`
}

// --- 主流程 ---------------------------------------------------------------

function buildSidebar(daysByMonth) {
  const months = [...daysByMonth.keys()].sort().reverse()
  const years = [...new Set(months.map((m) => m.slice(0, 4)))].sort().reverse()
  return years.map((year) => ({
    text: year,
    collapsed: year !== years[0],
    items: months
      .filter((m) => m.startsWith(year))
      .map((m) => ({ text: `${m.slice(4, 6)} 月`, link: `/month/${m.slice(0, 4)}-${m.slice(4, 6)}` })),
  }))
}

function main() {
  const { days } = loadDays()
  if (days.length === 0) throw new Error('data/ 下没有找到任何每日数据')

  for (const dir of GENERATED_DIRS) rmSync(dir, { recursive: true, force: true })

  const daysByMonth = new Map()
  for (const day of days) {
    const month = day.date.slice(0, 6)
    if (!daysByMonth.has(month)) daysByMonth.set(month, [])
    daysByMonth.get(month).push(day)
  }

  let changed = 0

  // 首页由生成器接管：hero 文案在源码里，正文永远是最新一天的四个榜单
  if (writeIfChanged(join(DOCS_DIR, 'index.md'), renderHome(days, days[days.length - 1]))) changed++

  days.forEach((day, i) => {
    const path = join(DOCS_DIR, 'daily', day.date.slice(0, 4), day.date.slice(4, 6), `${day.date}.md`)
    if (writeIfChanged(path, renderDailyPage(day, days[i - 1], days[i + 1]))) changed++
  })

  for (const [month, monthDays] of daysByMonth) {
    const path = join(DOCS_DIR, 'month', `${month.slice(0, 4)}-${month.slice(4, 6)}.md`)
    if (writeIfChanged(path, renderMonthPage(month, monthDays))) changed++
  }

  if (writeIfChanged(join(DOCS_DIR, 'daily', 'index.md'), renderDailyIndex(daysByMonth))) changed++

  const trendsPath = join(DATA_DIR, 'trends.json')
  if (existsSync(trendsPath)) {
    if (writeIfChanged(join(DOCS_DIR, 'trends', 'index.md'), renderTrends(readJson(trendsPath)))) changed++
  } else {
    console.warn('  警告：data/trends.json 不存在，跳过趋势页（先跑 python scripts/build_trends.py）')
  }

  const sidebarPath = join(DOCS_DIR, '.vitepress', 'sidebar.generated.json')
  writeIfChanged(sidebarPath, JSON.stringify(buildSidebar(daysByMonth), null, 2) + '\n')

  console.log(`  逐日页 ${days.length} · 月度页 ${daysByMonth.size} · 索引页 1 · 趋势页 1（内容有变化 ${changed} 个文件）`)
}

main()
