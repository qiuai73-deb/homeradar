import os
import json
from openai import OpenAI

def analyze_news(news_items, custom_prompt=""):
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("⚠️ 未检测到 OPENAI_API_KEY，跳过 AI 分析")
        return "⚠️ 未进行 AI 分析", news_items[:10], news_items[10:20]

    client = OpenAI(
        api_key=api_key,
        base_url=os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com")
    )

    system_prompt = custom_prompt if custom_prompt else "你是一个高级财经情报分析师。"

    # 瘦身输入数据，防止 Token 溢出
    slim_news = [
        {"title": item.get("title", ""), "source": item.get("source", "")}
        for item in news_items
    ]
    news_text = json.dumps(slim_news, ensure_ascii=False)

    try:
        response = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "deepseek-chat"),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"请对以下抓取到的 {len(slim_news)} 条新闻进行深度总结分析并提炼核心逻辑：\n{news_text}"}
            ],
            max_tokens=4000,
            response_format={"type": "json_object"}
        )
        
        result_content = response.choices[0].message.content
        result_data = json.loads(result_content)

        # 提取全局分析段落以及分类新闻
        summary_analysis = result_data.get("summary_analysis", "暂无全局分析数据")
        important = result_data.get("important", [])
        interest = result_data.get("interest", [])

        return summary_analysis, important, interest

    except Exception as e:
        print(f"❌ AI 分析过程报错: {e}")
        return "❌ 分析生成失败", news_items[:10], news_items[10:20]
