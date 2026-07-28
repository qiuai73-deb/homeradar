import os
import json
import feedparser
from ai_analyzer import analyze_news
"""
每日抓取国内新闻
通过 RSS 聚合（从 GitHub Actions 美国服务器运行）
"""
import hashlib
from datetime import datetime, timezone
from pathlib import Path

# ========== 新闻源配置 ==========
SOURCES = {
    "CCTV": {
        "name": "CCTV",
        "name_cn": "央视新闻",
        "rss": "https://plink.anyfeeder.com/weixin/cctvnewscenter",
    },
    "zaobao": {
        "name": "zaobao",
        "name_cn": "联合申报",
        "rss": "https://plink.anyfeeder.com/zaobao/realtime/china",
    },
    "caixin": {
        "name": "caixinl",
        "name_cn": "财新",
        "rss": "https://quanwenrss.com/caixin",
    },
    "wallstreetcn": {
        "name": "wallstreetcn-hot",
        "name_cn": "华尔街见闻",
        "url": "https://wallstreetcn.com/news/shares",
    },
    "cls": {
        "name": "cls-hot",
        "name_cn": "财联社热门",
        "url": "https://www.cls.cn/depth?id=1003",
    },
    "phoenix": {
        "name": "phoenix",
        "name_cn": "凤凰网",
        "rss": "https://news.ifeng.com",
    },
}

OUTPUT_DIR = Path(__file__).parent
MAX_ARTICLES = 10  # 每个源最多取多少条


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
                "source": config["name_cn"],  # 👈 将新闻来源中文名写入数据中！
            })
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

    # 2. 调用 AI 分析函数（解包接收 3 个返回值：全局总结段落、重磅新闻列表、感兴趣新闻列表）
    summary_analysis, important_news, interest_news = analyze_news(all_articles, prompt_text)

    # 3. 构造符合前端渲染的 JSON 结构（添加 summary_analysis 字段）
    json_path = OUTPUT_DIR / "news.json"
    json_data = {
        "updated": datetime.now(timezone.utc).isoformat(),
        "updated_beijing": datetime.now().strftime("%Y-%m-%d %H:%M 北京时间"),  # 新增这一行
        "summary_analysis": summary_analysis,  # 👈 【核心新增】全局 AI 宏观分析与研判总结段落
        "important": important_news,             # 包含 source 信息的重磅新闻列表
        "interest": interest_news,               # 包含 source 信息的兴趣新闻列表
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
