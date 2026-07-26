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

def clean_json_string(raw_text):
    """
    强化版 JSON 提取器：
    提取大模型返回文本中的 JSON 数据，并处理常见的格式问题。
    """
    # 1. 尝试用正则提取 Markdown 代码块中的 JSON
    json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw_text, re.DOTALL)
    if json_match:
        json_str = json_match.group(1)
    else:
        # 如果没有代码块，直接取第一个 { 到最后一个 } 之间的内容
        start_idx = raw_text.find('{')
        end_idx = raw_text.rfind('}')
        if start_idx != -1 and end_idx != -1:
            json_str = raw_text[start_idx:end_idx+1]
        else:
            json_str = raw_text

    # 2. 清理常见导致 JSON 解析失败的非法控制字符（比如未转义的换行）
    # 注意：不要简单地把所有 \n 删掉，因为 summary_analysis 里面需要 \n。
    # 这里主要依赖模型的输出能力，或者尝试用 ast.literal_eval 做终极备用方案。
    return json_str

def analyze_news(articles, prompt_text=""):
    """
    将抓取到的新闻发送给 DeepSeek 提取重磅/兴趣新闻，并做全局宏观研判
    返回 (summary_analysis, important_news_list, interest_news_list)
    """
    if not articles:
        return ("暂无新闻数据", [], [])

    # 将传入的文章列表转为简化字符串（减小 token）
    text_to_analyze = json.dumps(articles, ensure_ascii=False)

    default_system_prompt = """
你是一名高级财经情报分析师。
【核心任务】
1. 强制标题翻译：所有新闻的 "title" 必须彻底翻译为地道的中文！
2. 精简摘要："summary" 字段用 1 句精炼中文提炼（30字以内）。
3. 全局宏观研判："summary_analysis" 字段用 2-3 段中文写出当前市场主线逻辑与关键信号。

【输出格式要求】
必须严格只返回合法的 JSON 对象，不要输出任何额外的闲聊解释，格式如下：
{
  "summary_analysis": "【核心主线】...\n\n【市场与政策信号】...",
  "important": [
    {
      "title": "中文标题",
      "url": "原新闻URL",
      "summary": "中文摘要",
      "source": "新闻来源"
    }
  ],
  "interest": [
    {
      "title": "中文标题",
      "url": "原新闻URL",
      "summary": "中文摘要",
      "source": "新闻来源"
    }
  ]
}
"""
    system_content = prompt_text if prompt_text else default_system_prompt

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system_content},
                {"role": "user", "content": f"这是今天的原始新闻数据，请按要求分析并输出纯 JSON：\n{text_to_analyze}"}
            ],
            temperature=0.3,
            max_tokens=2500
        )
        
        raw_output = response.choices[0].message.content.strip()
        
        # 记录原始输出用于排查问题（可注释掉）
        # print(f"--- AI Raw Output ---\n{raw_output}\n---------------------")

        # 清洗并提取 JSON
        json_str = clean_json_string(raw_output)
        
        # 尝试解析 JSON
        try:
            result = json.loads(json_str)
        except json.JSONDecodeError as e:
            print(f"❌ JSON 解析失败: {e}。尝试进行容错处理...")
            # 尝试通过替换非法的换行或引号来修复（简单处理）
            # 这是个权宜之计，主要还是靠 prompt 约束 AI 输出合法 JSON
            fixed_str = json_str.replace('\n', '\\n').replace('\r', '')
            try:
                result = json.loads(fixed_str)
            except Exception as e2:
                print(f"❌ 容错解析依然失败: {e2}")
                return ("⚠️ AI 分析结果 JSON 格式错误，无法展示研判分析。", [], [])

        # 安全获取字段，提供默认值
        summary_analysis = result.get("summary_analysis", "AI 未生成全局总结。")
        important_news = result.get("important", [])
        interest_news = result.get("interest", [])

        # 再次确保返回的是列表
        if not isinstance(important_news, list): important_news = []
        if not isinstance(interest_news, list): interest_news = []

        return summary_analysis, important_news, interest_news

    except Exception as e:
        print(f"❌ 请求 DeepSeek API 过程报错: {e}")
        return (f"⚠️ AI 分析报错: {e}", [], [])
