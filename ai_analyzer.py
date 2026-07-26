import os
import json
from openai import OpenAI

def analyze_news(news_items, custom_prompt=""):
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("⚠️ 未检测到 OPENAI_API_KEY，跳过 AI 分析")
        return news_items[:10], news_items[10:20]

    client = OpenAI(
        api_key=api_key,
        base_url=os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com")
    )

    system_prompt = custom_prompt if custom_prompt else "你是一个新闻分析助手。"

    # 1. 限制发送给 AI 的数据量（避免输入过大，比如只挑选关键字段传给 AI）
    simplified_news = [
        {"title": item.get("title"), "source": item.get("source"), "url": item.get("url")}
        for item in news_items
    ]
    news_text = json.dumps(simplified_news, ensure_ascii=False)

    try:
        response = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "deepseek-chat"),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"请分析以下新闻：\n{news_text}"}
            ],
            max_tokens=4000, # 👈 显式设置较高的 max_tokens，防止 AI 回复被切断
            response_format={"type": "json_object"}
        )
        
        result_content = response.choices[0].message.content

        # 2. 解析 JSON
        result_data = json.loads(result_content)
        important = result_data.get("important", [])
        interest = result_data.get("interest", [])

        return important, interest

    except json.JSONDecodeError as e:
        print(f"❌ AI 返回的 JSON 被截断或不完整: {e}")
        print("💡 建议：在 Prompt 中让 AI 控制输出数量（如重磅新闻不超过10条）。")
        return news_items[:10], news_items[10:20]
    except Exception as e:
        print(f"❌ AI 分析过程报错: {e}")
        return news_items[:10], news_items[10:20]
