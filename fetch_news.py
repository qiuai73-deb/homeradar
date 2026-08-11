import base64
import hashlib
import hmac
import json
import os
import time
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import feedparser
import requests  # 用于抓取网页与发送钉钉通知
from ai_analyzer import analyze_news
from bs4 import BeautifulSoup

# ========== 新闻源统一配置 ==========
SOURCES = {
    # --- RSS 抓取通道 ---
    "caixin": {
        "name": "caixin",
        "name_cn": "财新",
        "url": "https://quanwenrss.com/caixin",
        "type": "rss",
    },
    "snowball": {
        "name": "snowball",
        "name_cn": "雪球",
        "url": "https://xueqiu.com/hots/topic/rss",
        "type": "rss",
    },
    # --- 普通网页抓取通道 ---
    "ths": {
        "name": "ths",
        "name_cn": "同花顺",
        "url": "https://www.10jqka.com.cn/classic",
        "type": "web",
    },
    "phoenix": {
        "name": "phoenix",
        "name_cn": "凤凰网",
        "url": "https://www.ifeng.com",
        "type": "web",
    },
    "sina": {
        "name": "sina",
        "name_cn": "新浪",
        "url": "https://finance.sina.com.cn/stock",
        "type": "web",
    },
    "eastmoney": {
        "name": "eastmoney",
        "name_cn": "东财",
        "url": "https://finance.eastmoney.com",
        "type": "web",
    },
    "zaobao": {
        "name": "zaobao",
        "name_cn": "联合早报",
        "url": "https://www.kuzaobao.com/plus/list.php?tid=1",
        "type": "web",
    },
    # --- API 抓取通道 ---
    "wallstreetcn_hot": {
        "name": "wscn",
        "name_cn": "华尔街见闻头条",
        "url": "https://api-one-wscn.awtmt.com/apiv1/content/carousel/information-flow?channel=global&limit=10",
        "type": "api",
   },
    "wallstreetcn_lastest": {
        "name": "wscn",
        "name_cn": "华尔街见闻最新",
        "url": "https://api-one-wscn.awtmt.com/apiv1/content/information-flow?channel=global&accept=article&limit=10",
        "type": "api",
    },
    
}
OUTPUT_DIR = Path(__file__).parent
MAX_ARTICLES = 10  # 每个源最多取多少条

# ================= 新闻推送去重 =================

PUSHED_FILE = OUTPUT_DIR / "pushed_news.json"


