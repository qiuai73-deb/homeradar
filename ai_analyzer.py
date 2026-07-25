import os
import json
from openai import OpenAI  # 确保头部导入了 OpenAI

# 初始化客户端（DeepSeek 完全兼容 OpenAI SDK 结构）
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com") # 👈 指向 DeepSeek 的 API 地址
)

USER_INTERESTS = """
我的兴趣方向包括：
1. 中国与世界各国的关系
2. 财经、股市与宏观经济趋势
3. 全球AI、高科技公司
"""

def analyze_news_with_ai(news_items):
    """
    news_items: 爬虫抓取到的新闻列表 [ {"title": "...", "summary": "...", "url": "..."}, ... ]
    """
    # 限制输入数量，避免超出 Token 上限（可预先精简）
    simplified_news = [
        {"id": idx, "title": item.get("title", ""), "summary": item.get("summary", "")[:100]}
        for idx, item in enumerate(news_items)
    ]

    prompt = f"""
    你是一个资深的新闻总编辑和个性化资讯推荐专家。
    请分析以下新闻列表（包含 ID、标题、摘要）：

    --- 新闻列表 ---
    {json.dumps(simplified_news, ensure_ascii=False)}
    --- 结束 ---

    请完成以下两个任务，并严格以 JSON 格式输出：

    任务 1：挑选出 10 条【对中国人最重要的新闻】。评估标准包括：国家重大政策、宏观经济波动、全民生活影响、重大社会事件。
    任务 2：挑选出 10 条【最符合用户个人兴趣的新闻】。
    用户的个人兴趣偏好为：
    {USER_INTERESTS}

    输出格式必须是合法的 JSON，严格遵循以下结构（直接返回 JSON，不要 Markdown 代码块包裹）：
    {{
        "important_news": [
            {{"id": 对应新闻ID, "reason": "为什么这条新闻对中国人重要（15字以内）"}},
            ...共10条
        ],
        "interest_news": [
            {{"id": 对应新闻ID, "reason": "为什么符合用户兴趣（15字以内）"}},
            ...共10条
        ]
    }}
    """

    response = client.chat.completions.create(
        model="deepseek-v4-flash",  
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        response_format={"type": "json_object"}
    )

    try:
        result = json.loads(response.choices[0].message.content)
        
        # 根据返回的 ID 提取完整新闻实体
        important_list = []
        for item in result.get("important_news", []):
            idx = item["id"]
            news_obj = news_items[idx].copy()
            news_obj["ai_reason"] = item.get("reason", "")
            important_list.append(news_obj)

        interest_list = []
        for item in result.get("interest_news", []):
            idx = item["id"]
            news_obj = news_items[idx].copy()
            news_obj["ai_reason"] = item.get("reason", "")
            interest_list.append(news_obj)

        return important_list, interest_list

    except Exception as e:
        print(f"AI 分析失败: {e}")
        # 保底逻辑：直接截取前10条
        return news_items[:10], news_items[10:20]
