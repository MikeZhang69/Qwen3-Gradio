import gradio as gr
from openai import OpenAI
import os
import time
import html
import re
import base64
import mimetypes
from datetime import datetime
from typing import List, Tuple, Optional
from PIL import Image
import io

# 尝试加载 .env 文件（如果存在）
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # 如果没有安装 python-dotenv，继续使用系统环境变量
    pass

# --- 配置 ---
# 安全的 API 密钥管理
API_KEY = os.environ.get("MODELSCOPE_API_KEY")
if not API_KEY:
    raise ValueError(
        "未找到 MODELSCOPE_API_KEY 环境变量。\n"
        "请设置环境变量：export MODELSCOPE_API_KEY=your_api_key_here\n"
        "或者在 .env 文件中添加：MODELSCOPE_API_KEY=your_api_key_here"
    )

BASE_URL = "https://api-inference.modelscope.cn/v1/"
MODEL_ID = 'Qwen/Qwen3-235B-A22B-Instruct-2507'

# 安全配置 - 支持环境变量覆盖
MAX_MESSAGE_LENGTH = int(os.environ.get("MAX_MESSAGE_LENGTH", 16000))  # 限制单条消息长度
MAX_HISTORY_LENGTH = int(os.environ.get("MAX_HISTORY_LENGTH", 50))     # 限制对话历史长度
RATE_LIMIT_DELAY = int(os.environ.get("RATE_LIMIT_DELAY", 1))          # 请求间隔（秒）
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB 文件大小限制

# API 限制配置 - 支持环境变量覆盖
MAX_OUTPUT_TOKENS = int(os.environ.get("MAX_OUTPUT_TOKENS", 32000))      # API最大输出token数 (32K)
DEFAULT_OUTPUT_TOKENS = int(os.environ.get("DEFAULT_OUTPUT_TOKENS", 8000))  # 默认输出token数 (8K)

# 支持的文件类型
SUPPORTED_TEXT_EXTENSIONS = {'.txt', '.md', '.py', '.js', '.html', '.css', '.json', '.xml', '.csv'}
SUPPORTED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}

# 初始化 OpenAI 客户端
try:
    client = OpenAI(
        base_url=BASE_URL,
        api_key=API_KEY,
    )
except Exception as e:
    print(f"Error initializing OpenAI client: {e}")
    client = None

# --- 文件处理函数 ---

def process_uploaded_file(file_path: str) -> Tuple[str, str]:
    """
    处理上传的文件
    
    Returns:
        Tuple[str, str]: (file_content, file_info)
    """
    if not file_path or not os.path.exists(file_path):
        return "", "文件不存在"
    
    # 检查文件大小
    file_size = os.path.getsize(file_path)
    if file_size > MAX_FILE_SIZE:
        return "", f"文件过大 ({file_size / 1024 / 1024:.1f}MB)，最大支持 {MAX_FILE_SIZE / 1024 / 1024}MB"
    
    file_name = os.path.basename(file_path)
    file_ext = os.path.splitext(file_name)[1].lower()
    
    try:
        # 处理文本文件
        if file_ext in SUPPORTED_TEXT_EXTENSIONS:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            file_info = f"📄 文件: {file_name} ({file_size} bytes)"
            return content, file_info
        
        # 处理图片文件
        elif file_ext in SUPPORTED_IMAGE_EXTENSIONS:
            # 读取并压缩图片
            with Image.open(file_path) as img:
                # 转换为RGB（如果需要）
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # 调整大小（保持比例）
                max_size = (800, 800)
                img.thumbnail(max_size, Image.Resampling.LANCZOS)
                
                # 转换为base64
                buffer = io.BytesIO()
                img.save(buffer, format='JPEG', quality=85)
                img_base64 = base64.b64encode(buffer.getvalue()).decode()
            
            file_info = f"🖼️ 图片: {file_name} ({img.size[0]}x{img.size[1]})"
            # 返回base64编码的图片数据，用于API调用
            return f"data:image/jpeg;base64,{img_base64}", file_info
        
        else:
            return "", f"不支持的文件类型: {file_ext}"
    
    except Exception as e:
        return "", f"文件处理失败: {str(e)[:100]}"

def get_timestamp() -> str:
    """获取当前时间戳"""
    return datetime.now().strftime("%H:%M:%S")

def format_message_with_timestamp(content: str, role: str) -> str:
    """为消息添加时间戳"""
    timestamp = get_timestamp()
    if role == "user":
        return f"**[{timestamp}] 您:** {content}"
    else:
        return f"**[{timestamp}] AI:** {content}"

