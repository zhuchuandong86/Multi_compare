import os
from concurrent.futures import ThreadPoolExecutor
from api_client import call_api
from parsers.image_parser import encode_and_compress_image
from config import MODEL_BLUE, MODEL_RED, MODEL_EDITOR, MODEL_TEXT




def process_single_page(image_path, page_num):
    """视觉引擎：负责单张图片的解析与数据清洗"""
    print(f"👉 正在深度解析并清洗页面 {page_num}: {os.path.basename(image_path)}...")
    try:
        base64_img = encode_and_compress_image(image_path)
    except Exception as e:
        return f"--- ⚠️ 图片预处理失败: {e} ---"
    
    messages = [{
        "role": "user",
        "content": [
            {
                "type": "text", 
                "text": f"这是电信运营商经营分析/网络分析报告的第 {page_num} 页。\n你现在的角色是严谨的『数据清洗与提取专家』。\n\n【提取与清洗规则】：\n1. 🛑 自动过滤噪音：绝对不要提取无意义的页眉、页脚、单纯的页码、背景水印、版权声明或无法识别的乱码。\n2. 📊 表格规范化：将所有财报表格、饼图、折线图转化为格式极其干净、对齐的标准 Markdown 表格。\n3. 📝 文本结构化：正文请保持清爽的排版，多用无序列表('- ')，去除原文中为了排版而产生的多余换行。\n4. 🚫 严禁主观加工：不要对数据进行任何评价或总结，只需忠实、干净地还原核心有效信息。"
            },
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_img}"}}
        ]
    }]
    from config import MODEL_VISION
    result = call_api(messages, model_name=MODEL_VISION, stream=False)
    return result.strip()


def get_safe_text_for_model(text, model_name):
    """【新增功能】：根据不同模型的真实上下文上限，动态截断文本"""
    limit = 40000  # 默认基准线
    name_lower = model_name.lower()
    
    if "deepseek-v3-0324" in name_lower:
        limit = 38000   # 明确已知 32k 限制，严格掐断防 400 报错
    elif "deepseek-r1" in name_lower:
        limit = 60000   # R1 通常部署 64k 左右的上下文
    elif "72b" in name_lower or "30b" in name_lower or "256k" in name_lower:
        limit = 120000  # Qwen 大家族原生 128k 起步，放宽限制
        
    if len(text) > limit:
        print(f"✂️ [安全管控] {model_name} 触发阈值，已动态截断至 {limit} 字符...")
        return text[:limit] + f"\n\n...[警告：由于 {model_name} 算力限制，尾部内容已安全截断]..."
    return text


def _call_specialist_agent(role_prompt, full_text, model_name, agent_name):
    """用于调用红/蓝军专家的内部并发函数"""
    print(f"[{agent_name}] 正在独立阅卷分析中...")
    
    # 【改动点】：获取当前模型能安全吃下的文本长度
    safe_text = get_safe_text_for_model(full_text, model_name)
    
    messages = [
        {"role": "system", "content": role_prompt},
        {"role": "user", "content": f"以下是完整的财报或者经营分析、网络分析报告提取数据，请严格按照你的角色设定，指出具体问题（必须标明来源页码）：\n\n{safe_text}"}
    ]
    # 【改动点】：开启 stream=True 防 504，同时开启 silent_stream=True 防止控制台字体重叠打架
    return call_api(messages, model_name=model_name, stream=True, silent_stream=True)


