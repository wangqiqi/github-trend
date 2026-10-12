# GitHub Trending

English | [中文](README.md)

Automatically scrape popular GitHub repositories information, including daily most starred repositories, most forked repositories, trending repositories, and Python language trending repositories — producing both human-readable Markdown and machine-readable JSON.

## Features

- Daily scraping of popular repositories on GitHub
- Data stored by year and month, Markdown files named `YYYYMMDD.md`
- **Automatic scraping and commit every day at 12:00 UTC** (GitHub Actions); `scheduler.py` can also run locally every 6 hours
- Repeated scrapes on the same day never overwrite existing data (second-level timestamp or sequence suffix)
- Every scrape also writes a sibling `.json` snapshot, plus a full index at `data/index.json`
- Network requests use timeouts and backoff retries; an incomplete scrape is **never** committed

## Scraped Content

- **Daily Most Starred Repositories**: TOP10 repositories created within the last year, sorted by stars
- **Daily Most Forked Repositories**: TOP10 repositories pushed within the last year, sorted by forks
- **Daily Trending Repositories**: TOP10 repositories on GitHub trending page
- **Python**: TOP10 popular Python repositories

## Usage

### Local Execution

1. Clone the repository:

```bash
git clone https://github.com/wangqiqi/github-trend.git
cd github-trend
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Run the scraper (one-time scraping):

```bash
python scraper.py
```

Optionally pass a token to avoid the unauthenticated GitHub API limit of 10 requests/minute:

```bash
GITHUB_TOKEN=ghp_xxx python scraper.py
```

4. Run the scheduler (scrapes every 6 hours, long-running process):

```bash
python scheduler.py
```

### Verification and Tests

```bash
pip install -r requirements-dev.txt
./scripts/verify.sh                      # syntax check + full test suite
./scripts/verify.sh tests/test_http.py   # a single test file
```

`python scraper.py` exits non-zero on failure, so CI turns red and the commit step is skipped.

### Automatic Execution with GitHub Actions

Two workflows are configured:

- `update-trending.yml`: scrapes **daily at 12:00 UTC**; also runs on pushes to main/master (changes under `data/**`, `.dsh/**` and the READMEs are ignored so the bot's own commits cannot re-trigger it); supports manual dispatch. Only one run per branch at a time.
- `ci.yml`: runs `./scripts/verify.sh` on pushes and pull requests.

If you fork this repository, you need to modify the following:

1. Git configuration in `.github/workflows/update-trending.yml` file:
   ```yaml
   git config --global user.email "${GITHUB_ACTOR}@users.noreply.github.com"
   git config --global user.name "${GITHUB_ACTOR}"
   ```
   You can keep these configurations (they will automatically use your GitHub username) or modify them to your own email and username.

## Data Storage

Markdown data is stored in the `data` directory by year and month:

```
data/
  ├── index.json              # full index of every daily file (and whether a sibling .json exists)
  └── 2026/
      └── 10/
          ├── 20261011.md     # tables for humans
          ├── 20261011.json   # snapshot for programs
          ├── 20261012.md
          └── 20261012.json
```

Earlier versions used timestamped filenames, so you may also see legacy names such as `YYYYMMDD_1234.md` (minute), `YYYYMMDD_120000.md` (second) and `YYYYMMDD_01.md` (sequence suffix).

### Machine-readable JSON

Each scrape writes a JSON file next to the Markdown:

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
          "description": "raw description (unescaped, untruncated)",
          "language": "Python",
          "stars": 150148,
          "forks": 8067
        }
      ]
    }
  ]
}
```

Key differences from Markdown: `stars`/`forks` are **integers**, and `description` is kept raw; unparseable counts are `null`.

`data/index.json` is a pure function of the data tree (no generation timestamp), so repeated runs produce identical bytes:

```bash
python scripts/build_index.py
```

## Maintenance Scripts

The scripts under `tools/` are one-off maintenance helpers. They **default to dry-run**; pass `--apply` to actually write, and originals are backed up to `backups/` first (gitignored).

```bash
python tools/cleanup.py                      # report duplicate files for the same day
python tools/cleanup.py --month 2025/04 --apply
python tools/merge_files.py 20250424         # dry-run merge
python tools/merge_files.py 20250424 --apply
```

## Custom Configuration

If you want to customize the scraped content or frequency, you can:

1. Modify the scraping functions in `scraper.py` to add or remove programming languages or topics of interest
2. Modify the scheduling frequency in `scheduler.py`
3. Modify the cron expression in `.github/workflows/update-trending.yml` to adjust the GitHub Actions execution frequency

## Changelog

See [CHANGELOG.md](CHANGELOG.md).

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
