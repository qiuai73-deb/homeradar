import hashlib
import hmac
import base64
import time
import urllib.parse
import requests

def send_feishu_msg(important_news, interest_news):
    """发送飞书机器人消息（post 富文本格式）"""
    webhook_url = os.getenv("FEISHU_WEBHOOK_URL")   # 建议改用飞书专用环境变量
    secret = os.getenv("FEISHU_SECRET")             # 飞书加签密钥（可选）

    if not webhook_url:
        print("⚠️ 未配置 FEISHU_WEBHOOK_URL，跳过飞书推送。")
        return

    # 1. 计算签名（与钉钉算法完全一致）
    target_url = webhook_url
    if secret:
        timestamp = str(round(time.time() * 1000))
        string_to_sign = f"{timestamp}\n{secret}"
        hmac_code = hmac.new(
            secret.encode("utf-8"),
            string_to_sign.encode("utf-8"),
            digestmod=hashlib.sha256
        ).digest()
        sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
        target_url = f"{webhook_url}?timestamp={timestamp}&sign={sign}"

    # 2. 构造飞书 post 消息内容（二维数组结构）
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    content = []

    # 标题行
    content.append([
        {"tag": "text", "text": f"📰 每日 AI 新闻深度精选 ({now_str})", "style": ["bold"]}
    ])
    content.append([{"tag": "text", "text": " "}])   # 空行

    # 重要新闻区块
    content.append([
        {"tag": "text", "text": "🚨 国计民生 (TOP 新闻)", "style": ["bold"]}
    ])
    for i, item in enumerate(important_news[:8], 1):
        title = item.get("title", "")
        url = item.get("url") or item.get("link") or "#"
        source = item.get("source", "")
        # 一行：序号 + 链接（标题）+ 来源
        content.append([
            {"tag": "text", "text": f"{i}. "},
            {"tag": "a", "text": title, "href": url},
            {"tag": "text", "text": f" `[{source}]`"}
        ])

    content.append([{"tag": "text", "text": " "}])   # 空行

    # 兴趣新闻区块
    content.append([
        {"tag": "text", "text": "🎯 猜你喜欢 (精选新闻)", "style": ["bold"]}
    ])
    for i, item in enumerate(interest_news[:8], 1):
        title = item.get("title", "")
        url = item.get("url") or item.get("link") or "#"
        source = item.get("source", "")
        content.append([
            {"tag": "text", "text": f"{i}. "},
            {"tag": "a", "text": title, "href": url},
            {"tag": "text", "text": f" `[{source}]`"}
        ])

    # 3. 组装飞书请求体
    payload = {
        "msg_type": "post",
        "content": {
            "post": {
                "zh_cn": {
                    "title": f"📰 每日新闻精选 ({now_str})",   # 可选标题（在消息卡片顶部显示）
                    "content": content
                }
            }
        }
    }

    # 4. 发送请求
    try:
        resp = requests.post(
            target_url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        res_data = resp.json()
        # 飞书返回码：0 表示成功，非0 则失败
        if res_data.get("code") == 0:
            print("🎉 飞书消息推送成功！")
        else:
            print(f"❌ 飞书推送失败: {res_data}")
    except Exception as e:
        print(f"❌ 飞书推送异常: {e}")
