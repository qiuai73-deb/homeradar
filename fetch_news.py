import os
import json
import feedparser
from datetime import datetime, timezone
from pathlib import Path
from ai_analyzer import analyze_news


# ========== 国际财经新闻源配置 ==========

SOURCES = {

    "reuters": {
        "name": "Reuters",
        "name_cn": "路透社",
        "rss": "https://news.google.com/rss/search?q=site:reuters.com&hl=en-US&gl=US&ceid=US:en",
    },

    "bloomberg": {
        "name": "Bloomberg",
        "name_cn": "彭博社",
        "rss": "https://news.google.com/rss/search?q=site:bloomberg.com+when:1d&hl=en-US&gl=US&ceid=US:en",
    },

    "wsj": {
        "name": "Wall Street Journal",
        "name_cn": "华尔街日报",
        "rss": "https://news.google.com/rss/search?q=site:wsj.com+when:1d&hl=en-US&gl=US&ceid=US:en",
    },

    "ft": {
        "name": "Financial Times",
        "name_cn": "金融时报",
        "rss": "https://news.google.com/rss/search?q=site:ft.com+when:1d&hl=en-US&gl=US&ceid=US:en",
    },

    "cnbc": {
        "name": "CNBC",
        "name_cn": "CNBC",
        "rss": "https://news.google.com/rss/search?q=site:cnbc.com+when:1d&hl=en-US&gl=US&ceid=US:en",
    },

    "economist": {
        "name": "Economist",
        "name_cn": "经济学人",
        "rss": "https://news.google.com/rss/search?q=site:economist.com+when:1d&hl=en-US&gl=US&ceid=US:en",
    },

    "BBC": {
        "name": "BBC",
        "name_cn": "BBC",
        "rss": "http://feeds.bbci.co.uk/news/rss.xml",
    },

    "NYT": {
        "name": "NYT",
        "name_cn": "纽约时报",
        "rss": "https://plink.anyfeeder.com/nytimes/cn",
    },
}


OUTPUT_DIR = Path(__file__).parent

MAX_ARTICLES = 10


# ==================================================
# 新闻去重功能
# ==================================================

PUSHED_FILE = OUTPUT_DIR / "pushed_news.json"


def load_pushed_news():
    """
    读取历史已经处理过的新闻
    """

    if PUSHED_FILE.exists():

        try:
            with open(PUSHED_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))

        except Exception:
            return set()

    return set()



def save_pushed_news(news_set):
    """
    保存历史新闻记录
    """

    with open(PUSHED_FILE, "w", encoding="utf-8") as f:

        json.dump(
            list(news_set)[-1000:],
            f,
            ensure_ascii=False,
            indent=2
        )



def get_news_key(item):
    """
    生成新闻唯一标识

    标题+URL组合，避免RSS链接变化导致重复
    """

    title = item.get("title", "")
    url = item.get("url", "")

    return title.strip() + "|" + url.strip()



def filter_new_articles(articles):

    """
    过滤已经处理过的新闻
    """

    pushed = load_pushed_news()

    new_articles = []


    for item in articles:

        key = get_news_key(item)

        if key not in pushed:

            new_articles.append(item)


    print(
        f"🆕 新新闻 {len(new_articles)} 篇，"
        f"过滤重复 {len(articles)-len(new_articles)} 篇"
    )


    return new_articles



# ==================================================
# 抓取新闻
# ==================================================

def fetch_source(key, config):

    """
    抓取单个 RSS 新闻源
    """

    print(
        f"  正在抓取 {config['name_cn']} ({config['name']})..."
    )


    articles = []


    try:

        request_headers = {

            "User-Agent":
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
            " AppleWebKit/537.36 Chrome/120 Safari/537.36"

        }


        feed = feedparser.parse(
            config["rss"],
            request_headers=request_headers
        )


        for entry in feed.entries[:MAX_ARTICLES]:


            title = entry.get(
                "title",
                ""
            ).strip()


            # 清理 Google News 后缀
            if " - " in title:

                title = title.rsplit(
                    " - ",
                    1
                )[0].strip()


            articles.append({

                "title": title,

                "url": entry.get(
                    "link",
                    ""
                ),

                "published": entry.get(
                    "published",
                    ""
                ),

                "summary": entry.get(
                    "summary",
                    ""
                ),

                "source": config["name_cn"]

            })


        print(
            f"  ✅ {config['name_cn']}: 获取 {len(articles)} 篇"
        )


        return articles


    except Exception as e:

        print(
            f"  ❌ {config['name_cn']} 抓取失败: {e}"
        )

        return []

# ==================================================
# 生成 Markdown
# ==================================================