def load_pushed_news():
    """读取历史已推送新闻"""
    if PUSHED_FILE.exists():
        try:
            with open(PUSHED_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except:
            return set()

    return set()


def save_pushed_news(news_list):
    """保存已推送新闻"""
    with open(PUSHED_FILE, "w", encoding="utf-8") as f:
        json.dump(list(news_list)[-500:], f, ensure_ascii=False, indent=2)


def filter_new_articles(articles):
    """去除已经推送过的新闻"""
    pushed = load_pushed_news()

    new_articles = []

    for item in articles:
        key = item.get("url") or item.get("title")

        if key not in pushed:
            new_articles.append(item)

    print(
        f"🆕 新新闻 {len(new_articles)} 条，历史重复 {len(articles)-len(new_articles)} 条"
    )

    return new_articles


def send_feishu_msg(important_news, interest_news):
    webhook_url = os.getenv("FEISHU_WEBHOOK_URL")
    if not webhook_url:
        print("⚠️ 未配置 FEISHU_WEBHOOK_URL，跳过消息推送。")
        return

    target_url = webhook_url
    print(f"🔗 请求 URL: {target_url}")

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    content = []

    # 标题行（加粗）
    content.append([
        {"tag": "text", "text": f"📰 每日 AI 新闻深度精选 ({now_str})", "style": ["bold"]}
    ])

    # 重要新闻区块
    content.append([
        {"tag": "text", "text": "🚨 国计民生 (TOP 新闻)", "style": ["bold"]}
    ])
    for i, item in enumerate(important_news[:8], 1):
        title = item.get("title", "")
        url = item.get("url") or item.get("link")
        if not url:
            continue  # 无链接则跳过该条
        source = item.get("source", "")
        content.append([
            {"tag": "text", "text": f"{i}. "},
            {"tag": "a", "text": title, "href": url},
            {"tag": "text", "text": f" `[{source}]`"}
        ])

    # 兴趣新闻区块
    content.append([
        {"tag": "text", "text": "🎯 猜你喜欢 (精选新闻)", "style": ["bold"]}
    ])
    for i, item in enumerate(interest_news[:8], 1):
        title = item.get("title", "")
        url = item.get("url") or item.get("link")
        if not url:
            continue
        source = item.get("source", "")
        content.append([
            {"tag": "text", "text": f"{i}. "},
            {"tag": "a", "text": title, "href": url},
            {"tag": "text", "text": f" `[{source}]`"}
        ])

    # 如果内容为空（比如所有新闻都没有链接），发一条提示
    if len(content) <= 2:   # 只有标题行和区块标题，没有新闻
        content.append([{"tag": "text", "text": "暂无新闻推送"}])

    payload = {
        "msg_type": "post",
        "content": {
            "post": {
                "zh_cn": {
                    "title": f"📰 每日新闻精选 ({now_str})",
                    "content": content
                }
            }
        }
    }

    try:
        resp = requests.post(
            target_url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        print(f"📡 HTTP 状态码: {resp.status_code}")
        print(f"📄 响应内容: {resp.text}")

        res_data = resp.json()
        if res_data.get("code") == 0:
            print("🎉 飞书消息推送成功！")
        else:
            print(f"❌ 飞书推送失败: {res_data}")
    except Exception as e:
        print(f"❌ 飞书推送异常: {e}")


def fetch_source(key, config):
    """抓取单个新闻源（支持 RSS、普通网页 Web 和 JSON API）"""
    print(f"  正在抓取 {config['name_cn']} ({config['name']})...")
    articles = []

    target_url = config.get("url") or config.get("rss")

    if not target_url:
        print(f"  ❌ {config['name_cn']}: 未配置有效的 URL")
        return []

    try:
        if config["type"] == "rss":
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            feed = feedparser.parse(target_url, request_headers=headers)
            for entry in feed.entries[:MAX_ARTICLES]:
                title = entry.get("title", "").strip()
                if " - " in title:
                    title = title.rsplit(" - ", 1)[0].strip()
                articles.append(
                    {
                        "title": title,
                        "url": entry.get("link", ""),
                        "published": entry.get("published", ""),
                        "summary": entry.get("summary", ""),
                        "source": config["name_cn"],
                    }
                )

        elif config["type"] == "api":
            # 华尔街见闻 JSON API 专用通道
            # 注意：不要用 display_time 判断新闻是否有效，因为部分新闻的 display_time 可能为 0。
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Referer": "https://wallstreetcn.com/",
                "Origin": "https://wallstreetcn.com",
                "Connection": "keep-alive",
            }

            # 使用 Session，并自动重试，适合 GitHub Actions 等网络环境
            session = requests.Session()
            response = session.get(
                target_url,
                headers=headers,
                timeout=20,
            )

            print(f"  [WSCN API] HTTP 状态码: {response.status_code}")
            print(f"  [WSCN API] Content-Type: {response.headers.get('Content-Type', '')}")

            response.raise_for_status()

            try:
                data = response.json()
            except ValueError:
                # API 偶尔可能返回 HTML / 文本错误页，直接打印前 300 字帮助排查
                print("  ❌ [WSCN API] 返回内容不是 JSON：")
                print(f"  {response.text[:300]}")
                return []

            print(f"  [WSCN API] 顶层字段: {list(data.keys()) if isinstance(data, dict) else type(data).__name__}")

            if not isinstance(data, dict):
                print("  ❌ [WSCN API] 返回 JSON 不是对象")
                return []

            api_code = data.get("code")
            print(f"  [WSCN API] API code: {api_code}")

            # 有些版本的接口没有 code，不能因此直接判定失败
            if api_code not in (None, 20000, 200):
                print(
                    f"  ❌ [WSCN API] API 返回异常: "
                    f"code={api_code}, message={data.get('message', '')}"
                )
                return []

            # 标准结构：data.items
            api_data = data.get("data") or {}
            items = []
            if isinstance(api_data, dict):
                items = api_data.get("items") or []
            elif isinstance(api_data, list):
                items = api_data

            print(f"  [WSCN API] data.items 数量: {len(items) if isinstance(items, list) else 0}")

            if not isinstance(items, list):
                print(f"  ❌ [WSCN API] items 类型异常: {type(items).__name__}")
                return []

            for item in items[:MAX_ARTICLES]:
                if not isinstance(item, dict):
                    continue

                # 当前 API：item.resource
                resource = item.get("resource")
                if not isinstance(resource, dict):
                    resource = item

                title = str(
                    resource.get("title")
                    or resource.get("title_text")
                    or resource.get("name")
                    or ""
                ).strip()

                article_url = str(
                    resource.get("uri")
                    or resource.get("url")
                    or resource.get("link")
                    or ""
                ).strip()

                # 有些 API 返回相对地址，补成完整华尔街见闻链接
                if article_url.startswith("/"):
                    article_url = urljoin("https://wallstreetcn.com", article_url)

                if not title or not article_url:
                    print(
                        "  ⚠️ [WSCN API] 跳过一条无标题/无链接的数据："
                        f"title={bool(title)}, url={bool(article_url)}"
                    )
                    continue

                # display_time 只是发布时间，不参与有效新闻判断
                display_time = resource.get("display_time")
                published = ""

                if display_time not in (None, "", 0, "0"):
                    try:
                        ts = int(float(display_time))
                        # 明确使用北京时间，避免 GitHub Actions 默认 UTC
                        from datetime import timedelta
                        beijing_tz = timezone(timedelta(hours=8))
                        published = datetime.fromtimestamp(
                            ts, tz=timezone.utc
                        ).astimezone(beijing_tz).strftime("%Y-%m-%d %H:%M:%S")
                    except (TypeError, ValueError, OSError, OverflowError):
                        published = str(display_time)

                summary = (
                    resource.get("content_short")
                    or resource.get("summary")
                    or resource.get("description")
                    or title
                )

                articles.append(
                    {
                        "title": title,
                        "url": article_url,
                        "published": published,
                        "summary": str(summary).strip(),
                        "source": config["name_cn"],
                    }
                )

            print(f"  [WSCN API] 成功解析: {len(articles)} 条")

            # 如果 API 明明返回了数据但最终为 0，打印第一条原始数据用于诊断
            if items and not articles:
                print("  ❌ [WSCN API] API 有 items，但没有成功解析任何新闻。")
                print(f"  [WSCN API] 第一条原始数据: {json.dumps(items[0], ensure_ascii=False)[:1000]}")

        elif config["type"] == "web":
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            }

            response = requests.get(target_url, headers=headers, timeout=12)
            response.encoding = "utf-8"
            soup = BeautifulSoup(response.text, "html.parser")

            links = soup.find_all("a")
            seen_urls = set()

            for link in links:
                title = link.get_text().strip()
                raw_url = link.get("href", "")

                if (
                    not raw_url
                    or raw_url.startswith("#")
                    or raw_url.startswith("javascript:")
                ):
                    continue

                full_url = urljoin(target_url, raw_url)

                if full_url.strip("/") in [
                    "https://wallstreetcn.com",
                    "https://www.wallstreetcn.com",
                ]:
                    continue

                invalid_keywords = [
                    "关于我们",
                    "版权声明",
                    "隐私政策",
                    "登录",
                    "注册",
                    "首页",
                    "下载App",
                    "更多",
                    "快讯",
                    "实时",
                ]
                if len(title) >= 8 and not any(
                    k in title for k in invalid_keywords
                ):
                    if full_url not in seen_urls:
                        seen_urls.add(full_url)
                        articles.append(
                            {
                                "title": title,
                                "url": full_url,
                                "published": datetime.now().strftime(
                                    "%Y-%m-%d"
                                ),
                                "summary": title,
                                "source": config["name_cn"],
                            }
                        )

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
    lines = [
        f"# 📰 国内新闻摘要",
        f"**更新时间：{now}**",
        "",
        "> 来源：国内媒体",
        "",
        "---",
        "",
    ]

    emoji_map = {
        "CCTV": "🔴",
        "zaobao": "🟢",
        "caixin": "🔵",
        "wallstreetcn": "🟡",
        "phoenix": "🟠",
        "cls": "🟣",
    }

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
            title = a["title"].strip().split(" - ")[0].strip()
            url = a["url"]
            lines.append(f"{i}. [{title}]({url})")
        lines.append("")

    lines.append("---")
    lines.append(f"*自动生成于 {now}*")
    return "\n".join(lines)