def export_conversation(history: List[dict]) -> str:
    """导出对话历史为文本格式"""
    if not history:
        return "暂无对话记录"
    
    export_text = f"# 对话记录导出\n导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    
    for msg in history:
        role = "用户" if msg["role"] == "user" else "AI助手"
        content = msg["content"].replace("**[", "[").replace("] 您:**", "] 您:").replace("] AI:**", "] AI:")
        export_text += f"## {role}\n{content}\n\n"
    
    return export_text

def handle_export(history: List[dict]):
    """处理对话导出"""
    if not history:
        return None, show_notification("暂无对话记录可导出", "warning")
    
    try:
        export_content = export_conversation(history)
        filename = f"conversation_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        
        # 创建临时文件
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(export_content)
        
        return filename, show_notification(f"对话已成功导出到 {filename}", "success")
    except Exception as e:
        return None, show_notification(f"导出失败: {str(e)[:50]}", "error")

def copy_last_response(history: List[dict]):
    """复制最后一条AI回复"""
    if not history:
        return "⚠️ 暂无对话记录"
    
    # 找到最后一条AI回复
    for msg in reversed(history):
        if msg["role"] == "assistant" and msg["content"].strip():
            # 移除时间戳格式
            content = msg["content"]
            if content.startswith("**[") and "] AI:**" in content:
                content = content.split("] AI:**", 1)[1].strip()
            
            # 在实际应用中，这里可以使用JavaScript来复制到剪贴板
            # 现在只是显示状态信息
            return f"✅ 已准备复制: {content[:50]}{'...' if len(content) > 50 else ''}"
    
    return "⚠️ 未找到AI回复"

def show_notification(message: str, msg_type: str = "info"):
    """显示通知消息"""
    icons = {"success": "✅", "error": "❌", "info": "ℹ️", "warning": "⚠️"}
    icon = icons.get(msg_type, "ℹ️")
    return f"{icon} {message}"

def get_api_info():
    """获取API信息和限制"""
    return f"""
    📊 **当前API配置信息:**
    - 模型: {MODEL_ID}
    - 最大输出tokens: {MAX_OUTPUT_TOKENS}
    - 默认输出tokens: {DEFAULT_OUTPUT_TOKENS}
    - 最大消息长度: {MAX_MESSAGE_LENGTH} 字符
    - 对话历史限制: {MAX_HISTORY_LENGTH} 条
    
    💡 **Token说明:**
    - 1 token ≈ 0.75个中文字符 或 1个英文单词的一部分
    - Qwen模型通常支持8K-32K+ tokens的上下文长度
    - 当前设置为保守估计，可根据实际API响应调整
    """

# --- 安全工具函数 ---

def sanitize_input(text: str) -> str:
    """
    清理和验证用户输入
    """
    if not text or not isinstance(text, str):
        return ""
    
    # 移除潜在的恶意字符
    text = html.escape(text.strip())
    
    # 限制长度
    if len(text) > MAX_MESSAGE_LENGTH:
        text = text[:MAX_MESSAGE_LENGTH] + "..."
    
    return text

def validate_history(history: List[dict]) -> List[dict]:
    """
    验证和清理对话历史
    """
    if not history:
        return []
    
    # 限制历史长度
    if len(history) > MAX_HISTORY_LENGTH:
        history = history[-MAX_HISTORY_LENGTH:]
    
    # 清理每条消息
    cleaned_history = []
    for item in history:
        if isinstance(item, dict) and "role" in item and "content" in item:
            clean_content = sanitize_input(item["content"])
            if clean_content or item["role"] == "assistant":  # 保留所有助手消息和有效用户消息
                cleaned_history.append({"role": item["role"], "content": clean_content})
    
    return cleaned_history

# 简单的速率限制
last_request_time = 0

def rate_limit_check() -> bool:
    """
    检查速率限制
    """
    global last_request_time
    current_time = time.time()
    
    if current_time - last_request_time < RATE_LIMIT_DELAY:
        return False
    
    last_request_time = current_time
    return True

# --- Gradio 应用核心逻辑 ---

