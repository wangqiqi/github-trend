---
layout: home

hero:
  name: GitHub 热门榜单
  text: 每日热门仓库的归档与趋势
  tagline: 每天 12:00 UTC 自动抓取 · Star / Fork / 趋势榜 / Python · 全历史机器可读
  actions:
    - theme: brand
      text: 数据说明
      link: /about
    - theme: alt
      text: GitHub 仓库
      link: https://github.com/wangqiqi/github-trend

features:
  - icon: 📅
    title: 每日四个榜单
    details: 每日 Star 最多 · 每日 Fork 最多 · 每日趋势榜 · Python 热榜，每天一份快照，同日不覆盖。
  - icon: 🔍
    title: 全历史可搜索
    details: 自 2025 年 3 月起逐日归档，按年 / 月分目录，站内本地搜索直达任意一天。
  - icon: 🤖
    title: 机器可读
    details: 每个 Markdown 快照都配一份同 schema 的 JSON（Star / Fork 为整数），另有全量索引与三张趋势榜。
  - icon: 📈
    title: 趋势分析
    details: 由全历史数据计算 Star 增速榜、常青榜与新晋榜，口径固定、结果可复现。
---

## 这个站点是什么

把仓库里逐日累积的榜单数据发布成可浏览、可搜索的站点，数据源头永远是 GitHub 仓库里的 `data/` 目录。

- 站点结构、抓取口径与已知数据缺口：[数据说明](/about)
- 原始数据：[GitHub 仓库](https://github.com/wangqiqi/github-trend)
