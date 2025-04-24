import os
import re
from datetime import datetime

def cleanup_directory(directory):
    """清理指定目录下的文件，只保留每天中午12点的文件"""
    # 获取目录下所有文件
    files = os.listdir(directory)
    
    # 按日期分组
    date_groups = {}
    for file in files:
        if not file.endswith('.md'):
            continue
            
        # 提取日期部分
        date_match = re.match(r'(\d{8})(?:_\d{4})?\.md', file)
        if not date_match:
            continue
            
        date = date_match.group(1)
        if date not in date_groups:
            date_groups[date] = []
        date_groups[date].append(file)
    
    # 处理每个日期的文件
    for date, files in date_groups.items():
        if len(files) == 1:
            # 如果只有一个文件，保留它
            continue
            
        # 查找中午12点的文件
        noon_files = [f for f in files if re.match(rf'{date}_12\d{{2}}\.md', f)]
        
        if noon_files:
            # 如果有中午12点的文件，保留最新的一个，删除其他
            keep_file = max(noon_files)
            for file in files:
                if file != keep_file:
                    os.remove(os.path.join(directory, file))
        else:
            # 如果没有中午12点的文件，保留基本文件（YYYYMMDD.md）
            base_file = f"{date}.md"
            if base_file in files:
                for file in files:
                    if file != base_file:
                        os.remove(os.path.join(directory, file))

def main():
    # 清理2025年3月和4月的文件
    months = ['2025/03', '2025/04']
    for month in months:
        directory = os.path.join('data', month)
        if os.path.exists(directory):
            print(f"清理目录: {directory}")
            cleanup_directory(directory)

if __name__ == '__main__':
    main() 