def main():
    print(f"🚀 开始抓取新闻...")

    all_data = {}

    for key, config in SOURCES.items():
        articles = fetch_source(key, config)
        all_data[key] = articles

    all_articles = []

    for key in SOURCES:
        all_articles.extend(all_data[key])

    # =============================
    # 去除已经推送过的新闻
    # =============================
    all_articles = filter_new_articles(all_articles)

    if not all_articles:
        print("✅ 没有新的新闻，跳过推送")
        return

    prompt_path = OUTPUT_DIR / "ai_analysis_prompt.txt"
    prompt_text = ""

    if prompt_path.exists():
        with open(prompt_path, "r", encoding="utf-8") as f:
            prompt_text = f.read().strip()

        print(f"📄 成功读取分析 Prompt（共 {len(prompt_text)} 字）")
    else:
        print("⚠️ 未找到 ai_analysis_prompt.txt，将使用默认 Prompt进行分析")

    print(f"开始对 {len(all_articles)} 篇文章进行 AI 分析与精选...")

    # 1. 调用 AI 分析（不再接收 summary_analysis）
    important_news, interest_news = analyze_news(all_articles, prompt_text)

    # 2. 构造 json 结构并保存
    json_path = OUTPUT_DIR / "news.json"

    json_data = {
        "updated": datetime.now(timezone.utc).isoformat(),
        "updated_beijing": datetime.now().strftime("%Y-%m-%d %H:%M 北京时间"),
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
        },
    }

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2)

    print("✅ 新闻列表 news.json 保存成功！")

    # 3. 保存 Markdown
    md_path = OUTPUT_DIR / "news.md"
    md_content = generate_markdown(all_data)

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    # 4. 📢 发送钉钉推送
    send_feishu_msg(important_news, interest_news)

    # =============================
    # 保存已经推送过的新闻
    # =============================
    pushed = load_pushed_news()

    for item in important_news + interest_news:
        key = item.get("url") or item.get("title")
        if key:
            pushed.add(key)

    save_pushed_news(pushed)

    print("✅ 已更新新闻去重记录")

    total = sum(len(v) for v in all_data.values())
    print(f"\n✅ 完成！共获取 {total} 篇文章")


if __name__ == "__main__":
    main()
