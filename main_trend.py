import os
from concurrent.futures import ThreadPoolExecutor
from api_client import call_api
from main import get_safe_text_for_model
from config import MODEL_VISION, MODEL_EDITOR, MODEL_TEXT

def _extract_single_year(year_label, text):
    """Map阶段：独立提取单年的核心数据"""
    print(f"[{year_label}] 历史数据正在清洗中...")
    safe_text = get_safe_text_for_model(text, MODEL_TEXT)
    
    prompt = f"""请提取【{year_label}】的核心财务指标（营收/利润等）、核心战略表述以及关键业务规模。
只需要提取数据和事实，不要做任何推演，不要和其他年份对比。如果没有找到数据请直接跳过。

【{year_label} 原始文本】：
{safe_text}
"""
    messages = [{"role": "user", "content": prompt}]
    return call_api(messages, model_name=MODEL_TEXT, stream=False)


def generate_trend_summary(yearly_data_dict):
    """Reduce阶段：按时间轴进行历史连贯性推演"""
    print("\n🤖 [历史趋势大脑] 启动！正在梳理时间轴...")
    
    extracted_results = {}
    with ThreadPoolExecutor(max_workers=min(len(yearly_data_dict), 5)) as executor:
        future_to_year = {
            executor.submit(_extract_single_year, year, text): year 
            for year, text in yearly_data_dict.items()
        }
        for future in future_to_year:
            year_label = future_to_year[future]
            extracted_results[year_label] = future.result()

    # 按照年份名称（如 2021, 2022）自动排序，保证时间轴连续
    sorted_years = sorted(extracted_results.keys())
    combined_context = ""
    for year in sorted_years:
        combined_context += f"\n\n{'='*20}\n【{year} 年度提取数据】：\n{extracted_results[year]}\n{'='*20}"

    editor_messages = [
        {
            "role": "system", 
            "content": "你是一位专注于追踪电信运营商企业生命周期与战略变迁的资深商业史分析师。你的任务是穿透多年的数据迷雾，画出企业的生命周期曲线。"
        },
        {
            "role": "user", 
            "content": f"""以下是该公司过去几年的核心切片数据。请输出《企业纵向战略演进与周期复盘报告》。

【历史时间轴数据库】：
{combined_context}

请严格按照以下维度输出：

1. **⏳ 战略演进与生命周期判定 (Strategic Evolution & Lifecycle)**
   - 纵观这几年，企业的核心战略发生过怎样的转移？（例如：从“抢夺用户”走向“深耕价值”）。
   - 指出在这几年中，哪一年是企业的“高光时刻”，哪一年是“战略拐点/阵痛期”？

2. **🚀 核心引擎的兴衰更替 (Engines Rise and Fall)**
   - **基本盘演进**：用数据证明，曾经支撑营收的【传统核心基本盘】是否出现了停滞或衰退？（⚠️ 铁律：请根据原文数据自行识别该公司的“基本盘”究竟是什么业务，不要生搬硬套！）
   - **第二曲线**：寻找【新增长引擎】。哪项新业务从哪一年开始爆发，并扛起了营收大旗？（⚠️ 铁律：必须基于原文中实际出现的业务名称进行分析，绝不允许凭空捏造行业通用概念）。

3. **⚠️ 长期结构性隐患 (Long-term Structural Risks)**
   - 跨越单年财报的粉饰，指出连年累积下来的痼疾（如：连年攀升的资本开支、持续下滑的毛利率、长期未见起色的某项投入等）。

4. **📈 多年核心指标演进表 (Multi-Year Evolution Table)**
   - 输出一张 Markdown 表格。
   - **表头格式必须为**：| 核心指标 | { ' | '.join(sorted_years) } | 趋势点评 |
   - 纵向展示几年的数据变动，一目了然。
"""
        }
    ]
    
    final_summary = call_api(editor_messages, model_name=MODEL_EDITOR, stream=True)
    return final_summary