def generate_final_summary(full_text, user_req=""):
    """大脑引擎升级：Multi-Agent 红蓝对抗工作流 (带专家底稿保留及用户需求优先)"""
    
    print("\n🤖 [Multi-Agent 启动] 正在唤醒虚拟专家团队进行红蓝对抗...")
    
    # 👇 新增：处理用户自定义需求
    user_directive_agent = ""
    user_directive_editor = ""
    if user_req and user_req.strip():
        print(f"🎯 接收到用户专属需求: {user_req.strip()}")
        user_directive_agent = f"\n\n【🌟 客户核心需求 (最高优先级)】：\n客户提出了具体的分析侧重点：“{user_req.strip()}”。你在寻找数据时，必须极其敏锐地捕捉与该需求相关的任何蛛丝马迹！"
        user_directive_editor = f"【🌟 客户核心需求 (最高优先级)】：\n客户提出了具体的分析侧重点：“{user_req.strip()}”。\n在输出报告时，你必须优先、重点回应这一需求。若原文件数据能支撑该需求，请作为报告的核心部分展开；若数据完全缺失，请在一开始明确告知客户。\n\n"
    
    # ---------------------------------------------------------
    # 第一阶段：红蓝两军并发独立看报告 (同时注入用户需求)
    # ---------------------------------------------------------
    blue_prompt = "你是一位极其严苛的『蓝军风控官』。你的唯一任务是：只找问题，不看成绩。请穿透字面意思，找出所有隐性风险、成本压力、业务下滑迹象等负面信号。必须极其犀利，并在每一条风险后标注 [来源文件：X页]。" + user_directive_agent
    
    red_prompt = "你是一位极具商业嗅觉的『红军战略官』。你的唯一任务是：寻找增长引擎。请专注发掘业务亮点、第二曲线潜力、高增长板块等积极信号。请保持客观乐观，并在每一个亮点后标注 [来源文件：X页]。" + user_directive_agent
    
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=2) as executor:
        future_blue = executor.submit(_call_specialist_agent, blue_prompt, full_text, MODEL_BLUE, "🔵 蓝军风控官")
        future_red = executor.submit(_call_specialist_agent, red_prompt, full_text, MODEL_RED, "🔴 红军战略官")
        
        blue_report = future_blue.result()
        red_report = future_red.result()
        
    print("✅ 红蓝两军辩论完毕！正在交由 [👨‍⚖️ 首席主编] 融合并输出最终报告...")

    # ---------------------------------------------------------
    # 第二阶段：主编 Agent 汇总输出
    # ---------------------------------------------------------
    editor_safe_text = get_safe_text_for_model(full_text, MODEL_EDITOR)
    
    editor_messages = [
        {
            "role": "system", 
            "content": "你现在是一位供职于顶级投行与战略咨询公司的【首席电信行业商业分析师兼资深行业专家】。你极其擅长穿透数据，从枯燥的经营数据中推演出企业的真实战略走向、业务健康度和潜在危机。你的最高原则是【数据驱动】和【绝对客观】。"
        },
        {
            "role": "user", 
            "content": f"""你现在拥有三份核心输入资料。请结合红蓝双方的意见，对原始数据进行最终判决。

【资料一：原始提取数据】：
{editor_safe_text}
---
【资料二：蓝军风控专家意见】：
{blue_report}
---
【资料三：红军战略专家意见】：
{red_report}

{user_directive_editor}
【最高执行指令（铁律）】：
1. **尽力而为与客观免责**：无论数据多么残缺，都请基于这些【仅有】的数据进行推演。**最核心原则：如果没有这项数据，就不要提这项数据。绝对不允许罗列空指标，也绝不允许靠常识瞎编。**
2. **强制精准溯源与排版规范（极其重要）**：
   - 引用数据必须使用 span 标签包裹，格式：`*<span style="color: gray;">[来源：第X页]</span>*`
   - 🛑 **排版铁律：绝不允许使用多级嵌套列表（如标题1下面带小圆点，或父子节点分离）。一律采用“加粗前缀 + 冒号 + 正文”的扁平化单层结构。**
   - ❌ 错误排版示范（严禁使用）：
     - 南非业务：
       - 营收：增长...
   - ✅ 正确排版示范（必须严格遵循）：
     - **南非业务营收**：同比增长0.6%至R240亿 *<span style="color: gray;">[来源：第10页]</span>*
     - **金融科技战略**：业务收入同比增长8.4% *<span style="color: gray;">[来源：第12页]</span>*
     - **优化客户获取**：针对连接数下滑区域推出限时优惠措施。
3. **零幻觉容忍**：如果在原始数据中找不到对应的页码支撑，请直接在你的脑海中删掉这句话，严禁泛泛而谈。

请严格基于原文数据，按照以下五大专业维度输出《深度商业经营研判报告》：
            
1. **📊 经营成果总结和分析 (Financial & Operational Results)**
- **数据透视**：不要报流水账！请直接抓取大盘中最核心的 3-4 个“主轴指标”或“惊艳/暴跌的异常值”。不仅要指出变化（如同比/环比），更要给出深度的归因分析。
- **质量评估**：仅基于已提取到的数据分析增长质量，如果没有就直接省略此项分析，退而求其次只做简单的客观描述。
- **铁律**：**不要罗列全部指标、报流水账；如果缺失某个关键指标（如未提及利润或ARPU），请直接在脑海中跳过该指标，绝对不要写“无数据”、“未提及”或“暂无披露”这类废话占用篇幅。**没有横向对比数据，就直接省略横向对比分

2. **🎯 战略走向与新动能校验 (Strategic Trajectory & New Growth Engines)**
- **战略解码**：基于管理层的表述、资源投入走向或高优考核指标，提炼当前企业最核心的 3-5 个战略重心。
- **第二曲线校验**：深度分析【创新业务/新动能】的真实落地结果。
- **铁律**：请大模型自行从原文提取该公司实际的新业务名称。拒绝毫无灵魂的数字罗列，必须拔高到“商业模式与护城河”的高度进行战略洞察！要用数据验证战略，而不是重复口号。**如果原文通篇只有传统业务，则直接表达未提及新业务”，**绝不允许硬编、臆想任何新业务。**

3. **⚠️ 风险穿透与压力洞察 (Risk & Pressure Penetration)**
- **显性风险**：直接点出报告中承认的下滑指标和受挫业务。
- **隐性风控**：拿着放大镜寻找数据背后的危机。
- **铁律**：**风险条目严格控制在 3-5 条。**如果没有足够的数据支撑隐性风险，有 1 条就写 1 条，甚至可以只写显性风险，**严禁无病呻吟或生搬硬套行业通用风险。**

4. **💡 首分析师战略建议 (Analyst's Strategic Recommendations)**
- **行动指南**：基于上述暴露的问题，给出犀利、可落地的管理层建议。
- **铁律**：**严格控制在 3-5 条，宁缺毋滥。拒绝假大空的职场废话。**

5. **📈 核心数据资产总表 (Master Data Table)**
- 将提取到的最重要的核心KPI整合为一张格式极简、对齐完美的 Markdown 表格。
- **只罗列原文中明确存在的数据指标，按照财务、业务、收入、用户等模块分类排序。**表格必须包含：指标名称、当前数值/表现、同环比变化（如有）。
- **表格最后一列必须是“数据来源”，且标注具体的页码。**

以下是完整的原文件提取内容：

"""
        }
    ]
    
    final_summary = call_api(editor_messages, model_name=MODEL_EDITOR, stream=True)
    
    if "⚠️ 本次提取彻底失败" in final_summary:
        print(f"\n🚨 警告：主编模型 {MODEL_EDITOR} 调用失败！")
        return final_summary
        
    preserved_agent_reports = f"""

---

## 🗂️ 专家组独立研判底稿 (Multi-Agent 视角)

<details markdown="1">
<summary>🔵 点击展开【蓝军风控官】的原始挑刺报告</summary>

{blue_report}

</details>

<details markdown="1">
<summary>🔴 点击展开【红军战略官】的原始增长报告</summary>

{red_report}

</details>
"""
    return final_summary + preserved_agent_reports
