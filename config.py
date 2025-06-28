"""
配置文件，存储LiveKit凭证和其他设置
"""

import os

# LiveKit配置 - 从环境变量中读取
LIVEKIT_API_KEY = os.environ.get("LIVEKIT_API_KEY", "your_api_key_here")  # 从环境变量读取或使用默认值
LIVEKIT_API_SECRET = os.environ.get("LIVEKIT_API_SECRET", "your_api_secret_here")  # 从环境变量读取或使用默认值
LIVEKIT_URL = os.environ.get("LIVEKIT_URL", "wss://your-livekit-instance.livekit.cloud")  # 从环境变量读取或使用默认值

# 翻译语言配置
TARGET_LANGUAGES = {
    "en": "英文",
    "vi": "越南语",
    "ms": "马来文",
    "th": "泰文",
    "ko": "韩文"
}

# 音频配置
SAMPLE_RATE = 16000
CHUNK_SIZE = 1024
CHANNELS = 1

# Whisper配置
WHISPER_MODEL = "medium"  # 可选: tiny, base, small, medium, large

# TTS配置
TTS_ENGINE = "edge-tts"  # 可选: edge-tts, google
GOOGLE_CREDENTIALS_FILE = os.environ.get("GOOGLE_CREDENTIALS_FILE", "google_credentials.json")  # 从环境变量读取或使用默认值 