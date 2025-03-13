#!/usr/bin/env python
# coding:utf-8

import time
import schedule
import os
import sys
import datetime
import logging
from scraper import job

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("github_trending.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("github_trending")

def run_job():
    """运行抓取任务"""
    logger.info("开始执行抓取任务...")
    try:
        # 使用时间戳，确保每次抓取都生成新文件
        success = job(use_git=True, use_timestamp=True)
        if success:
            logger.info("抓取任务执行完成")
        else:
            logger.error("抓取任务执行失败")
    except Exception as e:
        logger.exception(f"抓取任务执行异常: {str(e)}")

def main():
    """主函数，设置定时任务"""
    logger.info("启动定时任务调度器")
    
    # 立即执行一次
    run_job()
    
    # 每6小时执行一次
    schedule.every(6).hours.do(run_job)
    
    # 显示下一次执行时间
    next_run = schedule.next_run()
    if next_run:
        logger.info(f"下一次执行时间: {next_run.strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        while True:
            schedule.run_pending()
            time.sleep(60)  # 每分钟检查一次是否有待执行的任务
    except KeyboardInterrupt:
        logger.info("定时任务调度器已停止")
    except Exception as e:
        logger.exception(f"定时任务调度器异常: {str(e)}")

if __name__ == "__main__":
    main() 