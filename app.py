import streamlit as st
import os
import time
from datetime import datetime
from renderers.excel_builder import export_tables_to_excel  # 👈 【新增这一行】

# ==========================================
# 1. 核心路径防呆设计 (彻底解决目录混乱)
# ==========================================
# 获取 webui.py 当前所在的绝对路径（即 06_文件总结 文件夹）
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 规范化所有的输出目录，强制建在 06_文件总结 里面
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
UPLOAD_DIR = os.path.join(OUTPUT_DIR, "uploads")             # 存放所有上传的原文件
TEMP_IMG_DIR = os.path.join(OUTPUT_DIR, "pdf_temp_images")   # 存放 PDF 拆解图

# 确保目录永远存在
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(TEMP_IMG_DIR, exist_ok=True)

# 导入底层核心模块
from utils import natural_sort_key
from parsers.pdf_parser import convert_pdf_to_images
from main import process_single_page, generate_final_summary
from renderers.html_builder import export_to_html



# ==========================================
# 2. 页面基本设置
# ==========================================
st.set_page_config(
    page_title="AI 材料深度解读工作台",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
    <style>
    /* 隐藏默认菜单和页脚 */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* ---------------- 排版美化核心 ---------------- */
    /* 1. 调整正文字体和整体行高 */
    .stMarkdown p {
        font-size: 16px !important;
        line-height: 1.7 !important;
        margin-bottom: 12px !important;
    }

    /* 2. 解决列表项之间空隙过大、松散的问题 */
    .stMarkdown li {
        margin-bottom: 6px !important; /* 列表项之间的间距 */
    }
    .stMarkdown li > p {
        margin-bottom: 0px !important; /* 去除列表内段落的自带大边距 */
        margin-top: 0px !important;
    }
    .stMarkdown ul, .stMarkdown ol {
        margin-bottom: 20px !important;
        padding-left: 28px !important;
    }

    /* 3. 各级标题分层分级，增强视觉层级感 */
    .stMarkdown h2 {
        font-size: 22px !important;
        color: #1a202c !important;
        border-bottom: 2px solid #ebf4ff !important; /* 增加底边框区分大模块 */
        padding-bottom: 8px !important;
        margin-top: 35px !important;
        margin-bottom: 16px !important;
    }
    .stMarkdown h3 {
        font-size: 18px !important;
        color: #2b6cb0 !important; /* 小标题用深蓝色区分 */
        margin-top: 24px !important;
        margin-bottom: 12px !important;
        font-weight: 600 !important;
    }
    .stMarkdown strong {
        color: #111827 !important; /* 加粗字体颜色加深，突出重点 */
    }
    </style>
    """, unsafe_allow_html=True)

    
with st.sidebar:
    st.image("https://img.icons8.com/color/96/000000/combo-chart--v1.png", width=60)
    st.title("系统面板")
    st.markdown("---")
    max_pages = st.number_input("最大解析页数 (防超载)", min_value=1, max_value=500, value=100)
    st.markdown("---")
    st.success(f"📁 **数据存储路径已锁定:**\n\n所有的原文件和报告都会自动保存在:\n`{OUTPUT_DIR}`")

st.markdown("### 📊 AI 材料深度解读工作台")  # 两个 # 号，大小刚刚好，不突兀
st.markdown("基于 Qwen-VL 与 DeepSeek 多模型引擎，自动读取图文并进行红蓝军对抗生成商业洞察。")

# ==========================================
# 3. 双轨工作流（标签页设计）
# ==========================================
tab1, tab2 = st.tabs(["🚀 全流程智能解析 (传 PDF / 图片)", "⚡ 断点续传与重新生成 (直接传 MD)"])

# ---------------------------------------------------------
# 工作流 A：全流程解析 (看图 -> 提取 -> 总结 -> 网页)
# ---------------------------------------------------------
with tab1:
    st.markdown("###### 📥 步骤一：上传原始文件")
    uploaded_files = st.file_uploader(
        "请将需要分析的 PDF 报告或 PPT 截图拖拽至此", 
        type=["pdf", "png", "jpg", "jpeg"], 
        accept_multiple_files=True,
        key="full_pipeline"
    )

    # 用户自定义分析需求输入框
    user_requirement_full = st.text_area(
        "🎯 自定义分析侧重点 (选填)", 
        placeholder="例如：请重点提取各省份的 ARPU 值对比；或者重点关注政企DICT业务的增长和风险...",
        height=100
    )

    # 👇 【核心修改点】：改为双按钮并排显示
    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        btn_extract_only = st.button("📝 仅提取数据底稿 (生成 MD)", use_container_width=True, help="只把 PDF/图片 转换成文字底稿，不调用大模型进行长篇总结。适合用于【多文档对比】前的快速数据准备。")
    with col_btn2:
        btn_full_pipeline = st.button("🚀 开始全流程深度研判", type="primary", use_container_width=True)

    # 只要点击了任何一个按钮，就启动第一阶段的提取
    if btn_extract_only or btn_full_pipeline:
        if not uploaded_files:
            st.warning("⚠️ 请先上传至少一个文件！")
            st.stop()
            
        status_text = st.empty()
        progress_bar = st.progress(0)
        image_paths = []
        
        # 1. 接收文件并永久保存到 uploads 目录
        status_text.info("📦 正在接收并备份上传的文件...")
        timestamp_prefix = datetime.now().strftime("%Y%m%d_%H%M%S_") # 时间戳前缀防覆盖
        
        for file in uploaded_files:
            safe_filename = timestamp_prefix + file.name
            file_path = os.path.join(UPLOAD_DIR, safe_filename)
            
            with open(file_path, "wb") as f:
                f.write(file.getbuffer())
                
            if file.name.lower().endswith('.pdf'):
                pdf_imgs = convert_pdf_to_images(file_path, TEMP_IMG_DIR, max_pages)
                image_paths.extend(pdf_imgs)
            else:
                image_paths.append(file_path)
                
        if max_pages: image_paths = image_paths[:max_pages]
            
        total_pages = len(image_paths)
        if total_pages == 0:
            st.error("❌ 未能成功提取任何页面，请检查文件格式。")
            st.stop()

        # 2. 视觉解析
        all_content = ""
        st.markdown("###### 👁️ 步骤二：视觉引擎解析监控")
        with st.expander("👉 点击展开查看各页提取明细", expanded=False):
            log_placeholder = st.empty()
            log_text = ""
            for i, path in enumerate(image_paths):
                status_text.warning(f"👁️ 视觉引擎正在解析第 {i+1}/{total_pages} 页...")
                result = process_single_page(path, i + 1)
                
                filename_raw = os.path.basename(path)
                source_name = filename_raw.split('_page_')[0] if '_page_' in filename_raw else filename_raw
                page_block = f"\n\n> 📁 **[来源文件：{source_name}]** - 第 {i+1} 页提取内容\n{result}\n"
                all_content += page_block
                
                log_text += f"**✅ 第 {i+1} 页提取完成**\n\n"
                log_placeholder.markdown(log_text)
                progress_bar.progress((i + 1) / total_pages)
                
        # 实时保存一份最新的 MD 提取底稿
        temp_md_path = os.path.join(OUTPUT_DIR, f"提取底稿_{timestamp_prefix[:-1]}.md")
        with open(temp_md_path, "w", encoding="utf-8") as f:
            f.write(all_content)
            
        # 👇 【核心修改点】：如果是“仅提取模式”，到这里直接中断并提供下载
        if btn_extract_only:
            status_text.success("✅ 视觉提取完毕！(当前为仅提取数据模式)")
            progress_bar.empty()
            st.info("💡 底稿已生成！您可以直接下载该 Markdown 文件，用于【横向竞品对比】或【纵向历史趋势】模块。")
            
            with open(temp_md_path, "r", encoding="utf-8") as f:
                st.download_button(
                    label="⬇️ 一键下载 MD 数据底稿", 
                    data=f, 
                    file_name=f"提取底稿_{timestamp_prefix[:-1]}.md", 
                    mime="text/markdown",
                    type="primary"
                )
            st.stop() # 🛑 强制终止程序，防止进入后面的全流程总结
            
        # 👇 【核心修改点】：如果是“全流程模式”，继续执行后面的红蓝军对抗
        if btn_full_pipeline:
            status_text.success("✅ 视觉提取完毕！即将进入大脑深度研判...")
            progress_bar.empty()
            st.markdown("###### 🧠 步骤三：深度研判报告生成中")
            with st.spinner('红蓝军 正在进行交叉比对与财务推演 (请查看命令行后台的打字机输出)...'):
                summary = generate_final_summary(all_content, user_requirement_full)
                
            st.success("🎉 研判报告已生成！")
            st.markdown("---")
            st.markdown(summary, unsafe_allow_html=True)
            
            # ---------- 替换开始 ----------
            # 生成带时间戳的最终持久化文件
            final_md_content = f"# AI 深度洞察与业务研判报告\n\n{summary}\n\n---\n## 📚 附录：已清洗的分页底层数据\n<details markdown=\"1\">\n<summary>👉 点击展开查看各页原始核心数据 (已过滤噪音)</summary>\n\n{all_content}\n</details>"
            
            final_md_file = os.path.join(OUTPUT_DIR, f"AI研判报告_{timestamp_prefix[:-1]}.md")
            with open(final_md_file, "w", encoding="utf-8") as f:
                f.write(final_md_content)
                
            final_html_file = os.path.join(OUTPUT_DIR, f"AI研判网页版_{timestamp_prefix[:-1]}.html")
            export_to_html(final_md_content, final_html_file)

            # 生成 Excel 文件
            final_excel_file = os.path.join(OUTPUT_DIR, f"提取数据表_{timestamp_prefix[:-1]}.xlsx")
            has_excel = export_tables_to_excel(final_md_content, final_excel_file)
            
            # 提供下载
            st.markdown("### 💾 导出报告")
            cols = st.columns(3 if has_excel else 2)
            
            with cols[0]:
                with open(final_md_file, "r", encoding="utf-8") as f:
                    st.download_button("⬇️ 下载 Markdown 归档版", f, file_name=f"AI研判报告_{timestamp_prefix[:-1]}.md")
            with cols[1]:
                with open(final_html_file, "r", encoding="utf-8") as f:
                    st.download_button("🌐 下载精美 HTML 网页版", f, file_name=f"AI研判网页版_{timestamp_prefix[:-1]}.html")
                    
            if has_excel:
                with cols[2]:
                    with open(final_excel_file, "rb") as f:
                        st.download_button(
                            "📊 下载 Excel 数据表", 
                            f, 
                            file_name=f"提取数据表_{timestamp_prefix[:-1]}.xlsx", 
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
            # ---------- 替换结束 ----------


# ---------------------------------------------------------
# 工作流 B：断点续传 (直接吃 MD -> 总结 -> 网页)
# ---------------------------------------------------------
# ---------------------------------------------------------
# 工作流 B：断点续传 (直接吃 MD -> 总结 -> 网页)
# ---------------------------------------------------------
with tab2:
    st.markdown("###### 📥 步骤一：上传已有的 Markdown 数据文件")
    st.info("如果你之前提取的文本保存为了 `.md` 文件，将它传到这里，将直接跳过看图环节。")
    
    uploaded_md = st.file_uploader(
        "请将带有提取文本的 .md 文件拖拽至此", 
        type=["md"],
        key="md_pipeline"
    )
    
    # 👇 新增：用户自定义分析需求输入框 (注意 key 不能重复)
    user_requirement_md = st.text_area(
        "🎯 自定义分析侧重点 (选填)", 
        placeholder="例如：请重点提取各省份的 ARPU 值对比；或者重点关注政企DICT业务的增长和风险...",
        height=100,
        key="req_md"
    )
    
    if st.button("⚡ 直接生成深度分析与 HTML", type="primary", key="btn_md"):
        if not uploaded_md:
            st.warning("⚠️ 请先上传 .md 文件！")
            st.stop()
            
        # 1. 永久备份上传的 MD 文件
        timestamp_prefix = datetime.now().strftime("%Y%m%d_%H%M%S_")
        safe_md_filename = timestamp_prefix + uploaded_md.name
        md_save_path = os.path.join(UPLOAD_DIR, safe_md_filename)
        
        all_content = uploaded_md.getvalue().decode("utf-8")
        with open(md_save_path, "w", encoding="utf-8") as f:
            f.write(all_content)
            
        if not all_content.strip():
            st.error("❌ 文件内容为空！")
            st.stop()
            
        # 2. 开始总结
        # 👇 修改点：在调用总结函数时，传入 user_requirement_md
        # 大约在原来第 185 行附近
        st.markdown("###### 🧠 步骤二：大脑深度研判报告生成中")
        with st.spinner('正在直接读取文本并进行研判分析...'):
            summary = generate_final_summary(all_content, user_requirement_md)  # 👈 传入参数
            
        st.success("🎉 基于 MD 的研判报告已极速生成！")
        st.markdown("---")
        st.markdown(summary, unsafe_allow_html=True)

        
        # 3. 生成带时间戳的持久化文件
        final_md_content = f"# AI 深度洞察与业务研判报告\n\n{summary}\n\n---\n## 📚 附录：已清洗的分页底层数据\n<details markdown=\"1\">\n<summary>👉 点击展开查看各页原始核心数据 (已过滤噪音)</summary>\n\n{all_content}\n</details>"
        
        final_md_file = os.path.join(OUTPUT_DIR, f"极速直出报告_{timestamp_prefix[:-1]}.md")
        with open(final_md_file, "w", encoding="utf-8") as f:
            f.write(final_md_content)
            
        final_html_file = os.path.join(OUTPUT_DIR, f"极速直出网页版_{timestamp_prefix[:-1]}.html")
        export_to_html(final_md_content, final_html_file)
        
        # 4. 提供下载
        st.markdown("###### 💾 导出报告")
        col1, col2 = st.columns(2)
        with col1:
            with open(final_md_file, "r", encoding="utf-8") as f:
                st.download_button("⬇️ 下载 Markdown 归档版", f, file_name=f"极速直出报告_{timestamp_prefix[:-1]}.md")
        with col2:
            with open(final_html_file, "r", encoding="utf-8") as f:
                st.download_button("⬇️ 下载精美 HTML 网页版", f, file_name=f"极速直出网页版_{timestamp_prefix[:-1]}.html")


    #streamlit run 08_横竖对比/app.py
