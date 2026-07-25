import os
import json
from openai import OpenAI

USER_INTERESTS = """
我的兴趣方向包括：
1. 重点要关注与中国政治、经济、金融、科技相关的新闻
2. 全球财经、股市与宏观经济趋势
3. 全球AI、高科技公司
"""

def analyze_news(news_items):
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("⚠️ 未检测到 OPENAI_API_KEY，跳过 AI 分析")
        return news_items[:10], news_items[10:20]

    client = OpenAI(
        api_key=api_key,
        base_url=os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com")
    )
    
    simplified_news = [
        {
            "id": idx, 
            "title": item.get("title", ""), 
            "summary": (item.get("summary") or item.get("description") or "")[:120],
            "source": item.get("source") or item.get("source_name") or item.get("feed") or ""
        }
        for idx, item in enumerate(news_items)
    ]

    prompt = f"""
    你是一个专业的新闻总编辑兼高级同声传译。请分析以下新闻列表（包含 ID、标题、摘要、来源）：
    {json.dumps(simplified_news, ensure_ascii=False)}

    任务 1：挑选出 10 条【对中国人最重要的新闻】。
    任务 2：挑选出 10 条【最符合用户个人兴趣的新闻】。用户兴趣偏好为：
    {USER_INTERESTS}

    🚨【核心要求】：
    1. 必须将挑选出的新闻标题（title）和摘要（summary）翻译为通顺流畅的【简体中文】！
    2. 严格返回以下 JSON 格式：
    {{
        "important_news": [
            {{
                "id": 0, 
                "title_zh": "这里填翻译后的中文标题", 
                "summary_zh": "这里填翻译后的中文摘要（80字以内）", 
                "reason": "15字以内推荐理由"
            }}
        ],
        "interest_news": [
            {{
                "id": 1, 
                "title_zh": "这里填翻译后的中文标题", 
                "summary_zh": "这里填翻译后的中文摘要（80字以内）", 
                "reason": "15字以内推荐理由"
            }}
        ]
    }}
    """

    try:
        response = client.chat.completions.create(
            model="deepseek-v4-flash",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            response_format={"type": "json_object"}
        )
        
        raw_content = response.choices[0].message.content
        print("🤖 AI 返回的原始数据预览：\n", raw_content[:300]) # 方便在 Actions 里查看
        
        result = json.loads(raw_content)
        
        # 智能匹配函数：兼容各种 possible 的 key 名称
        def parse_item_list(items_data):
            parsed_list = []
            for item in items_data:
                idx = item.get("id")
                if idx is not None and isinstance(idx, int) and idx < len(news_items):
                    raw = news_items[idx]
                    
                    # 优先拿中文翻译字段，拿不到再找通用字段，最后才保底用原文
                    zh_title = item.get("title_zh") or item.get("translated_title") or item.get("title") or raw.get("title", "无标题")
                    zh_summary = item.get("summary_zh") or item.get("translated_summary") or item.get("summary") or raw.get("summary") or "暂无摘要"
                    # 提取新闻来源（兼容多种字段 key）
                    source = raw.get("source") or raw.get("source_name") or raw.get("feed") or raw.get("feed_title") or ""
                    
                    news_obj = {
                        "title": zh_title,
                        "url": raw.get("url") or raw.get("link") or "#",
                        "summary": zh_summary,
                        "source": source,  # 👈 新增保存新闻来源字段
                        "ai_reason": item.get("reason", "")
                    }
                    parsed_list.append(news_obj)
            return parsed_list

        # 兼容 JSON 返回结构
        important_raw = result.get("important_news", [])
        interest_raw = result.get("interest_news", [])

        important_list = parse_item_list(important_raw)
        interest_list = parse_item_list(interest_raw)

        print(f"✅ AI 成功解析并翻译：重磅新闻 {len(important_list)} 条，兴趣新闻 {len(interest_list)} 条")
        return important_list, interest_list

    except Exception as e:
        print(f"⚠️ AI 调用或解析失败: {e}")
        return news_items[:10], news_items[10:20]
