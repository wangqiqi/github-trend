# GitHub 热门榜单

[English](README_EN.md) | 中文

自动抓取 GitHub 热门仓库信息，包括每日 Star 最多的仓库、Fork 最多的仓库、趋势榜和 Python 语言热榜，并同时产出人类可读的 Markdown 与机器可读的 JSON。

## 功能特点

- 每天抓取 GitHub 上的热门仓库信息
- 按年份和月份存储数据，Markdown 文件命名格式为 `YYYYMMDD.md`
- **每天 12:00 UTC 自动抓取并提交**（GitHub Actions）；本地也可以用 `scheduler.py` 每 6 小时抓一次
- 同一天重复抓取时自动避让文件名（带秒级时间戳或序号），不覆盖既有数据
- 每次抓取同时写出同名 `.json` 快照，并维护一份全量索引 `data/index.json`
- 网络请求带超时与退避重试，抓取不全 **不会** 提交半成品数据

## 抓取内容

- **每日 Star 最多的仓库**：近一年创建、Star 数最高的 TOP10 仓库
- **每日 Fork 最多的仓库**：近一年有更新、Fork 数最高的 TOP10 仓库
- **每日趋势榜**：GitHub 趋势榜上的 TOP10 仓库
- **Python**：Python 语言的热门仓库 TOP10

## 使用方法

### 本地运行

1. 克隆仓库：

```bash
git clone https://github.com/wangqiqi/github-trend.git
cd github-trend
```

2. 安装依赖：

```bash
pip install -r requirements.txt
```

3. 运行抓取脚本（单次抓取）：

```bash
python scraper.py
```

可选：带上 token 可绕开 GitHub API 未认证时 10 次/分的限流。

```bash
GITHUB_TOKEN=ghp_xxx python scraper.py
```

4. 运行定时任务（每 6 小时自动抓取一次，本地常驻）：

```bash
python scheduler.py
```

### 验收与测试

```bash
pip install -r requirements-dev.txt
./scripts/verify.sh              # 语法检查 + 全部单测
./scripts/verify.sh tests/test_http.py   # 只跑某个测试文件
```

`python scraper.py` 失败时返回非零退出码，CI 会把这一步判红，后续提交不会执行。

### GitHub Actions 自动运行

本项目已配置两个 workflow：

- `update-trending.yml`：**每天 12:00 UTC** 定时抓取，支持手动触发；同一分支同时只跑一个实例。刻意不用 push 触发——抓取产物是按天一份的快照且同日不覆盖，代码推送会白攒出多份文件；代码推送的验证由 `ci.yml` 负责。
- `ci.yml`：推送与 PR 时运行 `./scripts/verify.sh`，代码坏了会被拦下。

如果您 fork 了本仓库，需要修改以下内容：

1. `.github/workflows/update-trending.yml` 文件中的 git 配置部分：
   ```yaml
   git config --global user.email "${GITHUB_ACTOR}@users.noreply.github.com"
   git config --global user.name "${GITHUB_ACTOR}"
   ```
   您可以保留这些配置（它们会自动使用您的 GitHub 用户名），或者修改为您自己的邮箱和用户名。

## 数据存储

Markdown 数据按年份和月份存储在 `data` 目录下：

```
data/
  ├── index.json              # 全量索引（所有日期的文件清单，含同名 json 是否存在）
  └── 2026/
      └── 10/
          ├── 20261011.md     # 人看的表格
          ├── 20261011.json   # 程序用的快照
          ├── 20261012.md
          └── 20261012.json
```

早期版本用过带时间戳的文件名，因此目录里也可能看到 `YYYYMMDD_1234.md`（分钟）、`YYYYMMDD_120000.md`（秒）和 `YYYYMMDD_01.md`（避让序号）等历史命名。

### 机器可读 JSON

每次抓取会在 Markdown 旁边写一份同名 JSON：

```json
{
  "date": "20261012",
  "generated_at": "2026-10-12T08:00:00Z",
  "source": "scraper.py",
  "sections": [
    {
      "id": "most-starred",
      "title": "每日 Star 最多的仓库",
      "repos": [
        {
          "rank": 1,
          "name": "owner/repo",
          "url": "https://github.com/owner/repo",
          "description": "原始描述（不转义、不截断）",
          "language": "Python",
          "stars": 150148,
          "forks": 8067
        }
      ]
    }
  ]
}
```

与 Markdown 的关键差异：`stars`/`forks` 是**整数**（Markdown 里为了可读性保留原样），`description` 保留原文；无法解析的计数为 `null`。

`data/index.json` 是数据树的纯函数（不含生成时刻），重复运行结果一致：

```bash
python scripts/build_index.py
```

## 维护脚本

`tools/` 下是一次性维护脚本，**默认 dry-run**，加 `--apply` 才会真正写盘，且原文件先备份到 `backups/`（已在 .gitignore 中）。

```bash
python tools/cleanup.py                      # 报告同一天的多余文件
python tools/cleanup.py --month 2025/04 --apply
python tools/merge_files.py 20250424         # 演练合并
python tools/merge_files.py 20250424 --apply
```

## 自定义配置

如果您想自定义抓取内容或频率，可以：

1. 修改 `scraper.py` 中的抓取函数，添加或删除您感兴趣的编程语言或主题
2. 修改 `scheduler.py` 中的定时任务频率
3. 修改 `.github/workflows/update-trending.yml` 中的 cron 表达式，调整 GitHub Actions 的运行频率

## 变更日志

见 [CHANGELOG.md](CHANGELOG.md)。

## 许可证

本项目采用 MIT 许可证，详情请参阅 [LICENSE](LICENSE) 文件。