def generate_markdown(all_data):

    """
    生成新闻 Markdown 文件
    """

    now = datetime.now().strftime(
        "%Y-%m-%d %H:%M 北京时间"
    )


    lines = [

        "# 📰 每日全球财经与国际新闻摘要",

        f"**更新时间：{now}**",

        "",

        "> 来源：路透社 · 彭博社 · 华尔街日报 · 金融时报 · CNBC · 经济学人 · BBC · 纽约时报",

        "",

        "---",

        "",

    ]


    emoji_map = {

        "reuters": "🔴",

        "bloomberg": "🟢",

        "wsj": "🔵",

        "ft": "🟡",

        "cnbc": "🟠",

        "economist": "🟣",

        "BBC": "🇬🇧",

        "NYT": "🇺🇸",

    }



    for key, articles in all_data.items():


        cfg = SOURCES[key]

        emoji = emoji_map.get(
            key,
            "📌"
        )


        lines.append(
            f"## {emoji} {cfg['name_cn']} ({cfg['name']})"
        )

        lines.append("")


        if not articles:

            lines.append(
                "> ⚠️ 本次未获取到文章"
            )

            lines.append("")

            continue



        for i, a in enumerate(
            articles,
            1
        ):

            title = a["title"]

            url = a["url"]


            lines.append(
                f"{i}. [{title}]({url})"
            )


        lines.append("")



    lines.append("---")

    lines.append(
        f"*自动生成于 {now}*"
    )


    return "\n".join(lines)





# ==================================================
# 主程序
# ==================================================

def main():

    print(
        f"🚀 开始抓取国际新闻..."
        f"({datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')})"
    )

    print()



    # 1. 抓取所有新闻源

    all_data = {}


    for key, config in SOURCES.items():

        articles = fetch_source(
            key,
            config
        )

        all_data[key] = articles



    # 2. 汇总所有新闻

    all_articles = []


    for key in SOURCES:

        all_articles.extend(
            all_data[key]
        )



    # ==================================================
    # 去除已经推送过的新闻
    # ==================================================

    all_articles = filter_new_articles(
        all_articles
    )


    if not all_articles:

        print(
            "✅ 没有新的新闻，跳过 AI 分析和推送"
        )

        return



    # 3. 读取 AI Prompt

    prompt_path = OUTPUT_DIR / "ai_analysis_prompt.txt"

    prompt_text = ""



    if prompt_path.exists():

        with open(
            prompt_path,
            "r",
            encoding="utf-8"
        ) as f:

            prompt_text = f.read().strip()


        print(
            f"📄 成功读取分析 Prompt（共 {len(prompt_text)} 字）"
        )


    else:

        print(
            "⚠️ 未找到 ai_analysis_prompt.txt，将使用默认 Prompt"
        )



    print(
        f"开始 AI 分析 {len(all_articles)} 篇新新闻..."
    )



    # 4. AI分析

    summary_analysis, important_news, interest_news = analyze_news(
        all_articles,
        prompt_text
    )



    # 5. 保存 news.json

    json_path = OUTPUT_DIR / "news.json"


    json_data = {

        "updated":
            datetime.now(timezone.utc).isoformat(),


        "updated_beijing":
            datetime.now().strftime(
                "%Y-%m-%d %H:%M 北京时间"
            ),


        "summary_analysis":
            summary_analysis,


        "important":
            important_news,


        "interest":
            interest_news,


        "sources": {

            key: {

                "name":
                    SOURCES[key]["name"],


                "name_cn":
                    SOURCES[key]["name_cn"],


                "count":
                    len(all_data[key]),


                "articles":
                    all_data[key],

            }

            for key in SOURCES

        }

    }



    with open(
        json_path,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            json_data,
            f,
            ensure_ascii=False,
            indent=2
        )



    print(
        "✅ news.json 保存成功！"
    )



    # 6. 保存 Markdown

    md_path = OUTPUT_DIR / "news.md"


    md_content = generate_markdown(
        all_data
    )


    with open(
        md_path,
        "w",
        encoding="utf-8"
    ) as f:

        f.write(
            md_content
        )



    print(
        "✅ news.md 保存成功！"
    )



    # ==================================================
    # 保存已经推送过的新闻记录
    # ==================================================

    pushed = load_pushed_news()



    for item in important_news + interest_news:

        key = get_news_key(
            item
        )


        if key:

            pushed.add(
                key
            )



    save_pushed_news(
        pushed
    )



    print(
        "✅ 已更新 pushed_news.json"
    )



    total = sum(
        len(v)
        for v in all_data.values()
    )


    print(
        f"\n✅ 全部完成！"
        f"共抓取 {total} 篇文章，"
        f"本次分析 {len(all_articles)} 篇新文章"
    )





if __name__ == "__main__":

    main()
