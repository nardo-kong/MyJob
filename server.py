import webbrowser
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import requests
import httpx
import threading
import sys
import os

# 确定资源文件路径，用于 PyInstaller 打包
def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

# 使用静态文件和模板文件的正确路径初始化 Flask
# 当通过 PyInstaller 运行时，静态文件夹和模板文件夹可能不存在
# 我们将所有内容都从一个目录提供
app = Flask(__name__, static_folder=resource_path(''))
CORS(app)
# 代理端点
@app.route('/api/ai', methods=['POST'])
def proxy_ai():
    # 立即打印日志，确认请求已到达
    print("\n--- Received request at /api/ai ---")
    
    data = request.get_json()
    
    # 打印接收到的数据，用于调试
    print(f"Request data: {data}")

    api_key = data.get('apiKey')
    endpoint = data.get('endpoint')
    model = data.get('model')
    messages = data.get('messages')
    is_test = data.get('isTest', False)

    if not api_key or not endpoint or not model:
        return jsonify({"error": "Missing API configuration"}), 400

    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {api_key}'
    }
    
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.5,
    }
    
    # 对于非测试请求，需要返回 JSON 对象
    if not is_test:
        payload["response_format"] = {"type": "json_object"}

    # LangChain 等客户端会自动将 /chat/completions 拼接到 base_url 后
    # 如果用户在前端输入的是 base_url，则自动补全
    if not endpoint.endswith('/chat/completions'):
        if not endpoint.endswith('/'):
            endpoint += '/'
        endpoint += 'chat/completions'

    try:
        # 核心：使用 httpx 来绕过 SSL 证书验证，并解决 requests 经常被 WAF 直接断开连接(10054)的问题
        print(f"Sending request to endpoint: {endpoint}")
        with httpx.Client(verify=False) as client:
            response = client.post(endpoint, headers=headers, json=payload, timeout=60.0)
        
        # 打印响应状态码和文本内容以便在后端控制台进行排错
        print(f"Response status code: {response.status_code}")
        print(f"Response text: {response.text}")
        
        response.raise_for_status()  # 如果响应状态码不是 2xx，则引发 HTTPError
        return jsonify(response.json())
    except httpx.RequestError as e:
        # 捕获所有 httpx 请求相关的异常
        error_message = f"Failed to connect to API endpoint: {str(e)}"
        
        # 尝试从原始异常中获取更详细的信息
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_detail = e.response.json()
                error_message += f" - {error_detail}"
            except ValueError:
                error_message += f" - {e.response.text}"
                
        # 关键：将详细错误信息打印到控制台以供调试
        print(f"--- PROXY ERROR ---\n{error_message}\n-------------------")
        return jsonify({"error": "Proxy request failed", "details": error_message}), 502
    except httpx.HTTPStatusError as e:
        error_message = f"HTTP Error {e.response.status_code}: {e.response.text}"
        print(f"--- HTTP STATUS ERROR ---\n{error_message}\n-------------------")
        return jsonify({"error": "API returned an error", "details": error_message}), 502
    except ValueError as e:
        # 捕获 JSON 解析错误
        error_message = f"Failed to parse API response as JSON: {str(e)}. Response text: {response.text}"
        print(f"--- PARSE ERROR ---\n{error_message}\n-------------------")
        return jsonify({"error": "Invalid JSON response", "details": error_message}), 502
    except Exception as e:
        error_message = f"An unexpected error occurred: {str(e)}"
        print(f"--- UNEXPECTED ERROR ---\n{error_message}\n-------------------")
        return jsonify({"error": "Unexpected error", "details": error_message}), 500


# 提供 Portal.html
@app.route('/')
def index():
    # 从资源路径提供 Portal.html
    return send_from_directory(app.static_folder, 'Portal.html')

def open_browser():
    """在默认浏览器中打开 web 应用"""
    webbrowser.open_new("http://localhost:5000")

if __name__ == '__main__':
    print("Starting server at http://localhost:5000")
    print("Your application is now available in your web browser.")
    print("Close this window to stop the server.")
    # 在服务器启动后延迟一秒打开浏览器
    threading.Timer(1, open_browser).start()
    # 运行服务器
    app.run(host='0.0.0.0', port=5000)