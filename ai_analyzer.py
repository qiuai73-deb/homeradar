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

def repair_truncated_json(json_str):
    """
    如果 JSON 因为 token 限制导致结尾被截断，尝试自动补全闭合符号
    """
    json_str = json_str.strip()
    
    # 如果结尾不是 } 或 ]，说明被截断了，尝试补全
    if not json_str.endswith('}'):
        # 移除最后一个不完整的项（寻找最后一个完整的对象结尾 } 或 ,）
        last_comma = json_str.rfind(',')
        if last_comma != -1:
            json_str = json_str[:last_comma]
        
        # 补齐未闭合的括号
        open_brackets = json_str.count('[') - json_str.count(']')
        open_braces = json_str.count('{') - json_str.count('}')
        
        json_str += ']' * max(0, open_brackets)
        json_str += '}' * max(0, open_braces)
        
    return json_str

def clean_json_string(raw_text):
    """从 AI 输出中提取 JSON 文本"""
    # 优先寻找 ```json ... ``` 块
    json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw_text, re.DOTALL)
    if json_match:
        return json_match.group(1).strip()
    
    # 否则寻找第一个 { 到最后一个 } 之间的内容
    start_idx = raw_text.find('{')
    end_idx = raw_text.rfind('}')
    if start_idx != -1 and end_idx != -1:
        return raw_text[start_idx:end_idx+1].strip()
        
    return raw_text.strip()

def analyze_news(articles, prompt_text=""):
    if not articles:
        return ("暂无新闻数据", [], [])

    # 🔹 关键优化：按优先级/去重筛选，最多只发前 60 条核心新闻给 AI
    # 150 条全文太大，极易超出返回 token 上限导致 JSON 被切断
    selected_articles = articles[:60]

    # 简化输入字段，进一步节省 token
    simplified_articles = [
        {"title": a.get("title", ""), "source": a.get("source", ""), "url": a.get("url", "")}
        for a in selected_articles
    ]

    text_to_analyze = json.dumps(simplified_articles, ensure_ascii=False)

    default_system_prompt = """你是一名高级财经情报分析师。
【核心任务】
1. 强制标题翻译：所有新闻的 "title" 必须彻底翻译为地道的中文！
2. 精简摘要："summary" 字段用 1 句精炼中文提炼（30字以内）。
3. 全局宏观研判："summary_analysis" 字段用 2-3 段中文写出当前市场主线逻辑与关键信号。

【输出格式】
必须严格只返回纯 JSON 对象，格式如下：
{
  "summary_analysis": "中文研判...",
  "important": [{"title": "中文标题", "url": "URL", "summary": "摘要", "source": "来源"}],
  "interest": [{"title": "中文标题", "url": "URL", "summary": "摘要", "source": "来源"}]
}"""

    system_content = prompt_text if prompt_text else default_system_prompt

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system_content},
                {"role": "user", "content": f"请分析以下新闻并返回纯 JSON（控制精简输出，限制 important 最多10条，interest 最多10条）：\n{text_to_analyze}"}
            ],
            temperature=0.3,
            max_tokens=4000  # 🔹 提升单次最大输出字数上限
        )
        
        raw_output = response.choices[0].message.content.strip()

        # 1. 提取 JSON 文本
        json_str = clean_json_string(raw_output)
        
        # 2. 尝试标准解析
        try:
            result = json.loads(json_str)
        except json.JSONDecodeError as e:
            print(f"⚠️ 第一次解析失败: {e}，尝试进行智能 JSON 截断修复...")
            # 3. 尝试修复截断的 JSON
            repaired_str = repair_truncated_json(json_str)
            try:
                result = json.loads(repaired_str)
                print("✅ 截断修复成功！")
            except Exception as e2:
                print(f"❌ 修复后依然解析失败: {e2}")
                return ("⚠️ AI 输出内容过长被截断，未能完成 JSON 解析。", [], [])

        # 安全提取字段
        summary_analysis = result.get("summary_analysis", "AI 未生成全局研判。")
        important_news = result.get("important", [])
        interest_news = result.get("interest", [])

        if not isinstance(important_news, list): important_news = []
        if not isinstance(interest_news, list): interest_news = []

        return summary_analysis, important_news, interest_news

    except Exception as e:
        print(f"❌ 请求 AI 过程报错: {e}")
        return (f"⚠️ AI 分析过程异常: {e}", [], [])