def predict(message: str, history: List[dict], uploaded_file=None, temperature=0.7, max_tokens=DEFAULT_OUTPUT_TOKENS):
    """
    核心预测函数，用于生成 AI 回复。
    
    Args:
        message (str): 用户输入的最新消息。
        history (List[dict]): Gradio Chatbot 提供的对话历史。
                              格式为 [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}, ...]
    
    Yields:
        List[dict]: 更新后的对话历史，用于流式更新 Chatbot UI。
    """
    # 安全检查
    if not client:
        yield history + [{"role": "user", "content": message}, {"role": "assistant", "content": "错误：OpenAI 客户端未成功初始化。请检查 API 密钥和网络连接。"}]
        return
    
    # 速率限制检查
    if not rate_limit_check():
        yield history + [{"role": "user", "content": message}, {"role": "assistant", "content": "请求过于频繁，请稍后再试。"}]
        return
    
    # 处理上传的文件
    file_content = ""
    file_info = ""
    if uploaded_file:
        file_content, file_info = process_uploaded_file(uploaded_file.name)
        if file_info and not file_content and "失败" in file_info:
            yield history + [{"role": "user", "content": message}, {"role": "assistant", "content": f"文件处理错误: {file_info}"}]
            return
    
    # 输入验证和清理
    clean_message = sanitize_input(message)
    if not clean_message and not file_content:
        yield history + [{"role": "user", "content": ""}, {"role": "assistant", "content": "请输入消息或上传文件。"}]
        return
    
    # 如果有文件内容，将其添加到消息中
    is_image = file_content.startswith("data:image/") if file_content else False
    
    if file_content:
        if is_image:
            # 对于图片，目前ModelScope API可能不支持视觉功能，所以提供描述
            if clean_message:
                clean_message = f"{clean_message}\n\n[已上传图片: {file_info}]"
            else:
                clean_message = f"我上传了一张图片: {file_info}，请告诉我如何处理图片文件。"
        else:
            # 对于文本文件，直接包含内容
            if clean_message:
                clean_message = f"{clean_message}\n\n[文件内容]\n{file_content}"
            else:
                clean_message = f"请分析这个文件:\n\n{file_content}"
    
    clean_history = validate_history(history)
    
    # 1. 准备 API 请求所需的消息格式
    # 系统提示 - 更安全的系统提示
    api_messages = [{
        'role': 'system', 
        'content': 'You are a helpful, harmless, and honest assistant. Do not provide harmful, illegal, or inappropriate content.'
    }]
    
    # 添加历史对话
    api_messages.extend(clean_history)
        
    # 添加当前用户消息
    api_messages.append({'role': 'user', 'content': clean_message})

    # 2. 调用模型 API 并开启流式响应
    try:
        stream = client.chat.completions.create(
            model=MODEL_ID,
            messages=api_messages,
            stream=True,
            max_tokens=max_tokens,  # 用户可控制的响应长度
            temperature=temperature,  # 用户可控制的随机性
        )
    except Exception as e:
        error_msg = f"API 调用失败: {str(e)[:100]}..."  # 限制错误消息长度
        yield clean_history + [{"role": "user", "content": clean_message}, {"role": "assistant", "content": error_msg}]
        return

    # 3. 处理流式响应并更新 UI
    # 首先，将用户的消息添加到历史记录中，AI 的回复暂时为空
    user_msg_with_timestamp = format_message_with_timestamp(clean_message, "user")
    clean_history.extend([
        {"role": "user", "content": user_msg_with_timestamp},
        {"role": "assistant", "content": ""}
    ])
    
    # 逐块接收和处理流式数据
    bot_response = ""
    try:
        for chunk in stream:
            if hasattr(chunk, 'choices') and len(chunk.choices) > 0:
                content = chunk.choices[0].delta.content
                if content is not None:
                    bot_response += content
                    # 限制响应长度
                    if len(bot_response) > MAX_MESSAGE_LENGTH:
                        bot_response = bot_response[:MAX_MESSAGE_LENGTH] + "..."
                        break
                    
                    # 更新历史记录中最后一条（也就是当前 AI）的回复
                    ai_msg_with_timestamp = format_message_with_timestamp(bot_response, "assistant")
                    clean_history[-1]["content"] = ai_msg_with_timestamp
                    # 通过 yield 更新 Gradio Chatbot UI
                    yield clean_history
    except Exception as e:
        error_msg = f"流式响应处理失败: {str(e)[:100]}..."
        error_msg_with_timestamp = format_message_with_timestamp(error_msg, "assistant")
        clean_history[-1]["content"] = error_msg_with_timestamp
        yield clean_history

# --- Gradio UI 界面构建 ---

# 自定义CSS样式
custom_css = """
#chatbot { 
    min-height: 600px;
    border-radius: 10px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
}
.message-timestamp {
    font-size: 0.8em;
    color: #666;
    margin-bottom: 5px;
}
.export-button {
    background: linear-gradient(45deg, #4CAF50, #45a049);
    color: white;
    border: none;
    border-radius: 5px;
    padding: 10px 20px;
    cursor: pointer;
    transition: all 0.3s ease;
}
.export-button:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 8px rgba(0,0,0,0.2);
}
.parameter-panel {
    background: #f5f5f5;
    padding: 15px;
    border-radius: 10px;
    margin: 10px 0;
    border: 1px solid #e0e0e0;
}
.file-upload {
    border: 2px dashed #4CAF50;
    border-radius: 10px;
    padding: 20px;
    text-align: center;
    transition: all 0.3s ease;
    background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
}
.file-upload:hover {
    border-color: #45a049;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
}
.status-message {
    padding: 10px;
    border-radius: 5px;
    margin: 5px 0;
    font-weight: bold;
}
.success {
    background-color: #d4edda;
    color: #155724;
    border: 1px solid #c3e6cb;
}
.error {
    background-color: #f8d7da;
    color: #721c24;
    border: 1px solid #f5c6cb;
}
"""

