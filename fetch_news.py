import os
import json
import time
import hmac
import urllib.parse
import feedparser
import requests  # 用于抓取网页与发送钉钉通知
from bs4 import BeautifulSoup
from ai_analyzer import analyze_news
import hashlib
from datetime import datetime, timezone
from pathlib import Path

# ========== 新闻源统一配置 ==========
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
    
    # --- 普通网页抓取通道 ---
    "wallstreetcn": {
        "name": "wallstreetcn-hot",
        "name_cn": "华尔街见闻",
        "url": "https://wallstreetcn.com/news/global",
        "type": "web"
    },
    "ths": {
        "name": "ths",
        "name_cn": "同花顺",
        "url": "https://www.10jqka.com.cn",
        "type": "web"
    },
    "phoenix": {
        "name": "phoenix",
        "name_cn": "凤凰网",
        "url": "https://www.ifeng.com",
        "type": "web"
    },
    "sina": {
        "name": "sina",
        "name_cn": "新浪",
        "url": "https://finance.sina.com.cn/stock",
        "type": "web"
    },
    
}

OUTPUT_DIR = Path(__file__).parent
MAX_ARTICLES = 10  # 每个源最多取多少条


def send_dingtalk_msg(summary_analysis, important_news, interest_news):
    """加签发送钉钉机器人消息"""
    webhook_url = os.getenv("DINGTALK_WEBHOOK_URL")
    secret = os.getenv("DINGTALK_SECRET")

    if not webhook_url:
        print("⚠️ 未配置 DINGTALK_WEBHOOK_URL，跳过钉钉推送。")
        return

    # 1. 计算签名 (如果设置了密钥 Secret)
    target_url = webhook_url
    if secret:
        timestamp = str(round(time.time() * 1000))
        secret_enc = secret.encode('utf-8')
        string_to_sign = f'{timestamp}\n{secret}'
        string_to_sign_enc = string_to_sign.encode('utf-8')
        hmac_code = hmac.new(secret_enc, string_to_sign_enc, digestmod=hashlib.sha256).digest()
        sign = urllib.parse.quote_plus(base64.b64encode(hmac_code)) if 'base64' in globals() else urllib.parse.quote_plus(__import__('base64').b64encode(hmac_code))
        target_url = f"{webhook_url}&timestamp={timestamp}&sign={sign}"

    # 2. 拼接 Markdown 内容
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    md_text = f"### 📰 每日 AI 新闻深度精选 ({now_str})\n\n"

    if summary_analysis:
        md_text += f"> **🤖 AI 财经研判**：\n> {summary_analysis.strip()[:300]}...\n\n---\n\n"

    md_text += "#### 🚨 **国计民生 (TOP 新闻)**\n"
    for i, item in enumerate(important_news[:10], 1):
        title = item.get("title", "")
        url = item.get("url") or item.get("link") or "#"
        source = item.get("source", "")
        md_text += f"{i}. [{title}]({url}) `[{source}]`\n"

    md_text += "\n#### 🎯 **猜你喜欢 (精选新闻)**\n"
    for i, item in enumerate(interest_news[:10], 1):
        title = item.get("title", "")
        url = item.get("url") or item.get("link") or "#"
        source = item.get("source", "")
        md_text += f"{i}. [{title}]({url}) `[{source}]`\n"

    # 3. 发送 POST 请求
    payload = {
        "msgtype": "markdown",
        "markdown": {
            "title": f"📰 每日新闻精选 ({now_str})",
            "text": md_text
        }
    }

    try:
        resp = requests.post(target_url, json=payload, headers={"Content-Type": "application/json"}, timeout=10)
        res_data = resp.json()
        if res_data.get("errcode") == 0:
            print("🎉 钉钉消息推送成功！")
        else:
            print(f"❌ 钉钉推送失败: {res_data}")
    except Exception as e:
        print(f"❌ 钉钉推送异常: {e}")


from urllib.parse import urljoin

def fetch_source(key, config):
    """抓取单个新闻源（自适应支持 RSS 和普通 Web 网页，优化二级页面/相对路径提取）"""
    print(f"  正在抓取 {config['name_cn']} ({config['name']})...")
    articles = []
    
    try:
        if config["type"] == "rss":
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            feed = feedparser.parse(config["rss"], request_headers=headers)
            for entry in feed.entries[:MAX_ARTICLES]:
                title = entry.get("title", "").strip()
                if " - " in title:
                    title = title.rsplit(" - ", 1)[0].strip()
                articles.append({
                    "title": title,
                    "url": entry.get("link", ""),
                    "published": entry.get("published", ""),
                    "summary": entry.get("summary", ""),
                    "source": config["name_cn"],
                })
        
        elif config["type"] == "web":
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            }
            
            response = requests.get(config["url"], headers=headers, timeout=12)
            response.encoding = 'utf-8'
            soup = BeautifulSoup(response.text, 'html.parser')
            
            links = soup.find_all('a')
            seen_urls = set()

            for link in links:
                title = link.get_text().strip()
                raw_url = link.get('href', '')
                
                if not raw_url or raw_url.startswith('#') or raw_url.startswith('javascript:'):
                    continue
                
                # 1. 自动拼接补全为完整绝对路径 (例如 /articles/3712345 -> https://www.wallstreetcn.com/articles/3712345)
                full_url = urljoin(config["url"], raw_url)
                
                # 2. 排除纯根域名（防止抓回主页本身）
                if full_url.strip('/') in ["https://wallstreetcn.com", "https://www.wallstreetcn.com"]:
                    continue

                # 3. 过滤噪音标题（如导航、登录按钮、纯数字或极短标题）
                invalid_keywords = ["关于我们", "版权声明", "隐私政策", "登录", "注册", "首页", "下载App", "更多", "快讯", "实时"]
                if len(title) >= 8 and not any(k in title for k in invalid_keywords):
                    # 去重处理
                    if full_url not in seen_urls:
                        seen_urls.add(full_url)
                        articles.append({
                            "title": title,
                            "url": full_url,
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
            title = a["title"].strip().split(" - ")[0].strip()
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

    all_articles = []
    for key in SOURCES:
        all_articles.extend(all_data[key])

    prompt_path = OUTPUT_DIR / "ai_analysis_prompt.txt"
    prompt_text = ""
    if prompt_path.exists():
        with open(prompt_path, "r", encoding="utf-8") as f:
            prompt_text = f.read().strip()
        print(f"📄 成功读取分析 Prompt（共 {len(prompt_text)} 字）")
    else:
        print("⚠️ 未找到 ai_analysis_prompt.txt，将使用默认 Prompt进行分析")
        
    print(f"开始对 {len(all_articles)} 篇文章进行 AI 分析与宏观总结...")

    # 1. 调用 AI 分析
    summary_analysis, important_news, interest_news = analyze_news(all_articles, prompt_text)

    # 2. 构造 json 结构并保存
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

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2)

    print("✅ 带 AI 全局总结及新闻列表的 news.json 保存成功！")

    # 3. 保存 Markdown
    md_path = OUTPUT_DIR / "news.md"
    md_content = generate_markdown(all_data)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    # 4. 📢 关键步骤：发送钉钉推送
    send_dingtalk_msg(summary_analysis, important_news, interest_news)

    total = sum(len(v) for v in all_data.values())
    print(f"\n✅ 完成！共获取 {total} 篇文章")


if __name__ == "__main__":
    main()
