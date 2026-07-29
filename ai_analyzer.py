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

def auto_fix_truncated_json(json_str):
    """
    当 JSON 字符串因 Token 超限被截断时，强行切掉最后一个不完整的对象并补齐括号
    """
    json_str = json_str.strip()
    
    # 找到最后一个完整对象的结束位置 }
    last_brace = json_str.rfind('}')
    if last_brace != -1:
        # 截取到最后一个完整对象
        truncated = json_str[:last_brace + 1]
        
        # 补齐可能缺失的数组和对象闭合括号
        open_brackets = truncated.count('[') - truncated.count(']')
        open_braces = truncated.count('{') - truncated.count('}')
        
        truncated += ']' * max(0, open_brackets)
        truncated += '}' * max(0, open_braces)
        return truncated
    return json_str

def analyze_news(articles, prompt_text=""):
    if not articles:
        return ("暂无新闻数据", [], [])

    # 🔹 1. 严格限制输入数量：只取前 100 条，防止 AI 输出过长导致  溢出截断！
    selected_articles = articles[:100]
    simplified_articles = [
        {"title": a.get("title", ""), "source": a.get("source", ""), "url": a.get("url", "")}
        for a in selected_articles
    ]

    text_to_analyze = json.dumps(simplified_articles, ensure_ascii=False)

    default_system_prompt = """你是一名高级财经情报分析师。
【核心任务与严格限制】
1. 强制标题翻译：所有新闻的 "title" 必须彻底翻译为地道的中文！
2. 精简摘要："summary" 字段控制在 20 字以内（1句极简说明）！
3. 数量限制："important" 列表10 条，"interest" 列表10 条！
4. 全局宏观研判："summary_analysis" 字段用 2 段中文提炼核心逻辑。

【强制格式】
必须返回合法 JSON 对象，格式如下：
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
                {"role": "user", "content": f"请分析以下新闻并返回 JSON（严禁超长，important 最多10条，interest 最多10条）：\n{text_to_analyze}"}
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
            max_tokens=8000
        )
        
        raw_output = response.choices[0].message.content.strip()

        # 尝试直接解析
        try:
            result = json.loads(raw_output)
        except json.JSONDecodeError as e:
            print(f"⚠️ 捕获到截断/格式报错 ({e})，正在启动自动补全截断修复...")
            
            # 🔹 2. 尝试智能修复被切断的 JSON
            repaired_str = auto_fix_truncated_json(raw_output)
            try:
                result = json.loads(repaired_str)
                print("✅ 截断修复成功！成功提取已生成的部分新闻")
            except Exception as e2:
                print(f"❌ 自动修复失败: {e2}")
                return ("⚠️ AI 输出了无法修复的数据，请重试。", [], [])

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
