import os
from concurrent.futures import ThreadPoolExecutor
from api_client import call_api
from main import get_safe_text_for_model  # 复用你写好的截断函数
from config import MODEL_VISION, MODEL_EDITOR, MODEL_TEXT

def _extract_single_company(company_name, text):
    """Map阶段：独立提取单家公司的数据，防止幻觉混淆"""
    print(f"[{company_name}] 专属分析师正在提纯数据...")
    safe_text = get_safe_text_for_model(text, MODEL_TEXT)
    
    prompt = f"""你现在的任务是为【{company_name}】提取高度结构化的商业指标。
请从以下报告中，提取该公司的：1. 核心财务指标（营收、利润、ARPU等）；2. 核心战略方向；3. 面临的显性风险。
必须绝对客观，不要对比其他公司，只需提取【{company_name}】自己的数据。如果在文本中找不到，请直接跳过，绝不编造。

【{company_name} 原始文本】：
{safe_text}
"""
    messages = [{"role": "user", "content": prompt}]
    return call_api(messages, model_name=MODEL_TEXT, stream=False)


def generate_compare_summary(company_data_dict):
    """Reduce阶段：多公司拉通对比"""
    print("\n🤖 [多模态竞品大脑] 启动！正在并行提取各家数据...")
    
    extracted_results = {}
    # 1. 并行 Map 提取各家数据
    with ThreadPoolExecutor(max_workers=len(company_data_dict)) as executor:
        future_to_company = {
            executor.submit(_extract_single_company, name, text): name 
            for name, text in company_data_dict.items()
        }
        for future in future_to_company:
            company_name = future_to_company[future]
            extracted_results[company_name] = future.result()

    print("✅ 各家数据提纯完毕！首席竞品分析师正在输出深度横评...")

    # 2. 组装给主编的对比上下文
    combined_context = ""
    for name, data in extracted_results.items():
        combined_context += f"\n\n{'='*20}\n【{name} 的核心数据提取】：\n{data}\n{'='*20}"

    # 3. 终局 Reduce 生成对比报告
    editor_messages = [
        {
            "role": "system", 
            "content": "你是一位顶级投行首席TMT分析师，极其擅长电信行业竞品分析。你的任务是基于我提供的多家公司独立数据，进行极其犀利的横向评测。"
        },
        {
            "role": "user", 
            "content": f"""以下是各家公司的结构化提取数据，请基于这些数据输出《行业竞品横向对比研判报告》。

【多公司基础数据库】：
{combined_context}

【排版与内容铁律】：
1. 绝对不要平铺直叙地罗列每家公司的数据！必须采用“对比视角”（例如：“在政企市场，A公司增速远超B公司”）。
2. 如果缺乏某家公司的某项对比数据，请直接省略该维度的对比，绝不脑补。
3. 如果公司名字明显写反或者有差错的话，修改成正确的；

请按照以下结构输出：

1. **🥇 行业大盘与座次重排 (Industry Landscape)**
   - 总结当前几家公司的竞争格局（谁在领跑，谁在掉队，谁在蚕食谁的份额），不止是规模，重点是增长。

2. **⚔️ 核心战场刺刀见红 (Core Battlefield Clash)**
   - 挑选3-5个核心业务战场，横向对比各家的表现与打法差异。（⚠️ 铁律：请根据原文数据自行识别什么是核心业务，不要生搬硬套！）

3. **🛡️ 护城河与软肋对决 (Moats vs. Weaknesses)**
   - 犀利点出每一家公司最大的“底牌”（优势）和最大的“阿喀琉斯之踵”（劣势）。

4. **📈 横向对比核心数据表 (Comparison Data Table)**
   - 输出一张 Markdown 表格。
   - **表头格式必须为**：| 指标名称 | 公司A数值 | 公司B数值 | 公司C数值 | 胜出者/点评 |
   - 只对比大家都有的数据，缺失的数据用 “-” 表示。
"""
        }
    ]
    
    final_summary = call_api(editor_messages, model_name=MODEL_EDITOR, stream=True)
    return final_summary
