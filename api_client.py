import requests
import time
import json
from config import *

# 【新增 silent_stream 参数】
def call_api(messages, model_name, stream=False, silent_stream=False):
    """增加 silent_stream 参数：后台传输数据防 504，但不打印到控制台干扰视线"""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }
    payload = {
        "model": model_name,
        "messages": messages,
        "temperature": 0.1,
        "stream": stream
    }
    
    current_timeout = 600 if "deepseek" in model_name.lower() or "72b" in model_name.lower() or "30b" in model_name.lower() else 120
    
    for attempt in range(1, RETRY_TIMES + 1):
        try:
            response = requests.post(API_URL, headers=headers, json=payload, stream=stream, timeout=current_timeout)
            
            if stream and response.status_code == 200:
                full_content = ""
                if not silent_stream:
                    print("\n" + "="*50)
                    
                for line in response.iter_lines():
                    if line:
                        decoded_line = line.decode('utf-8')
                        if decoded_line.startswith('data: '):
                            data_str = decoded_line[6:]
                            if data_str.strip() == '[DONE]':
                                break
                            try:
                                data_json = json.loads(data_str)
                                chunk = data_json['choices'][0]['delta'].get('content', '')
                                if chunk:
                                    # 如果不是静默模式，才打印到屏幕上
                                    if not silent_stream:
                                        print(chunk, end='', flush=True) 
                                    full_content += chunk
                            except json.JSONDecodeError:
                                continue
                                
                if not silent_stream:
                    print("\n" + "="*50 + "\n")
                return full_content
                
            elif not stream and response.status_code == 200:
                return response.json()["choices"][0]["message"]["content"]
                
            if response.status_code == 429 or response.status_code >= 500:
                print(f"⚠️ 服务器限流或拥堵 ({response.status_code})。等待 {RETRY_DELAY} 秒后重试...")
                time.sleep(RETRY_DELAY)
                continue
                
            print(f"❌ 服务器明确拒绝请求！状态码: {response.status_code}\n详情: {response.text}")
            break
            
        except requests.exceptions.Timeout:
            print(f"⏳ 请求超时！尝试重连...")
            time.sleep(RETRY_DELAY)
        except Exception as e:
            print(f"📡 网络异常: {e}。等待重试...")
            time.sleep(RETRY_DELAY)
            
    return "--- ⚠️ 本次提取彻底失败 ---"
