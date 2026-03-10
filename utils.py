import re

def natural_sort_key(s):
    """
    自然排序算法
    解决 10.jpg 排在 2.jpg 前面的痛点
    """
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', s)]
