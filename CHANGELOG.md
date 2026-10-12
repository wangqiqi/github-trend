# Changelog

本项目遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 与 [语义化版本](https://semver.org/lang/zh-CN/)。

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
