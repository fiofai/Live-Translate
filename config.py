import os
from dotenv import load_dotenv
import logging

# 加载.env文件（如果存在）
load_dotenv()

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
        
        # 项目路径配置
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.voice_samples_dir = os.path.join(self.base_dir, "voice_samples")
        self.voice_embeddings_dir = os.path.join(self.base_dir, "voice_embeddings")
        
        # 确保必要的目录存在
        self._ensure_dirs_exist()
        
        # Real-Time-Voice-Cloning模型路径
        self.encoder_path = os.path.join(self.base_dir, "encoder", "saved_models", "encoder.pt")
        self.synthesizer_path = os.path.join(self.base_dir, "synthesizer", "saved_models", "synthesizer.pt")
        self.vocoder_path = os.path.join(self.base_dir, "vocoder", "saved_models", "vocoder.pt")
    
    def _get_env(self, name, default=None, required=True):
        """从环境变量获取配置值"""
        value = os.environ.get(name, default)
        if required and value is None:
            self.logger.warning(f"警告: 环境变量 {name} 未设置")
        return value
    
    def _ensure_dirs_exist(self):
        """确保必要的目录存在"""
        dirs = [
            self.voice_samples_dir,
            self.voice_embeddings_dir
        ]
        
        for dir_path in dirs:
            if not os.path.exists(dir_path):
                os.makedirs(dir_path)
                self.logger.info(f"创建目录: {dir_path}")
                
    def get_rtvc_model_paths(self):
        """获取Real-Time-Voice-Cloning模型路径"""
        return {
            "encoder": self.encoder_path,
            "synthesizer": self.synthesizer_path,
            "vocoder": self.vocoder_path
        } 