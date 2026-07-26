import os
import requests
import json
from datetime import datetime, timedelta
import glob
import re

# ========== 可配置参数 ==========
RETENTION_DAYS = 7            # 保留最近几天的缓存
CACHE_ROOT = "cached_news"    # 缓存根目录
# =================================

API_KEY = os.environ.get("DEEPSEEK_API_KEY")
if not API_KEY:
    print("错误: 未找到 DEEPSEEK_API_KEY")
    exit(1)

# ---------- 新闻源（完全不动，照抄你原来的） ----------
# 这里保留你原有的新闻获取逻辑，我只给示例，你实际替换成自己的
news_items = [
    {"title": "OpenAI发布新模型", "url": "https://example.com/news/1", "summary": "这是通过DeepSeek提取的国外新闻正文内容..."}
]
# 如果你原来有 requests.get 抓 RSS 等，放在这里，不要改。
# ---------------------------------------------------

def extract_content(title, url):
    """调用DeepSeek提取正文（不变）"""
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "deepseek-v4-flash",
        "messages": [
            {"role": "system", "content": "请提取这段新闻的详细正文内容，返回纯文本。"},
            {"role": "user", "content": f"标题：{title}\n来源：{url}"}
        ]
    }
    try:
        resp = requests.post("https://api.deepseek.com/v1/chat/completions",
                             headers=headers, json=payload, timeout=30)
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"]
        else:
            return f"【正文提取失败】HTTP {resp.status_code}"
    except Exception as e:
        return f"【正文提取异常】{str(e)}"

def save_news_item(item):
    """保存单条新闻，按日期分目录，并返回文件路径"""
    title = item["title"]
    url = item["url"]
    today = datetime.now().strftime("%Y-%m-%d")
    day_dir = os.path.join(CACHE_ROOT, today)
    os.makedirs(day_dir, exist_ok=True)

    # 文件名：清理非法字符，取前30个字符
    safe_title = re.sub(r'[\\/*?:"<>|]', "", title)[:30]
    if not safe_title:
        safe_title = "无标题"
    filename = os.path.join(day_dir, f"{safe_title}.md")

    # 如果今天已经缓存过同名，跳过
    if os.path.exists(filename):
        print(f"跳过已存在: {filename}")
        return None

    print(f"正在处理: {title}")
    body = extract_content(title, url)

    with open(filename, "w", encoding="utf-8") as f:
        f.write(f"# {title}\n\n")
        f.write(f"**原文链接**: [{url}]({url})\n\n")
        f.write(f"**缓存时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n---\n\n")
        f.write(body)

    print(f"已缓存: {filename}")
    return filename

def generate_index():
    """生成索引页，列出所有缓存文件"""
    index_path = os.path.join(CACHE_ROOT, "index.md")
    with open(index_path, "w", encoding="utf-8") as f:
        f.write("# 📰 缓存新闻索引\n\n")
        f.write(f"最后更新：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n---\n\n")

        # 按日期倒序排列
        day_dirs = sorted(glob.glob(os.path.join(CACHE_ROOT, "????-??-??")), reverse=True)
        for day_dir in day_dirs:
            day_name = os.path.basename(day_dir)
            f.write(f"## {day_name}\n\n")
            md_files = sorted(glob.glob(os.path.join(day_dir, "*.md")))
            for md_file in md_files:
                # 读取标题（第一行 # 标题）
                with open(md_file, "r", encoding="utf-8") as mf:
                    first_line = mf.readline().strip()
                    if first_line.startswith("# "):
                        title = first_line[2:]
                    else:
                        title = os.path.basename(md_file).replace(".md", "")
                # 相对路径
                rel_path = os.path.relpath(md_file, start=CACHE_ROOT)
                f.write(f"- [{title}]({rel_path})\n")
            f.write("\n")
        f.write("---\n\n")
        f.write(f"*缓存保留最近 {RETENTION_DAYS} 天，超出自动清理。*\n")

def clean_old_caches():
    """删除超过 RETENTION_DAYS 天的缓存目录"""
    cutoff = datetime.now() - timedelta(days=RETENTION_DAYS)
    for day_dir in glob.glob(os.path.join(CACHE_ROOT, "????-??-??")):
        try:
            dir_date = datetime.strptime(os.path.basename(day_dir), "%Y-%m-%d")
            if dir_date < cutoff:
                import shutil
                shutil.rmtree(day_dir)
                print(f"已删除过期目录: {day_dir}")
        except ValueError:
            continue  # 非日期目录跳过

def main():
    # 1. 抓取并缓存新内容
    for item in news_items:
        save_news_item(item)

    # 2. 重新生成索引页
    generate_index()

    # 3. 清理过期缓存
    clean_old_caches()

    # 4. 把索引也加入 Git（工作流会提交所有变更）
    print("缓存更新完成。")

if __name__ == "__main__":
    main()
