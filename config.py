import os
import logging
from dotenv import load_dotenv
from logging.handlers import RotatingFileHandler
import sys

# 加载.env文件（如果存在）
load_dotenv()

# 配置日志
def setup_logging():
    """设置日志配置"""
    log_formatter = logging.Formatter('[%(asctime)s] [%(levelname)s] %(message)s')
    
    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(log_formatter)
    
    # 文件处理器（可选）
    file_handler = RotatingFileHandler(
        'app.log', 
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    file_handler.setFormatter(log_formatter)
    
    # 配置根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    
    return root_logger

class Config:
    """配置类，用于管理系统配置和环境变量"""
    
    def __init__(self):
        # 设置日志
        self.logger = logging.getLogger("config")
        
        # LiveKit配置
        self.livekit_url = self._get_env("LIVEKIT_URL")
        self.livekit_api_key = self._get_env("LIVEKIT_API_KEY")
        self.livekit_api_secret = self._get_env("LIVEKIT_API_SECRET")
        
        # 翻译API配置
        self.deepl_api_key = self._get_env("DEEPL_API_KEY", required=False)
        self.microsoft_translator_api_key = self._get_env("MICROSOFT_TRANSLATOR_API_KEY", required=False)
        
        # 检查至少有一个翻译API可用
        if not self.deepl_api_key and not self.microsoft_translator_api_key:
            self.logger.warning("警告: 没有配置任何翻译API密钥，翻译功能将不可用")
        
        # TTS引擎配置
        self.tts_engine = self._get_env("TTS_ENGINE", default="gtts")
        
        # 语音识别配置 (Whisper模型大小)
        self.whisper_model = self._get_env("WHISPER_MODEL", default="small")
        
        # Hugging Face配置
        self.hf_token = self._get_env("HF_TOKEN", required=True)
        self.hf_repo = self._get_env("HF_REPO", default="fiofai/voice-profiles")
        
        # 临时文件目录
        self.temp_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "temp")
        os.makedirs(self.temp_dir, exist_ok=True)
        
        # 模型文件名
        self.model_files = {
            "encoder": "encoder.pt",
            "synthesizer": "synthesizer.pt",
            "vocoder": "vocoder.pt"
        }
    
    def _get_env(self, name, default=None, required=True):
        """从环境变量获取配置值"""
        value = os.environ.get(name, default)
        if required and value is None:
            self.logger.warning(f"警告: 环境变量 {name} 未设置")
        return value
    
    def get_hf_model_path(self, model_type):
        """获取Hugging Face上的模型路径"""
        if model_type not in self.model_files:
            self.logger.error(f"错误: 未知的模型类型 {model_type}")
            return None
        
        return f"{self.hf_repo}/{self.model_files[model_type]}" 
