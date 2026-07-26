import os
import json
import feedparser
from ai_analyzer import analyze_news
"""
每日抓取路透社、彭博社、华尔街日报头条
通过 Google News RSS 聚合（从 GitHub Actions 美国服务器运行）
"""
import hashlib
from datetime import datetime, timezone
from pathlib import Path

# ========== 新闻源配置 ==========
SOURCES = {
    "reuters": {
        "name": "Reuters",
        "name_cn": "路透社",
        "rss": "https://news.google.com/rss/search?q=site:reuters.com&hl=en-US&gl=US&ceid=US:en",
    },
    "bloomberg": {
        "name": "Bloomberg",
        "name_cn": "彭博社",
        "rss": "https://news.google.com/rss/search?q=site:bloomberg.com&hl=en-US&gl=US&ceid=US:en",
    },
    "wsj": {
        "name": "Wall Street Journal",
        "name_cn": "华尔街日报",
        "rss": "https://news.google.com/rss/search?q=site:wsj.com&hl=en-US&gl=US&ceid=US:en",
    },
    "ft": {
        "name": "Financial Times",
        "name_cn": "金融时报",
        "rss": "https://news.google.com/rss/search?q=site:ft.com&hl=en-US&gl=US&ceid=US:en",
    },
    "cnbc": {
        "name": "CNBC",
        "name_cn": "CNBC",
        "rss": "https://news.google.com/rss/search?q=site:cnbc.com&hl=en-US&gl=US&ceid=US:en",
    },
    "scmp": {
        "name": "South China Morning Post",
        "name_cn": "南华早报",
        "rss": "https://news.google.com/rss/search?q=site:scmp.com&hl=en-US&gl=US&ceid=US:en",
    },
    "marketwatch": {
        "name": "MarketWatch",
        "name_cn": "MarketWatch",
        "rss": "https://news.google.com/rss/search?q=site:marketwatch.com&hl=en-US&gl=US&ceid=US:en",
    },
    "yahoofinance": {
        "name": "Yahoo Finance",
        "name_cn": "雅虎财经",
        "rss": "https://news.google.com/rss/search?q=site:finance.yahoo.com&hl=en-US&gl=US&ceid=US:en",
    },
    "Zaobao": {
        "name": "Zaobao",
        "name_cn": "联合早报",
        "rss": "https://news.google.com/search?q=%E8%81%94%E5%90%88%E6%97%A9%E6%8A%A5&hl=zh-CN&gl=CN&ceid=CN%3Azh-Hans",
    },
    "BBC": {
        "name": "BBC",
        "name_cn": "BBC",
        "rss": "http://feeds.bbci.co.uk/news/rss.xml",
    },

}

OUTPUT_DIR = Path(__file__).parent
MAX_ARTICLES = 15  # 每个源最多取多少条


def fetch_source(key, config):
    """抓取单个新闻源"""
    print(f"  正在抓取 {config['name_cn']} ({config['name']})...")
    try:
        feed = feedparser.parse(config["rss"])
        articles = []
        for entry in feed.entries[:MAX_ARTICLES]:
            articles.append({
                "title": entry.get("title", ""),
                "url": entry.get("link", ""),
                "published": entry.get("published", ""),
                "summary": entry.get("summary", ""),
                "source": config["name_cn"],  # 👈 【核心关键修改】将新闻来源中文名写入数据中！
            })
        print(f"  ✅ {config['name_cn']}: 获取到 {len(articles)} 篇文章")
        return articles
    except Exception as e:
        print(f"  ❌ {config['name_cn']}: 抓取失败 - {e}")
        return []


def generate_markdown(all_data):
    """生成可读的 Markdown 摘要"""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        f"# 📰 每日财经新闻摘要",
        f"**更新时间：{now}**",
        "",
        "> 来源：路透社 (Reuters) · 彭博社 (Bloomberg) · 华尔街日报 (WSJ)",
        "",
        "---",
        "",
    ]

    emoji_map = {"reuters": "🔴", "bloomberg": "🟢", "wsj": "🔵", "ft": "🟡", "cnbc": "🟠", "scmp": "🟣", "marketwatch": "🟤", "yahoofinance": "⚪"}

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
            # 去掉 Google News 加的后缀
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

    print(f"开始对 {len(all_articles)} 篇文章进行 AI 分析...")

    # 2. 调用 AI 分析函数（进行挑选和排序）
    important_news, interest_news = analyze_news(all_articles)

    # 3. 构造符合前端渲染的 JSON 结构
    json_path = OUTPUT_DIR / "news.json"
    json_data = {
        "updated": datetime.now(timezone.utc).isoformat(),
        "important": important_news,  # 包含 source 信息的重磅新闻列表
        "interest": interest_news,    # 包含 source 信息的兴趣新闻列表
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

    print("✅ 带 AI 分析结果及新闻来源的 news.json 保存成功！")

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
