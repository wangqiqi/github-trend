# GitHub Trending

English | [中文](README.md)

Automatically scrape popular GitHub repositories information, including daily most starred repositories, most forked repositories, trending repositories, and AI-related trending repositories.

## Features

- Daily scraping of popular repositories on GitHub
- Data stored by year and month, with filename format YYYYMMDD.md
- Automatic updates every 6 hours, with timestamps in filenames to avoid overwriting
- Automatic scraping triggered on new pushes
- Complete repository links and descriptions, including language, star count, fork count, etc.
- Data presented in table format for better readability

## Scraped Content

- **Daily Most Starred Repositories**: TOP10 repositories sorted by star count
- **Daily Most Forked Repositories**: TOP10 repositories sorted by fork count
- **Daily Trending Repositories**: TOP10 repositories on GitHub trending page
- **AI-related Trending Repositories**:
  - **Python**: Popular repositories in Python language
  - **Deep Learning**: Popular repositories related to deep learning
  - **Machine Learning**: Popular repositories related to machine learning

## Usage

### Local Execution

1. Clone the repository:

```bash
git clone https://github.com/yourusername/github_treding.git
cd github_treding
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Run the scraper (one-time scraping):

```bash
python scraper.py
```

4. Run the scheduler (automatic scraping every 6 hours):

```bash
python scheduler.py
```

### Automatic Execution with GitHub Actions

This project is configured with GitHub Actions, which will run automatically:

- At 0:00, 6:00, 12:00, 18:00 (UTC) daily
- When there's a new push to the main or master branch
- When manually triggered

If you fork this repository, you need to modify the following:

1. Git configuration in `.github/workflows/update-trending.yml` file:
   ```yaml
   git config --global user.email "${GITHUB_ACTOR}@users.noreply.github.com"
   git config --global user.name "${GITHUB_ACTOR}"
   ```
   You can keep these configurations (they will automatically use your GitHub username) or modify them to your own email and username.

## Data Storage

All scraped data is stored in the `data` directory by year and month, for example:

```
data/
  └── 2023/
      ├── 01/
      │   ├── 20230101.md
      │   ├── 20230101_1200.md  # File with timestamp
      │   ├── 20230102.md
      │   └── ...
      ├── 02/
      │   ├── 20230201.md
      │   └── ...
      └── ...
```

## Custom Configuration

If you want to customize the scraped content or frequency, you can:

1. Modify the scraping functions in `scraper.py` to add or remove programming languages or topics of interest
2. Modify the scheduling frequency in `scheduler.py`
3. Modify the cron expression in `.github/workflows/update-trending.yml` to adjust the GitHub Actions execution frequency

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details. 