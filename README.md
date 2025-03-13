# GitHub 热门榜单

[English](README_EN.md) | 中文

自动抓取 GitHub 热门仓库信息，包括每日 Star 最多的仓库、Fork 最多的仓库、趋势榜和人工智能方向的热榜。

## 功能特点

- 每天抓取 GitHub 上的热门仓库信息
- 按照年份和月份存储数据，文件命名格式为 YYYYMMDD.md
- 每 6 小时自动更新一次，并在文件名中添加时间戳避免覆盖
- 支持在有新的推送时自动触发抓取
- 提供完整的仓库链接和简介，包括语言、Star 数、Fork 数等信息
- 以表格形式呈现数据，更加清晰直观

## 抓取内容

- **每日 Star 最多的仓库**：按照 Star 数量排序的 TOP10 仓库
- **每日 Fork 最多的仓库**：按照 Fork 数量排序的 TOP10 仓库
- **每日趋势榜**：GitHub 趋势榜上的 TOP10 仓库
- **人工智能方向热榜**：
  - **Python**：Python 语言热门仓库
  - **Deep Learning**：深度学习相关热门仓库
  - **Machine Learning**：机器学习相关热门仓库

## 使用方法

### 本地运行

1. 克隆仓库：

```bash
git clone https://github.com/yourusername/github_treding.git
cd github_treding
```

2. 安装依赖：

```bash
pip install -r requirements.txt
```

3. 运行抓取脚本（单次抓取）：

```bash
python scraper.py
```

4. 运行定时任务（每 6 小时自动抓取一次）：

```bash
python scheduler.py
```

### GitHub Actions 自动运行

本项目已配置 GitHub Actions，会在以下情况自动运行：

- 每天的 0:00, 6:00, 12:00, 18:00 (UTC) 定时运行
- 有新的推送到 main 或 master 分支时
- 手动触发工作流

如果您 fork 了本仓库，需要修改以下内容：

1. `.github/workflows/update-trending.yml` 文件中的 git 配置部分：
   ```yaml
   git config --global user.email "${GITHUB_ACTOR}@users.noreply.github.com"
   git config --global user.name "${GITHUB_ACTOR}"
   ```
   您可以保留这些配置（它们会自动使用您的 GitHub 用户名），或者修改为您自己的邮箱和用户名。

## 数据存储

所有抓取的数据按照年份和月份存储在 `data` 目录下，例如：

```
data/
  └── 2023/
      ├── 01/
      │   ├── 20230101.md
      │   ├── 20230101_1200.md  # 带时间戳的文件
      │   ├── 20230102.md
      │   └── ...
      ├── 02/
      │   ├── 20230201.md
      │   └── ...
      └── ...
```

## 自定义配置

如果您想自定义抓取内容或频率，可以：

1. 修改 `scraper.py` 中的抓取函数，添加或删除您感兴趣的编程语言或主题
2. 修改 `scheduler.py` 中的定时任务频率
3. 修改 `.github/workflows/update-trending.yml` 中的 cron 表达式，调整 GitHub Actions 的运行频率

## 许可证

本项目采用 MIT 许可证，详情请参阅 [LICENSE](LICENSE) 文件。
