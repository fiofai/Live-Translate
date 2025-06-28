# 现场实时语音翻译系统

这是一个功能强大的实时语音翻译系统，可以将中文语音实时转换为多种语言，并通过LiveKit服务广播到各个语言频道，允许用户通过扫描二维码选择自己需要的语言进行收听。

## 系统架构

```
🎙️ Speaker麦克风  
    ↓  
🧠 Whisper本地实时语音识别  
    ↓  
🌐 AI翻译（中文 → 越南语、英文、马来文、泰文、韩文）  
    ↓  
🗣️ TTS语音合成（每种语言生成不同音频）  
    ↓  
📡 使用LiveKit广播每个语言的音频流（多语言频道）  
    ↓  
📱 用户扫码进入网页 → 选择语言 → 听对应翻译的语音  
```

## 功能特点

- 使用Whisper或Faster-Whisper进行实时中文语音识别
- 支持将中文实时翻译成多种语言：
  - 英文
  - 越南语
  - 马来文
  - 泰文
  - 韩文
- 使用Edge-TTS或Google Cloud TTS进行语音合成
- 通过LiveKit将多语言音频并行广播
- 提供网页客户端，支持扫码连接和语言选择

## 本地开发

### 安装依赖

1. 安装Python 3.8或更高版本
2. 安装所需依赖：
   ```
   pip install -r requirements.txt
   ```

### 配置设置

在使用前，请先配置`config.py`文件：

1. 设置LiveKit凭证：
   ```python
   LIVEKIT_API_KEY = "your_api_key_here"
   LIVEKIT_API_SECRET = "your_api_secret_here"
   LIVEKIT_URL = "wss://your-livekit-instance.livekit.cloud"
   ```

2. 如果使用Google TTS，请配置Google Cloud凭证：
   ```python
   GOOGLE_CREDENTIALS_FILE = "path/to/your/google_credentials.json"
   ```

### 本地运行

#### 启动翻译服务

```bash
python main.py [选项]
```

选项:
- `--use-faster-whisper`: 使用Faster-Whisper模型（推荐，速度更快）
- `--use-google-translate`: 使用Google翻译（在线，更准确）
- `--whisper-model MODEL`: 指定Whisper模型大小 (tiny, base, small, medium, large)
- `--room-name NAME`: 指定LiveKit房间名称
- `--use-simulation`: 使用模拟音频输入（无麦克风环境）

#### 启动Web服务器

```bash
python web_server.py [选项]
```

选项:
- `--host HOST`: 指定服务器主机 (默认: 0.0.0.0)
- `--port PORT`: 指定服务器端口 (默认: 8080)
- `--with-translator`: 自动启动翻译服务

#### 使用客户端

1. 启动翻译服务和Web服务器
2. 服务启动后会生成二维码文件 `translator_qrcode.png`
3. 访问 `http://[服务器IP]:8080/qrcode` 查看二维码
4. 用手机扫描二维码或直接访问提供的URL
5. 在网页中选择需要的语言即可开始收听翻译

## 部署到Render

您可以轻松地将此项目部署到Render平台：

1. 在Render上创建一个新的Web Service
2. 连接到您的GitHub仓库
3. 设置以下环境变量：
   - `LIVEKIT_URL`: 您的LiveKit Websocket URL
   - `LIVEKIT_API_KEY`: 您的LiveKit API密钥
   - `LIVEKIT_API_SECRET`: 您的LiveKit API密钥密文
   - `GOOGLE_CREDENTIALS_FILE`（可选）: 如果使用Google TTS，可以提供凭证JSON内容
4. 部署配置：
   - 运行时环境: Python 3
   - 构建命令: `pip install -r requirements.txt`
   - 启动命令: `gunicorn web_server:app`
5. 点击部署

Render会自动安装依赖并启动服务。部署后，您可以通过以下方式访问应用：
- Web界面: `https://[您的应用名].onrender.com`
- 二维码页面: `https://[您的应用名].onrender.com/qrcode`

## 文件结构

```
live-translator/
├── main.py            # 主程序，负责识别 → 翻译 → 合成 → 推流
├── translator.py      # 翻译模块
├── tts_engine.py      # TTS合成模块
├── voice_clone_module.py     # 语音克隆模块
├── streamer.py        # LiveKit推流模块
├── audio_input.py     # 麦克风输入模块
├── config.py          # LiveKit配置/API密钥等
├── web_server.py      # Web服务器
├── web/               # 客户端网页文件
│   ├── index.html     # 用户端网页（扫码后选择语言播放）
│   └── js/            # JavaScript文件
│       ├── client.js  # 客户端逻辑
│       └── voice_recorder.js # 录音功能
└── requirements.txt   # 所需依赖库列表
```

## 注意事项

- 首次运行时，系统会下载Whisper模型和必要的语言包
- 翻译和TTS功能需要互联网连接
- 如果使用Google Cloud TTS，需要有效的Google Cloud凭证
- LiveKit服务需要有效的API密钥和API密钥，可以在[LiveKit Cloud](https://livekit.io)注册免费账号获取

## 技术实现

- **语音识别**: 使用OpenAI的Whisper模型进行实时语音识别
- **翻译**: 支持Google翻译API和Argos-Translate离线翻译
- **TTS合成**: 支持Edge-TTS(离线)和Google Cloud TTS(在线)
- **音频流处理**: 使用PyAudio或SoundDevice进行麦克风输入
- **实时音频广播**: 使用LiveKit进行WebRTC音频广播
- **网页客户端**: 使用LiveKit Web SDK实现音频接收和播放

## 贡献与问题反馈

如有问题或改进建议，请提交Issue或Pull Request。

## 许可证

MIT 