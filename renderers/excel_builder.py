import pandas as pd
import re

def export_tables_to_excel(md_content, excel_path):
    """
    智能扫描 Markdown 文本中的所有表格，
    并将其剥离出来，按顺序存入一个包含多 Sheet 的 Excel 文件中。
    """
    # 寻找包含 Markdown 分割线 (如 |---| 或 |:---:|) 的段落块
    blocks = md_content.split('\n\n')
    tables = [b for b in blocks if re.search(r'\|[\s\-\:]+\|', b)]
    
    valid_tables = 0
    try:
        # 使用 openpyxl 引擎写入 Excel
        with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
            for idx, table_text in enumerate(tables):
                # 逐行清洗表格内容
                lines = [line.strip() for line in table_text.strip().split('\n') if '|' in line]
                if len(lines) < 2:
                    continue
                    
                # 提取表头
                headers = [col.strip() for col in lines[0].strip('|').split('|')]
                
                data = []
                for line in lines[1:]:
                    # 跳过纯对齐/分割线那一行
                    if re.search(r'^\|?[\s\-\:]+\|?$', line.replace('|', '')):
                        continue
                        
                    row = [col.strip() for col in line.strip('|').split('|')]
                    
                    # 防呆设计：对齐列数，防止大模型抽风少写了一格导致报错
                    if len(row) < len(headers):
                        row.extend([''] * (len(headers) - len(row)))
                    elif len(row) > len(headers):
                        row = row[:len(headers)]
                    data.append(row)
                    
                if data:
                    df = pd.DataFrame(data, columns=headers)
                    # 限制 Sheet 名称，防重名或超长
                    sheet_name = f'数据表_{idx+1}'
                    df.to_excel(writer, sheet_name=sheet_name, index=False)
                    valid_tables += 1
                    
        # 如果成功提取到至少一个表格，返回 True
        return valid_tables > 0
        
    except Exception as e:
        print(f"❌ Excel 导出异常: {e}")
        return False
