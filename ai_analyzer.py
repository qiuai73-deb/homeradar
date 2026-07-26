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

    # 将新闻列表转为字符串传给 AI
    news_text = json.dumps(news_items, ensure_ascii=False)

    try:
        response = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "deepseek-chat"),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"请分析以下新闻：\n{news_text}"}
            ],
            response_format={"type": "json_object"}  # 强制 DeepSeek 返回 JSON 格式
        )
        
        # 获取 AI 返回的文本内容
        result_content = response.choices[0].message.content
        print("🤖 AI 原始返回内容：", result_content[:200]) # 打印前200字方便排查

        # 解析 JSON 字符串
        result_data = json.loads(result_content)

        # 注意：这里假设你的 txt 提示词让 AI 返回了 {"important": [...], "interest": [...]} 结构
        important = result_data.get("important", [])
        interest = result_data.get("interest", [])

        return important, interest

    except Exception as e:
        print(f"❌ AI 分析过程报错: {e}")
        # 报错时降级处理
        return news_items[:10], news_items[10:20]
