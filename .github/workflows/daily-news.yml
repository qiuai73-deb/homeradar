import os
import json
import feedparser
import requests  # 👈 新增：用于抓取普通网页 HTML
from bs4 import BeautifulSoup  # 👈 新增：用于解析普通网页内容
from ai_analyzer import analyze_news
"""
每日抓取国内新闻
通过 RSS 聚合与网页解析（从 GitHub Actions 美国服务器运行）
"""
import hashlib
from datetime import datetime, timezone
from pathlib import Path

# ===== 推送通知 =====
notification:
  enabled: true                      # 打开推送通知

# ========== 新闻源统一配置 ==========
# 将两者合并为一个大字典，但通过 type 字段来区分抓取逻辑，并统一使用 'url' 键
SOURCES = {
    # --- RSS 抓取通道 ---
    "CCTV": {
        "name": "CCTV",
        "name_cn": "央视新闻",
        "url": "https://plink.anyfeeder.com/weixin/cctvnewscenter",
        "type": "rss"
    },
    "zaobao": {
        "name": "zaobao",
        "name_cn": "联合早报",
        "url": "https://plink.anyfeeder.com/zaobao/realtime/china",
        "type": "rss"
    },
    "caixin": {
        "name": "caixinl",
        "name_cn": "财新",
        "url": "https://quanwenrss.com/caixin",
        "type": "rss"
    },
    # --- 普通网页抓取通道 ---
    "wallstreetcn": {
        "name": "wallstreetcn-hot",
        "name_cn": "华尔街见闻",
        "url": "https://wallstreetcn.com/news/shares",
        "type": "web"
    },
    "cls": {
        "name": "cls-hot",
        "name_cn": "财联社热门",
        "url": "https://www.cls.cn/depth?id=1003",
        "type": "web"
    },
    "phoenix": {
        "name": "phoenix",
        "name_cn": "凤凰网",
        "url": "https://news.ifeng.com",
        "type": "web"
    },
}

OUTPUT_DIR = Path(__file__).parent
MAX_ARTICLES = 10  # 每个源最多取多少条


def fetch_source(key, config):
    """抓取单个新闻源（自适应支持 RSS 和普通 Web 网页）"""
    print(f"  正在抓取 {config['name_cn']} ({config['name']})...")
    articles = []
    
    try:
        # ======= 核心修改：分流处理 =======
        if config["type"] == "rss":
            # 1. RSS 解析逻辑
            feed = feedparser.parse(config["url"])
            for entry in feed.entries[:MAX_ARTICLES]:
                articles.append({
                    "title": entry.get("title", ""),
                    "url": entry.get("link", ""),
                    "published": entry.get("published", ""),
                    "summary": entry.get("summary", ""),
                    "source": config["name_cn"],
                })
        
        elif config["type"] == "web":
            # 2. 网页 HTML 解析逻辑（防止直接读取 'rss' 报错）
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            response = requests.get(config["url"], headers=headers, timeout=10)
            response.encoding = 'utf-8'
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 💡 针对不同网页的简易 A 标签新闻提取逻辑（避免获取到 0 篇）
            links = soup.find_all('a')
            for link in links:
                title = link.get_text().strip()
                url = link.get('href', '')
                
                # 过滤掉字数太少、没有跳转链接或只是内部导航的无效链接
                if len(title) > 8 and url.startswith('http') and not any(x in title for x in ["关于我们", "版权声明", "隐私政策"]):
                    articles.append({
                        "title": title,
                        "url": url,
                        "published": datetime.now().strftime("%Y-%m-%d"),
                        "summary": title,
                        "source": config["name_cn"],
                    })
                    if len(articles) >= MAX_ARTICLES:
                        break

        print(f"  ✅ {config['name_cn']}: 获取到 {len(articles)} 篇文章")
        return articles
        
    except Exception as e:
        print(f"  ❌ {config['name_cn']}: 抓取失败 - {e}")
        return []


def generate_markdown(all_data):
    """生成可读的 Markdown 摘要"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M 北京时间")
    print(f"生成的更新时间: {now}")  # 调试输出
    lines = [
        f"# 📰 国内新闻摘要",
        f"**更新时间：{now}**",
        "",
        "> 来源：国内媒体",
        "",
        "---",
        "",
    ]

    emoji_map = {"CCTV": "🔴", "zaobao": "🟢", "caixin": "🔵", "wallstreetcn": "🟡", "phoenix": "🟠", "cls": "🟣"}

    for key, articles in all_data.items():
        cfg = SOURCES[key]
        emoji = emoji_map.get(key, "📌")
        lines.append(f"## {emoji} {cfg['name_cn']} ({cfg['name']})")
        lines.append("")
        if not articles:
            lines.append("> ⚠️ 本次未获取到文章")
            lines.append("")
            continue
        for i, a in enumerate(articles, 1):
            title = a["title"].strip()
            title = title.split(" - ")[0].strip()
            url = a["url"]
            lines.append(f"{i}. [{title}]({url})")
        lines.append("")

    lines.append("---")
    lines.append(f"*自动生成于 {now}*")
    return "\n".join(lines)


def main():
    print(f"🚀 开始抓取新闻... ({datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')})")
    print()

    all_data = {}
    for key, config in SOURCES.items():
        articles = fetch_source(key, config)
        all_data[key] = articles

    # 1. 收集所有抓取到的文章到一个总列表里面
    all_articles = []
    for key in SOURCES:
        all_articles.extend(all_data[key])

    # ------------------ 🔹 读取同目录下的 Prompt 文件 ------------------
    prompt_path = OUTPUT_DIR / "ai_analysis_prompt.txt"
    prompt_text = ""
    if prompt_path.exists():
        with open(prompt_path, "r", encoding="utf-8") as f:
            prompt_text = f.read().strip()
        print(f"📄 成功读取分析 Prompt（共 {len(prompt_text)} 字）")
    else:
        print("⚠️ 未找到 ai_analysis_prompt.txt，将使用默认 Prompt进行分析")
        
    print(f"开始对 {len(all_articles)} 篇文章进行 AI 分析与宏观总结...")

    # 2. 调用 AI 分析函数
    summary_analysis, important_news, interest_news = analyze_news(all_articles, prompt_text)

    # 3. 构造符合前端渲染的 JSON 结构
    json_path = OUTPUT_DIR / "news.json"
    json_data = {
        "updated": datetime.now(timezone.utc).isoformat(),
        "updated_beijing": datetime.now().strftime("%Y-%m-%d %H:%M 北京时间"),
        "summary_analysis": summary_analysis,
        "important": important_news,
        "interest": interest_news,
        "sources": {
            key: {
                "name": SOURCES[key]["name"],
                "name_cn": SOURCES[key]["name_cn"],
                "count": len(all_data[key]),
                "articles": all_data[key],
            }
            for key in SOURCES
        }
    }

    # 4. 保存 JSON 文件
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2)

    print("✅ 带 AI 全局总结及新闻列表的 news.json 保存成功！")

    # 5. 保存 Markdown
    md_path = OUTPUT_DIR / "news.md"
    md_content = generate_markdown(all_data)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    # 统计
    total = sum(len(v) for v in all_data.values())
    print(f"\n✅ 完成！共获取 {total} 篇文章")
    print(f"   JSON: {json_path}")
    print(f"   Markdown: {md_path}")


if __name__ == "__main__":
    main()
