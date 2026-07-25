import os
import json
from openai import OpenAI

USER_INTERESTS = """
我的兴趣方向包括：
1. 中国与世界各国的关系
2. 财经、股市与宏观经济趋势
3. 全球AI、高科技公司
"""

def analyze_news(news_items):
    # 1. 获取 API Key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("⚠️ 未检测到 OPENAI_API_KEY，跳过 AI 分析，默认截取前 10 条新闻")
        return news_items[:10], news_items[10:20]

    client = OpenAI(
        api_key=api_key,
        base_url=os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com")
    )
    
    # 精简数据发给 AI
    simplified_news = [
        {"id": idx, "title": item.get("title", ""), "summary": (item.get("summary") or item.get("description") or "")[:120]}
        for idx, item in enumerate(news_items)
    ]

    # 在 Prompt 中要求 AI 将标题、摘要和推荐理由全部翻译为简体中文
    prompt = f"""
    你是一个资深新闻总编辑兼同声传译专家。请分析以下新闻列表（包含 ID、标题、摘要）：
    {json.dumps(simplified_news, ensure_ascii=False)}

    任务 1：挑选出 10 条【对中国人最重要的新闻】。评估标准：国家政策、宏观经济、全民生活、重大社会事件。
    任务 2：挑选出 10 条【最符合用户个人兴趣的新闻】。用户兴趣偏好为：
    {USER_INTERESTS}

    ⚠️ 核心要求：
    1. 无论原始新闻是英文还是其他语言，请必须将提取出的【标题(title)】和【摘要(summary)】全部翻译为通顺流畅的【简体中文】！
    2. 输出格式必须是严格的 JSON，结构如下：
    {{
        "important_news": [
            {{"id": 0, "title": "翻译后的中文标题", "summary": "翻译后的中文摘要", "reason": "15字以内中文推荐理由"}}
        ],
        "interest_news": [
            {{"id": 1, "title": "翻译后的中文标题", "summary": "翻译后的中文摘要", "reason": "15字以内中文推荐理由"}}
        ]
    }}
    """

    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            response_format={"type": "json_object"}
        )
        result = json.loads(response.choices[0].message.content)
        
        # 匹配提取重要新闻（优先使用 AI 翻译后的中文文本）
        important_list = []
        for item in result.get("important_news", []):
            idx = item.get("id")
            if idx is not None and isinstance(idx, int) and idx < len(news_items):
                raw = news_items[idx]
                news_obj = {
                    "title": item.get("title") or raw.get("title", "无标题"),  # 优先取 AI 翻译的中文标题
                    "url": raw.get("url") or raw.get("link") or "#",
                    "summary": item.get("summary") or raw.get("summary") or "暂无摘要",  # 优先取 AI 翻译的中文摘要
                    "ai_reason": item.get("reason", "")
                }
                important_list.append(news_obj)

        # 匹配提取兴趣新闻（优先使用 AI 翻译后的中文文本）
        interest_list = []
        for item in result.get("interest_news", []):
            idx = item.get("id")
            if idx is not None and isinstance(idx, int) and idx < len(news_items):
                raw = news_items[idx]
                news_obj = {
                    "title": item.get("title") or raw.get("title", "无标题"),
                    "url": raw.get("url") or raw.get("link") or "#",
                    "summary": item.get("summary") or raw.get("summary") or "暂无摘要",
                    "ai_reason": item.get("reason", "")
                }
                interest_list.append(news_obj)

        return important_list, interest_list

    except Exception as e:
        print(f"⚠️ AI 调用失败，回退到默认列表: {e}")
        return news_items[:10], news_items[10:20]