with gr.Blocks(theme=gr.themes.Soft(), css=custom_css) as demo:
    gr.Markdown(
        """
        # 🤖 Qwen3 大模型对话应用
        
        这是一个基于 Gradio 和 ModelScope Qwen3 模型 API 构建的 AI 聊天机器人。
        
        - **持续对话**: 应用会记录您的对话历史，AI 的回答会基于上下文。
        - **流式输出**: AI 的回答会像打字一样逐字显示，提升交互体验。
        - **一键清空**: 点击“清除”按钮可以随时开始新的对话。
        """
    )
    
    chatbot = gr.Chatbot(
        label="对话窗口",
        type="messages",
        elem_id="chatbot"
    )
    
    # 参数控制面板
    with gr.Accordion("🎛️ AI 参数设置", open=False):
        with gr.Row():
            temperature_slider = gr.Slider(
                minimum=0.1,
                maximum=2.0,
                value=0.7,
                step=0.1,
                label="创造性 (Temperature)",
                info="数值越高，回答越有创意但可能不够准确"
            )
            max_tokens_slider = gr.Slider(
                minimum=100,
                maximum=MAX_OUTPUT_TOKENS,
                value=DEFAULT_OUTPUT_TOKENS,
                step=100,
                label="最大回复长度 (Max Tokens)",
                info=f"限制AI回复的最大token数 (1 token ≈ 0.75个中文字符，最大{MAX_OUTPUT_TOKENS})"
            )
        
        # API信息显示
        with gr.Accordion("📊 API信息", open=False):
            gr.Markdown(get_api_info())
    
    with gr.Row():
        msg_textbox = gr.Textbox(
            scale=4,
            show_label=False,
            placeholder="请输入您的问题，然后按 Enter 键或点击“发送”按钮",
            container=False,
        )
        submit_btn = gr.Button("发送", variant="primary", scale=1, min_width=0)

    with gr.Row():
        file_upload = gr.File(
            label="📎 拖拽文件到此处或点击上传 (支持文本文件和图片)",
            file_types=[".txt", ".md", ".py", ".js", ".html", ".css", ".json", ".xml", ".csv", 
                       ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"],
            file_count="single"
        )
    
    # 功能按钮区域
    with gr.Row():
        export_btn = gr.Button("📥 导出对话", variant="secondary", scale=1)
        copy_btn = gr.Button("📋 复制最后回复", variant="secondary", scale=1)
        clear_btn = gr.ClearButton(
            [msg_textbox, chatbot, file_upload], 
            value="🗑️ 清除对话", 
            variant="stop",
            scale=1
        )
    
    # 导出文件下载组件和状态显示
    export_file = gr.File(label="📥 导出的对话文件", visible=False)
    status_display = gr.Textbox(
        label="📢 操作状态", 
        placeholder="操作状态将在这里显示...",
        interactive=False,
        max_lines=2
    )



    # --- 事件绑定 ---
    
    # 绑定“发送”按钮的点击事件
    submit_btn.click(predict, [msg_textbox, chatbot, file_upload, temperature_slider, max_tokens_slider], chatbot)
    
    # 绑定文本框的回车事件
    msg_textbox.submit(predict, [msg_textbox, chatbot, file_upload, temperature_slider, max_tokens_slider], chatbot)
    
    # 绑定导出按钮
    export_btn.click(
        handle_export,
        [chatbot],
        [export_file, status_display]
    )
    
    # 绑定复制按钮
    copy_btn.click(
        copy_last_response,
        [chatbot],
        status_display
    )
    
    # 主题切换功能（简单实现）
    def toggle_theme():
        return "🌞 浅色主题" if "🌓" in theme_btn.value else "🌓 切换主题"
    
    # 清空文本框，为下一次输入做准备
    submit_btn.click(lambda: "", None, msg_textbox)
    msg_textbox.submit(lambda: "", None, msg_textbox)


if __name__ == "__main__":
    # 启动 Gradio 应用
    # share=True 会创建一个公开链接，方便分享
    demo.launch(share=True)
