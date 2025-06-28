# 实时语音翻译系统

一个实时语音翻译系统，允许演讲者用中文讲话，观众通过手机连接到网页选择语言后，实时收听翻译后的语音。翻译员的声音通过语音克隆技术进行合成。

## 功能特点

- **实时语音识别**：使用 Faster-Whisper 实时识别中文语音
- **多语言翻译**：支持将中文翻译成越南语、印尼语、韩文、泰文和英文
- **语音克隆**：使用 Real-Time-Voice-Cloning 技术，将翻译后的文本合成为具有预先录制好的翻译员声音的语音
- **实时音频流广播**：通过 LiveKit 将不同语言的合成语音实时广播到各自的语言频道
- **简洁的网页客户端**：观众可以扫描二维码或直接访问链接，选择语言频道，实时收听翻译后的语音

## 系统架构

系统由以下核心模块组成：

1. **音频输入模块**：处理麦克风输入和语音识别
2. **翻译模块**：支持 DeepL 和 Microsoft Translator API，进行多语言翻译
3. **语音克隆模块**：使用 Real-Time-Voice-Cloning 技术合成翻译员声音
4. **TTS 引擎**：作为语音克隆的兜底方案
5. **流媒体模块**：管理与 LiveKit 的连接和音频流推送
6. **Web 服务器**：提供网页客户端和 API 接口

## 安装指南

### 前提条件

- Python 3.8 或更高版本
- FFmpeg（用于音频处理）
- 适用于 PyTorch 的 CUDA（可选，用于加速语音克隆）

### 安装步骤

1. **克隆项目仓库**

```bash
git clone https://github.com/yourusername/live-translate-system.git
cd live-translate-system
```

2. **安装依赖**

```bash
pip install -r requirements.txt
```

3. **下载 Real-Time-Voice-Cloning 模型**

在项目根目录下创建以下目录结构：

```
encoder/saved_models/
synthesizer/saved_models/
vocoder/saved_models/
```

下载预训练模型并放置在相应目录中：
- encoder.pt → encoder/saved_models/
- synthesizer.pt → synthesizer/saved_models/
- vocoder.pt → vocoder/saved_models/

4. **配置环境变量**

创建 `.env` 文件，参考 `.env.example` 进行配置：

```
# LiveKit配置
LIVEKIT_URL=wss://your-livekit-instance.livekit.cloud
LIVEKIT_API_KEY=your-api-key
LIVEKIT_API_SECRET=your-api-secret

# 翻译API配置
DEEPL_API_KEY=your-deepl-api-key
MICROSOFT_TRANSLATOR_API_KEY=your-microsoft-translator-api-key

# TTS引擎配置 (gtts或azure)
TTS_ENGINE=gtts

# Azure TTS配置 (如果使用Azure TTS)
AZURE_SPEECH_KEY=your-azure-speech-key
AZURE_SPEECH_REGION=eastus

# Whisper模型大小 (tiny, base, small, medium, large)
WHISPER_MODEL=small

# 应用基础URL (用于生成二维码)
BASE_URL=https://your-app-url.com

# 模拟音频输入 (true或false)
USE_MOCK_INPUT=false
```

## 本地运行

1. **启动应用**

```bash
python main.py
```

2. **访问网页客户端**

打开浏览器访问：http://localhost:8000

3. **录制语音样本**

在网页客户端中，点击"开始录音"按钮录制语音样本，用于语音克隆。

4. **扫描二维码**

访问 http://localhost:8000/qrcode 获取二维码，观众可以扫描二维码连接到翻译系统。

## 部署到 Render

1. **创建新的 Web 服务**

在 Render 控制台中创建一个新的 Web 服务，并连接到您的 GitHub 仓库。

2. **配置构建命令**

```bash
apt-get update && apt-get install -y ffmpeg && pip install -r requirements.txt
```

3. **配置启动命令**

```bash
python main.py
```

4. **设置环境变量**

在 Render 控制台中，添加与 `.env` 文件中相同的环境变量。

5. **部署服务**

点击"Create Web Service"按钮开始部署。

## 使用方法

1. **演讲者端**：
   - 确保麦克风正常工作
   - 系统会自动识别中文语音并进行翻译

2. **观众端**：
   - 扫描二维码或访问提供的链接
   - 选择需要的语言
   - 调整音量，开始收听翻译后的语音

## 技术说明

- **语音识别**：使用 Faster-Whisper 进行实时中文语音识别
- **翻译 API**：支持 DeepL API 和 Microsoft Translator API，可以根据配置选择使用
- **语音克隆**：使用 Real-Time-Voice-Cloning 技术，需要预先录制翻译员的语音样本
- **TTS 引擎**：当语音克隆不可用时，使用 gTTS 或 Azure TTS 作为兜底方案
- **流媒体服务**：使用 LiveKit 进行实时音频流广播
- **Web 框架**：使用 FastAPI 构建后端服务和 API

## 注意事项

- 确保 FFmpeg 已正确安装，Real-Time-Voice-Cloning 依赖它进行音频处理
- 语音克隆需要较高的计算资源，建议使用具有 CUDA 支持的环境
- 免费的翻译 API 有使用限制，请注意配额

## 许可证

MIT

## 联系方式

如有问题或建议，请联系：your-email@example.com 