"""pytest 共享配置：把仓库根目录加入 sys.path，使测试可直接 import scraper。"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
