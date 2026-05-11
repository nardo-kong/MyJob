import webbrowser
from flask import Flask, request, jsonify, send_from_directory
import requests
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

    try:
        # 核心：使用 verify=False 来绕过 SSL 证书验证
        response = requests.post(endpoint, headers=headers, json=payload, verify=False)
        response.raise_for_status()  # 如果响应状态码不是 2xx，则引发 HTTPError
        return jsonify(response.json())
    except requests.exceptions.RequestException as e:
        # 捕获所有 requests 相关的异常
        error_message = f"Failed to connect to API endpoint: {str(e)}"
        # 关键：将详细错误信息打印到控制台以供调试
        print(f"--- PROXY ERROR ---\n{error_message}\n-------------------")
        
        # 尝试从原始异常中获取更详细的信息
        if e.response is not None:
            try:
                error_detail = e.response.json()
                error_message += f" - {error_detail}"
            except ValueError:
                error_message += f" - {e.response.text}"
        return jsonify({"error": "Proxy request failed", "details": error_message}), 502


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