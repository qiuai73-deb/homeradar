import os
import json
import re
from openai import OpenAI

# ================= 配置区 =================
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
BASE_URL = "https://api.deepseek.com/v1"
MODEL = "deepseek-chat"
# ==========================================

client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=BASE_URL)

def sanitize_json_string(json_str):
    """
    清洗 AI 返回文本中常见的非法字符（如未转义的控制字符）
    """
    json_str = json_str.strip()
    # 过滤可能导致 JSON 报错的控制字符（保留标准的 \n, \t, \r）
    json_str = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', json_str)
    return json_str

def analyze_news(articles, prompt_text=""):
    if not articles:
        return ("暂无新闻数据", [], [])

    # 精简并筛选前 60 条核心新闻发送给 AI
    selected_articles = articles[:60]
    simplified_articles = [
        {"title": a.get("title", ""), "source": a.get("source", ""), "url": a.get("url", "")}
        for a in selected_articles
    ]

    text_to_analyze = json.dumps(simplified_articles, ensure_ascii=False)

    default_system_prompt = """你是一名高级财经情报分析师。
【核心任务】
1. 强制标题翻译：所有新闻的 "title" 必须彻底翻译为地道的中文！绝对不能在 "title" 中混用英文双引号！
2. 精简摘要："summary" 字段用 1 句精炼中文提炼（30字以内）。
3. 全局宏观研判："summary_analysis" 字段用 2-3 段中文写出当前市场主线逻辑与关键信号。

【强制格式】
你必须返回合法的 JSON 对象，格式规范如下：
{
  "summary_analysis": "中文研判...",
  "important": [{"title": "中文标题", "url": "URL", "summary": "摘要", "source": "来源"}],
  "interest": [{"title": "中文标题", "url": "URL", "summary": "摘要", "source": "来源"}]
}"""

    system_content = prompt_text if prompt_text else default_system_prompt

    try:
        # 🔹 关键改动：开启 response_format={"type": "json_object"}
        # 这会强制模型从底层保证输出 100% 格式合法的 JSON 结构
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system_content},
                {"role": "user", "content": f"请分析以下新闻并返回 JSON（控制精简输出，important 最多10条，interest 最多10条）：\n{text_to_analyze}"}
            ],
            response_format={"type": "json_object"},  # 👈 核心：强制 JSON 模式
            temperature=0.3,
            max_tokens=4000
        )
        
        raw_output = response.choices[0].message.content.strip()
        cleaned_str = sanitize_json_string(raw_output)

        # 尝试标准解析
        try:
            result = json.loads(cleaned_str)
        except json.JSONDecodeError as e:
            print(f"❌ JSON 解析失败 ({e})，正在尝试容错替换未转义引号...")
            # 容错降级：如果模型依然把英文双引号写入了字符串内部，尝试正则修复
            fixed_str = re.sub(r'(?<!\\)"(?=[^:,}\]]*")', '\\"', cleaned_str)
            result = json.loads(fixed_str)

        # 安全获取字段
        summary_analysis = result.get("summary_analysis", "AI 未生成全局研判。")
        important_news = result.get("important", [])
        interest_news = result.get("interest", [])

        if not isinstance(important_news, list): important_news = []
        if not isinstance(interest_news, list): interest_news = []

        return summary_analysis, important_news, interest_news

    except Exception as e:
        print(f"❌ 请求 AI 过程报错: {e}")
        return (f"⚠️ AI 分析过程异常: {e}", [], [])
