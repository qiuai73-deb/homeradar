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
    # 1. 优先获取环境变量里的 API Key
    api_key = os.getenv("OPENAI_API_KEY")
    
    # 如果没有配置 API Key，触发保底方案，防止程序直接崩溃
    if not api_key:
        print("⚠️ 未检测到 OPENAI_API_KEY，跳过 AI 分析，默认截取前 10 条新闻")
        return news_items[:10], news_items[10:20]

    # 2. 在拿到 Key 之后再初始化客户端
    client = OpenAI(
        api_key=api_key,
        base_url=os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com")
    )
    
    # 精简数据发给 AI
    simplified_news = [
        {"id": idx, "title": item.get("title", ""), "summary": item.get("summary", "")[:100]}
        for idx, item in enumerate(news_items)
    ]

    prompt = f"""
    你是一个资深新闻总编辑。请分析以下新闻列表（包含 ID、标题、摘要）：
    {json.dumps(simplified_news, ensure_ascii=False)}

    任务 1：挑选出 10 条【对中国人最重要的新闻】。评估标准：国家政策、宏观经济、全民生活、重大社会事件。
    任务 2：挑选出 10 条【最符合用户个人兴趣的新闻】。用户兴趣偏好为：
    {USER_INTERESTS}

    必须严格返回 JSON 格式，结构如下：
    {{
        "important_news": [{"id": 0, "reason": "15字以内理由"}],
        "interest_news": [{"id": 1, "reason": "15字以内理由"}]
    }}
    """

    try:
        response = client.chat.completions.create(
            model="deepseek-chat", # 如果用 OpenAI 官方可以改为 gpt-4o-mini
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            response_format={"type": "json_object"}
        )
        result = json.loads(response.choices[0].message.content)
        
        # 匹配提取重要新闻
        important_list = []
        for item in result.get("important_news", []):
            idx = item["id"]
            if idx < len(news_items):
                news_obj = news_items[idx].copy()
                # 兼容不同爬虫的摘要字段（summary / description / content）
                news_obj["summary"] = news_obj.get("summary") or news_obj.get("description") or news_obj.get("content") or ""
                news_obj["ai_reason"] = item.get("reason", "")
                important_list.append(news_obj)

        # 匹配提取兴趣新闻
        interest_list = []
        for item in result.get("interest_news", []):
            idx = item["id"]
            if idx < len(news_items):
                news_obj = news_items[idx].copy()
                news_obj["summary"] = news_obj.get("summary") or news_obj.get("description") or news_obj.get("content") or ""
                news_obj["ai_reason"] = item.get("reason", "")
                interest_list.append(news_obj)

        return important_list, interest_list

    except Exception as e:
        print(f"⚠️ AI 调用失败，回退到默认列表: {e}")
        return news_items[:10], news_items[10:20]
