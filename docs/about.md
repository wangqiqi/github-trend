# 数据说明

## 相关链接

| 去哪 | 链接 | 说明 |
| --- | --- | --- |
| 本站 | <https://znza.top/github-trend/> | 在线站点（你正在看的这个） |
| 每日归档 | [每日榜单归档](/daily/) | 按天浏览全部快照 |
| 趋势榜 | [趋势榜](/trends/) | Star 增速 / 常青 / 新晋 |
| 源码仓库 | <https://github.com/wangqiqi/github-trend> | 抓取脚本与全部数据 |
| 全量索引 | [`data/index.json`](https://github.com/wangqiqi/github-trend/blob/master/data/index.json) | 每天的文件清单与同名 JSON 是否存在 |
| 趋势产物 | [`data/trends.json`](https://github.com/wangqiqi/github-trend/blob/master/data/trends.json) | 三张榜的原始数据（可复现） |
| 许可证 | [MIT](https://github.com/wangqiqi/github-trend/blob/master/LICENSE) | 数据与代码均 MIT |

原始文件走 raw 直链也可以，例如
`https://raw.githubusercontent.com/wangqiqi/github-trend/master/data/2026/10/20261012.json`。

## 数据从哪来

GitHub Actions 每天 **12:00 UTC** 抓取一次，提交到仓库 `data/` 目录；本站只是这份数据的一个视图，**页面内容以仓库为准**。

每次抓取产出四个段落：

| 段落 | 含义 |
| --- | --- |
| 每日 Star 最多的仓库 | 近一年创建、Star 数最高的 TOP10（GitHub Search API） |
| 每日 Fork 最多的仓库 | 近一年有更新、Fork 数最高的 TOP10（GitHub Search API） |
| 每日趋势榜 | GitHub Trending 页面当日 TOP10 |
| Python | Python 语言 Trending 当日 TOP10 |

> 历史早期版本还包含「人工智能方向热榜 / Deep Learning / Machine Learning」段落。该段自建仓起始终为空，已在 v1.0.0 移除；老文件里仍能看到它。

## 本站怎么自动更新

抓取到上线是全自动的，没有人值守：

```
12:00 UTC 定时抓取 → 写入 data/（Markdown + JSON）→ 重建索引 → 提交到仓库
   ⚠️ 该提交由 GITHUB_TOKEN 发出，不会触发 push 事件
   → deploy-site.yml 靠 workflow_run 接住 → 重新生成全部页面 → 部署到本站
```

两条相关约定：

- **抓取失败就整体跳过**：任一段拿不到数据时脚本非零退出，不写文件、不提交，站点也就不会带着残缺数据刷新
- **定时是 best-effort**：GitHub 的 schedule 可能比 12:00 UTC 晚若干小时落地，页面上的日期以仓库里最新那份为准

## 与博客站的关系

本站与 znza.top 主站（`vitepress-blog-source` 仓库）**构建上互不依赖**，只有一条单向外链：主站「项目站」菜单里挂着本站地址。所以本站更新不需要动主站，主站改版也不会影响这里。

## 文件与格式

```
data/
  ├── index.json              # 全量索引：每天的文件清单（含是否有同名 JSON）
  ├── trends.json             # 趋势产物（增速 / 常青 / 新晋三榜）
  └── 2026/10/
      ├── 20261011.md         # 人看的表格
      └── 20261011.json       # 程序用的快照
```

JSON 快照的结构：

```json
{
  "date": "20261011",
  "generated_at": "2026-10-11T16:41:32Z",
  "source": "scraper.py",
  "sections": [
    {
      "id": "most-starred",
      "title": "每日 Star 最多的仓库",
      "repos": [
        { "rank": 1, "name": "owner/repo", "url": "https://github.com/owner/repo",
          "description": "…", "language": "Python", "stars": 150148, "forks": 8067 }
      ]
    }
  ]
}
```

与 Markdown 的差异：JSON 里 `stars` / `forks` 是**整数**，`description` 保留原文（Markdown 里为了表格可读性会截断并转义竖线）。

## 已知数据缺口（诚实说明）

历史数据不是完美的，下面这些是真实现状，不是本站解析漏了：

- **约 5% 的天数缺 Star / Fork 两段**：那些日子 GitHub Search API 失败（未认证限流或服务抖动），当时写下的就是「暂无数据」。
- **个别早期文件缺趋势榜段**：旧版抓取流程「先建文件、再逐段追加」，中途失败会留下半成品（该缺陷已在 v1.0.0 修掉，现在抓不全就整体失败、不落盘）。
- **历史 JSON 是回填的**：`source` 为 `backfill:markdown`、`generated_at` 为 `null`，其 `description` 是当年 Markdown 里被截断过的版本。

## 趋势榜口径

趋势结果由 `scripts/build_trends.py` 生成，口径写在代码常量里并随 `data/trends.json` 一起输出：

- **增速榜**：上榜至少 3 天，按「最后 Star − 首次 Star」排序
- **常青榜**：上榜天数最多
- **新晋榜**：首次出现在最后 30 天窗口内

产物**不含时间戳**，同样的数据每次运行结果字节一致（同分按名称排序）。

## 自己拿数据

数据就在 GitHub 仓库里，任何一天都可以直接取用：

- Markdown：`data/YYYY/MM/YYYYMMDD.md`
- JSON：`data/YYYY/MM/YYYYMMDD.json`
- 索引：`data/index.json`
