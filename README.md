# Gradio AI 对话应用

基于 Gradio 和 ModelScope Qwen3 模型的安全 AI 聊天机器人。

## 🔒 安全特性

- ✅ 环境变量管理 API 密钥
- ✅ 输入验证和清理
- ✅ 速率限制保护
- ✅ 消息长度限制
- ✅ 对话历史长度限制
- ✅ 错误处理和日志记录

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置 API 密钥

**方法一：使用 .env 文件（推荐）**

```bash
# 复制示例文件
cp .env.example .env

# 编辑 .env 文件，添加您的 API 密钥
# MODELSCOPE_API_KEY=your_actual_api_key_here
```

**方法二：设置环境变量**

```bash
# Linux/macOS
export MODELSCOPE_API_KEY=your_actual_api_key_here

# Windows
set MODELSCOPE_API_KEY=your_actual_api_key_here
```

### 3. 运行应用

```bash
python Gradio-Conversation.py
```

## ⚙️ 配置选项

您可以通过环境变量自定义以下设置：

- `MODELSCOPE_API_KEY`: ModelScope API 密钥（必需）
- `MAX_MESSAGE_LENGTH`: 单条消息最大长度（默认：16000字符）
- `MAX_HISTORY_LENGTH`: 对话历史最大条数（默认：50）
- `RATE_LIMIT_DELAY`: 请求间隔秒数（默认：1）
- `MAX_OUTPUT_TOKENS`: API最大输出token数（默认：32000）
- `DEFAULT_OUTPUT_TOKENS`: 默认输出token数（默认：8000）

## 🛡️ 安全最佳实践

1. **永远不要**在代码中硬编码 API 密钥
2. 将 `.env` 文件添加到 `.gitignore`
3. 定期轮换 API 密钥
4. 在生产环境中使用更严格的速率限制
5. 考虑添加用户认证和授权

## 📁 项目结构

```
.
├── Gradio-Conversation.py  # 主应用文件
├── requirements.txt        # Python 依赖
├── .env.example           # 环境变量示例
├── .gitignore            # Git 忽略文件
└── README.md             # 项目文档
```

## 🔧 故障排除

### API 密钥错误
确保您的 `MODELSCOPE_API_KEY` 环境变量已正确设置。

### 依赖问题
如果遇到导入错误，请确保所有依赖都已安装：
```bash
pip install --upgrade -r requirements.txt
```

### 网络连接问题
确保您的网络可以访问 ModelScope API 端点。

## 📝 许可证

本项目仅供学习和研究使用。请遵守 ModelScope 的使用条款。