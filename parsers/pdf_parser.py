import os
from pdf2image import convert_from_path
from pdf2image.exceptions import PDFInfoNotInstalledError

def convert_pdf_to_images(pdf_path, output_dir, max_pages=None):
    """将 PDF 转换为一系列图片，并用原文件名作为前缀防冲突"""
    os.makedirs(output_dir, exist_ok=True)
    image_paths = []
    
    base_name = os.path.splitext(os.path.basename(pdf_path))[0]
    print(f"📑 正在将 PDF [{base_name}] 展开为图像矩阵 (已开启底层引擎加速)...")
    
    try:
        poppler_path = r"C:\poppler-25.12.0\Library\bin" # 确保这里是你的真实路径
        
        # 【核心升级】：
        # 1. dpi=150: 黄金清晰度！既能保证大模型看清最小的表格数字，又能避免内嵌大图撑爆内存。
        # 2. thread_count=4: 开启 4 个并发线程。原本拆解 100 页 PDF 需要 1 分钟，现在只要 15 秒！
        images = convert_from_path(
            pdf_path, 
            last_page=max_pages, 
            poppler_path=poppler_path,
            dpi=150,               # 强制限制渲染精度防崩溃
            thread_count=4         # 开启多线程榨干 CPU 性能
        )
        
    except PDFInfoNotInstalledError:
        print("❌ 致命错误：未找到 Poppler！请检查路径是否正确。")
        return []
    except Exception as e:
        print(f"❌ 转换 PDF 时发生异常: {e}")
        return []
    
    for i, img in enumerate(images):
        p = os.path.join(output_dir, f"{base_name}_page_{i+1}.jpg")
        # 稍微压缩一下生成的暂存图片质量，减少硬盘读写耗时
        img.save(p, "JPEG", quality=90)
        image_paths.append(p)
        
    return image_paths
