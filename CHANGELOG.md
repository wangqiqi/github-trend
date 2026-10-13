# Changelog

本项目遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 与 [语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### Fixed

- 每日抓取 workflow 在提交前同步重建 `data/trends.json`，避免数据已更新但趋势产物过期导致 CI `test_committed_trends_file_is_up_to_date` 失败
- GitHub Pages 相关 Actions 升至 `setup-node@v7`、`configure-pages@v6`、`upload-pages-artifact@v5`、`deploy-pages@v5`（与 Dependabot 提案一致，合并后 CI 可绿）

## [1.2.1] - 2026-10-12

### Added

- **日历缺口图例**：日历页顶部给出图例与覆盖统计，并把「没有快照」的日期分成三类 —— **真缺口**（抓取区间内的失败日）、**项目开始前**、**尚未抓取**；年度与月度分别统计，避免把「还没到」算成「缺数据」
- 日历守门新增图例存在性断言（缺口统计不能被无声删掉）

### Fixed

- 日历统计恒为 0 的 bug：`datesOfYear` 用 `getUTCFullYear() === year` 严格比较，而 `year` 来自 `slice(0, 4)` 是字符串，循环一次都没进；改为 `Number(year)`

### Notes

- 口径修正：初版把「全年天数 − 有快照天数」当作缺口，导致 2026 显示「缺 82 天（22%）」—— 其中 80 天其实尚未到来。改按抓取区间分类后：2025 区间内零缺口（71 天为项目开始前）、2026 真缺口 2 天（`2026-04-28`、`2026-10-05`）
- 文档：博客「开源项目 · GitHub 热门榜单」介绍页加了在线站点入口并纠正过期信息（每 6 小时更新、已移除的 AI 热榜段、push 触发、`main` 分支链接等），改动在 `vitepress-blog-source` 仓库

## [1.2.0] - 2026-10-12

### Added

- **日历视图**：`/calendar/` 年份总览 + `/calendar/YYYY` 十二个月历网格 —— 一天一格，有快照的日期可点进当日榜单，没有数据的日子是灰格（历史上有 API 失败与半成品写入的日子，如实呈现）
- **月度页加月历**：每月页面顶部是当月日历，下面是当月快照列表
- **站点 About 链接区**：站点 / 源码仓库 / 原始数据 / 索引 / 趋势产物 / 许可证 / raw 直链，一次给全
- **仓库 About 元数据**：description 重写、补上 homepage=`https://znza.top/github-trend/` 与 6 个 topics（对齐 planrun 等兄弟项目站）
- **脱敏证明** `tests/test_privacy.py`：全仓库扫严格凭据形态（ghp_/ghs_/github_pat_/AKIA/私钥/Slack token）、手写文件扫本机绝对路径、构建产物再扫一遍；`backups/` 不得入库；workflow 不得回显凭据；token 只允许进 `Authorization` 头
- **日历守门**：`verify-site.sh` 断言每年日历的可点日期数 == 该年数据天数，且每个链接目标页真实存在
- **跨仓库防漂移测试** `tests/test_crossrepo.py`：兄弟仓库在本机时校验博客「项目站」条目与本站 base 一致，且博客部署不依赖本仓库
- 文档补「数据到站点的自动同步链路」与「与博客站的关系」两节（含 `GITHUB_TOKEN` 提交不触发 push、失败连带跳过部署）

### Changed

- **每日归档页从 20 行月份表改为年份卡片**（每年天数 + 年历入口 + 紧凑月份链接行）
- 侧边栏年份可点进年历（年 → 月结构不变，逐日条目仍然不进侧边栏）

### Notes

- 日历刻意用 **Markdown 表格**而非 raw HTML：Markdown 链接会被 VitePress 自己的死链检查覆盖，raw HTML 的 href 不会；`verify-site.sh` 的计数守门作为第二道防线
- 脱敏结论：发布面**结构上就没有敏感数据**（只有公开 GitHub 元数据），token 从环境读、只进请求头，不进文件/日志/产物 —— 现在这一点由断言证明

## [1.1.0] - 2026-10-12

### Added

- **在线站点**：<https://znza.top/github-trend/> —— VitePress 站点，逐日榜单归档（577 天）· 月度页 · 本地搜索 · 三张趋势榜 · 数据说明；内容每次构建从 `data/` 现场生成，生成物不入库
- **趋势产物** `data/trends.json`：由全历史 JSON 聚合 Star 增速榜 / 常青榜 / 新晋榜，口径写成常量、产物无时间戳，同样数据每次结果一致（`scripts/build_trends.py`）
- **历史 JSON 回填** `scripts/backfill_export.py`：把 577 个历史 Markdown 表格反向解析成与抓取器同 schema 的 per-day JSON，全历史从此 Markdown 与 JSON 成对
- **站点部署流水线** `deploy-site.yml`：构建 → GitHub Pages，并监听抓取 workflow 的 `workflow_run`（`GITHUB_TOKEN` 的提交不触发 push 事件，只靠 `on: push` 会让站点停在旧数据）
- **站点验收**：`scripts/verify-site.sh`（生成 + 构建 + 产物断言：页数、单页体积守门、趋势页口径）· `scripts/check-site.sh`（线上四页 200 冒烟）· `scripts/verify-all.sh`（Python + 站点一次跑完）
- **博客入口**：znza.top 顶栏「项目站」与开源专栏加入 GitHub Trend 外链（改动在 `vitepress-blog-source` 仓库）

### Changed

- 仓库首次引入 Node 工具链（`package.json` + `package-lock.json` + vitepress），PlanRun 闸门随之回归标准用法（`pnpm run plan-check` 等）
- `ci.yml` 拆出独立的 `site` job（`npm ci` + 站点构建断言），与 Python 的 `verify` job 分开

### Notes

- 侧边栏刻意只到「年 → 月」：实测把 577 天全放进侧边栏会让单页 HTML 55KB → 280KB、产物 50MB → 173MB
- 历史数据缺口（约 5% 天数的 Star/Fork 段落缺失、1 天半成品）已在站点「数据说明」页如实标注

## [1.0.1] - 2026-10-12

### Changed

- **抓取 workflow 不再由 push 触发**：抓取产物是按天一份的快照且同日不覆盖，每次代码推送都会白攒出多份文件（实测一天攒出 `20261012.md` / `_01` / `_02` / `_03`）。现在只按每天 12:00 UTC 定时或手动触发；代码推送的验证仍由 `ci.yml` 负责。
- 依赖升级（dependabot）：`requests>=2.34.2` · `pyquery>=2.1.0` · `schedule>=1.2.2` · `pytest>=9.1.1` · `PyYAML>=6.0.3`；GitHub Actions 升至 `actions/checkout@v7`、`actions/setup-python@v7`

### Fixed

- `tools/cleanup.py` 与 `tools/merge_files.py` 现在会把同名 `.json` 快照一并移入备份：此前只搬 `.md`，会留下索引未曾引用的无主孤儿文件
- `tools/merge_files.py` 渲染目录时自引用，会产出重复的 `## 目录`；现改为按实际段落重新生成
- 新增 `python tools/merge_files.py <date> --force`：只有 1 个文件时也能原地重排，用于修历史上被坏脚本写坏的文件

## [1.0.0] - 2026-10-12

首个正式版本。把长期运行的抓取管道从「能跑」加固为「可验证、不脏提交、可被程序消费」。

### Added

- **机器可读产物**：每次抓取在 Markdown 旁同时写出同名 `.json` 快照，`stars`/`forks` 为整数，`description` 保留原文不转义不截断
- **`data/index.json` 全量索引**：由 `scripts/build_index.py` 生成，是数据树的纯函数（可重复运行字节一致）
- **验收体系**：`scripts/verify.sh`（compileall + pytest）与 `tests/` 套件，测试数 0 → 160
- **代码 CI**：`.github/workflows/ci.yml`，推送与 PR 都跑验收
- **Dependabot**：pip 与 github-actions 每周检查
- **网络层**：请求超时、指数退避重试（尊重 `Retry-After`）、`GITHUB_TOKEN` 鉴权
- **维护脚本** `tools/`：`cleanup.py` / `merge_files.py`，默认 dry-run，`--apply` 前先备份到 `backups/`
- 文档：英文 README 与实现对齐，新增文档防漂移测试

### Changed

- 抓取改为「全部抓完、全部校验，再原子落盘（`tmp` + `os.replace`）」；任一段为空即失败，不再写半成品
- `python scraper.py` 失败时返回非零退出码，CI 不再把失败当成功提交
- `stars`/`forks` 统一为纯整数字符串，描述按词边界截断并转义表格分隔符
- 同日重复抓取改用秒级时间戳 / 序号避让，不再覆盖既有数据
- git 操作从 `os.system` 字符串拼接改为 `subprocess` 参数列表（`gitops.py`），push 到当前分支而非硬编码 `master`
- 抓取 workflow：新增 `concurrency` 与 `timeout-minutes`，Actions 升级至 `checkout@v4` / `setup-python@v5`，启用 pip 缓存，`paths-ignore` 防止机器人提交自触发，`git add data/` 取代 `git add -A`
- README（中英）与实现对齐：定时频率、真实仓库地址、JSON 产物说明

### Removed

- **「人工智能方向热榜」空段**：自 2025-03 建仓起，577/579 个文件中该段始终为「暂无数据」
- `os.system` 拼字符串执行 git 的写法

### Fixed

- 趋势榜状态码校验从 `assert` 改为 `raise_for_status`（`python -O` 下不再失效）
- `merge_files.py` 的 `##\s+` 分割 bug：会把 `### Python` 切成孤立的 `#` 并压平标题层级
- `merge_files.py` 渲染目录时自引用，会产出重复的 `## 目录`
- `cleanup.py` 月份硬编码（2025/03、2025/04），导致 `20250424` 的冗余文件长期残留
- `.gitignore` 中 ` backups/` 因前导空格失效
- 历史文件 `data/2025/04/20250424.md` 中重复的 `## 目录`（已重排，原件备份在 `backups/`）

### Notes

- 历史 579 个 Markdown 文件不回填：不含对应 JSON，且仍可能带千分位格式，按 Sprint Out of scope 处理
- API 限流：CI 中由 `secrets.GITHUB_TOKEN` 鉴权；本地可通过同名环境变量传入
