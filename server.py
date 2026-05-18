import webbrowser
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from openai import OpenAI
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
    temperature = data.get('temperature') # 允许从前端获取
    skip_ssl = data.get('skipSsl', False) # 允许前端指定是否跳过 SSL 校验
    stream = data.get('stream', False) # 是否启用流式输出
    is_test = data.get('isTest', False)

    if not api_key or not endpoint or not model:
        return jsonify({"error": "Missing API configuration"}), 400

    try:
        print(f"Sending request via OpenAI SDK to: {endpoint} (SkipSSL: {skip_ssl}, Stream: {stream})")

        # 根据前端参数决定是否启用 SSL 校验，延长超时时间以支持思考模型
        client = OpenAI(
            api_key=api_key,
            base_url=endpoint,
            http_client=httpx.Client(timeout=300.0, verify=not skip_ssl)
        )
        
        # 构造请求参数，如果前端没传 temperature 则不发送该参数
        # 解决某些推理模型（如 QVQ, o1）对 temperature 的严格限制
        completion_args = {
            "model": model,
            "messages": messages,
        }
        if temperature is not None:
            completion_args["temperature"] = float(temperature)
        if stream:
            completion_args["stream"] = True
            completion_args["stream_options"] = {"include_usage": True}

        # 使用官方 SDK 请求
        response = client.chat.completions.create(**completion_args)

        if stream:
            print("Stream mode: starting SSE response")
            def generate():
                import json
                chunk_count = 0
                try:
                    usage_info = None
                    for chunk in response:
                        if hasattr(chunk, 'usage') and chunk.usage is not None:
                            usage_info = chunk.usage
                            
                        delta = chunk.choices[0].delta if chunk.choices and len(chunk.choices) > 0 else None
                        if not delta:
                            continue
                        chunk_count += 1
                        content = delta.content or ""
                        reasoning = ""
                        if hasattr(delta, 'reasoning_content') and delta.reasoning_content:
                            reasoning = delta.reasoning_content
                        yield f"data: {json.dumps({'content': content, 'reasoning': reasoning})}\n\n"
                    
                    if usage_info:
                        prompt_tokens = usage_info.prompt_tokens
                        completion_tokens = usage_info.completion_tokens
                        total_tokens = usage_info.total_tokens
                        
                        cached_tokens = 0
                        if hasattr(usage_info, 'prompt_tokens_details') and usage_info.prompt_tokens_details:
                            cached_tokens = getattr(usage_info.prompt_tokens_details, 'cached_tokens', 0)
                            
                        print(f"Stream mode: completed SSE response ({chunk_count} chunks) - Token消耗: 输入 {prompt_tokens} (含缓存 {cached_tokens}), 输出 {completion_tokens}, 总计 {total_tokens}")
                    else:
                        print(f"Stream mode: completed SSE response ({chunk_count} chunks)")
                        
                    yield "data: [DONE]\n\n"
                except Exception as e:
                    print(f"Stream generation error: {e}")
                    yield f"data: {json.dumps({'error': str(e)})}\n\n"
            from flask import Response
            return Response(generate(), mimetype='text/event-stream')

        print(f"SDK response type: {type(response)}")
        print(f"SDK response value: {response}")

        if isinstance(response, str):
            content = response
        else:
            try:
                content = response.choices[0].message.content
            except AttributeError:
                dumped = response.model_dump() if hasattr(response, "model_dump") else response
                print(f"SDK response dump: {dumped}")
                content = dumped["choices"][0]["message"]["content"]
        
        # 将结果反序列化为类似格式以便前端继续使用
        return jsonify({
            "choices": [{
                "message": {
                    "content": content
                }
            }]
        })
        
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