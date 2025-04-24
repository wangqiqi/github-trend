import os
import re
from datetime import datetime

def merge_files(date):
    """合并指定日期的所有文件"""
    # 获取日期目录
    year_month = date[:4] + '/' + date[4:6]
    directory = os.path.join('data', year_month)
    
    # 获取该目录下所有文件
    files = os.listdir(directory)
    
    # 筛选出指定日期的文件
    target_files = [f for f in files if f.startswith(date)]
    
    if not target_files:
        print(f"未找到 {date} 的文件")
        return
    
    # 按时间戳排序
    target_files.sort()
    
    # 读取所有文件内容
    all_content = {}
    for file in target_files:
        file_path = os.path.join(directory, file)
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            # 提取每个部分的内容
            sections = re.split(r'##\s+', content)
            for section in sections[1:]:  # 跳过标题部分
                title = section.split('\n')[0].strip()
                all_content[title] = section
    
    # 创建新文件
    new_file = os.path.join(directory, f"{date}.md")
    with open(new_file, 'w', encoding='utf-8') as f:
        # 写入标题
        f.write(f"# GitHub 热门榜单 {date} ({datetime.now().strftime('%H:%M:%S')})\n\n")
        f.write("## 目录\n\n")
        f.write("- [每日 Star 最多的仓库](#每日-star-最多的仓库)\n")
        f.write("- [每日 Fork 最多的仓库](#每日-fork-最多的仓库)\n")
        f.write("- [每日趋势榜](#每日趋势榜)\n")
        f.write("- [人工智能方向热榜](#人工智能方向热榜)\n")
        f.write("  - [Python](#python)\n\n")
        
        # 写入各个部分
        for title, content in all_content.items():
            f.write(f"## {content}\n\n")
    
    # 删除旧文件
    for file in target_files:
        if file != f"{date}.md":
            os.remove(os.path.join(directory, file))
            print(f"已删除文件: {file}")
    
    print(f"已合并文件到: {new_file}")
    return new_file

def git_commit_push(file_path):
    """提交并推送到远程仓库"""
    date = os.path.basename(file_path).split('.')[0]
    
    # 添加文件
    os.system(f'git add {file_path}')
    
    # 提交
    os.system(f'git commit -m "Update trending repositories: {date}"')
    
    # 推送
    os.system('git push')
    
    print("已提交并推送到远程仓库")

def main():
    # 合并今天的文件
    today = datetime.now().strftime('%Y%m%d')
    merged_file = merge_files(today)
    
    if merged_file:
        # 提交到远程仓库
        git_commit_push(merged_file)

if __name__ == '__main__':
    main() 