import os
import logging
import asyncio
import tempfile
from typing import Optional, Dict, Any
import numpy as np
import io
from pydub import AudioSegment

# 导入配置
from config import Config

class TTSEngine:
    """TTS引擎，作为语音克隆的兜底方案"""
    
    def __init__(self):
        self.config = Config()
        self.logger = logging.getLogger("tts_engine")
        
        # 获取TTS引擎类型
        self.engine_type = self.config.tts_engine.lower()
        self.logger.info(f"使用TTS引擎: {self.engine_type}")
        
        # 初始化TTS引擎
        self._initialize_engine()
        
        # 语言代码映射
        self.lang_code_map = {
            # gTTS语言代码
            "gtts": {
                "en": "en",
                "zh": "zh-cn",
                "vi": "vi",
                "id": "id",
                "ko": "ko",
                "th": "th"
            },
            # Azure TTS语言代码
            "azure": {
                "en": "en-US",
                "zh": "zh-CN",
                "vi": "vi-VN",
                "id": "id-ID",
                "ko": "ko-KR",
                "th": "th-TH"
            }
        }
    
    def _initialize_engine(self):
        """初始化TTS引擎"""
        if self.engine_type == "gtts":
            try:
                from gtts import gTTS
                self.gtts_available = True
                self.logger.info("gTTS引擎初始化成功")
            except Exception as e:
                self.logger.error(f"gTTS引擎初始化失败: {str(e)}")
                self.gtts_available = False
        
        elif self.engine_type == "azure":
            try:
                import azure.cognitiveservices.speech as speechsdk
                
                # 检查Azure Speech API密钥
                self.azure_speech_key = os.environ.get("AZURE_SPEECH_KEY")
                self.azure_speech_region = os.environ.get("AZURE_SPEECH_REGION", "eastus")
                
                if not self.azure_speech_key:
                    self.logger.warning("未设置Azure Speech API密钥，Azure TTS不可用")
                    self.azure_available = False
                else:
                    self.speech_config = speechsdk.SpeechConfig(
                        subscription=self.azure_speech_key,
                        region=self.azure_speech_region
                    )
                    self.azure_available = True
                    self.logger.info("Azure TTS引擎初始化成功")
            except Exception as e:
                self.logger.error(f"Azure TTS引擎初始化失败: {str(e)}")
                self.azure_available = False
        
        else:
            self.logger.warning(f"未知的TTS引擎类型: {self.engine_type}，将使用gTTS作为默认引擎")
            self.engine_type = "gtts"
            try:
                from gtts import gTTS
                self.gtts_available = True
                self.logger.info("gTTS引擎初始化成功")
            except Exception as e:
                self.logger.error(f"gTTS引擎初始化失败: {str(e)}")
                self.gtts_available = False
    
    async def synthesize(self, text: str, lang_code: str) -> Optional[np.ndarray]:
        """
        将文本合成为语音
        
        Args:
            text: 要合成的文本
            lang_code: 语言代码
            
        Returns:
            合成的音频数据，如果合成失败则返回None
        """
        if not text:
            return None
            
        # 根据引擎类型选择合成方法
        if self.engine_type == "gtts" and self.gtts_available:
            return await self._synthesize_gtts(text, lang_code)
        elif self.engine_type == "azure" and self.azure_available:
            return await self._synthesize_azure(text, lang_code)
        else:
            # 如果配置的引擎不可用，尝试使用gTTS
            self.logger.warning(f"配置的TTS引擎 {self.engine_type} 不可用，尝试使用gTTS")
            return await self._synthesize_gtts(text, lang_code)
    
    async def _synthesize_gtts(self, text: str, lang_code: str) -> Optional[np.ndarray]:
        """使用gTTS合成语音"""
        try:
            from gtts import gTTS
            
            # 转换语言代码
            gtts_lang = self.lang_code_map["gtts"].get(lang_code)
            if not gtts_lang:
                self.logger.warning(f"gTTS不支持语言: {lang_code}，使用英语作为回退")
                gtts_lang = "en"
            
            # 创建临时文件
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
                temp_path = temp_file.name
            
            # 在事件循环中运行阻塞操作
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: gTTS(text=text, lang=gtts_lang).save(temp_path)
            )
            
            # 读取音频文件
            audio = AudioSegment.from_mp3(temp_path)
            
            # 转换为numpy数组
            samples = np.array(audio.get_array_of_samples())
            
            # 如果是立体声，转换为单声道
            if audio.channels == 2:
                samples = samples.reshape((-1, 2))
                samples = samples.mean(axis=1)
            
            # 转换为float32，范围为[-1, 1]
            samples = samples.astype(np.float32) / (2**15 if samples.dtype == np.int16 else 2**31)
            
            # 删除临时文件
            try:
                os.unlink(temp_path)
            except:
                pass
                
            return samples
            
        except Exception as e:
            self.logger.error(f"gTTS合成出错: {str(e)}")
            return None
    
    async def _synthesize_azure(self, text: str, lang_code: str) -> Optional[np.ndarray]:
        """使用Azure TTS合成语音"""
        try:
            import azure.cognitiveservices.speech as speechsdk
            
            # 转换语言代码
            azure_lang = self.lang_code_map["azure"].get(lang_code)
            if not azure_lang:
                self.logger.warning(f"Azure TTS不支持语言: {lang_code}，使用英语作为回退")
                azure_lang = "en-US"
            
            # 设置语音
            self.speech_config.speech_synthesis_language = azure_lang
            
            # 创建语音合成器
            synthesizer = speechsdk.SpeechSynthesizer(speech_config=self.speech_config, audio_config=None)
            
            # 创建事件
            done = asyncio.Event()
            audio_data = io.BytesIO()
            
            # 定义回调
            def stream_callback(evt):
                audio_data.write(evt.audio_data)
                
            def completed_cb(evt):
                done.set()
                
            # 设置回调
            synthesizer.synthesis_started.connect(lambda evt: None)
            synthesizer.synthesizing.connect(lambda evt: None)
            synthesizer.synthesis_completed.connect(completed_cb)
            synthesizer.synthesis_canceled.connect(lambda evt: done.set())
            synthesizer.synthesis_word_boundary.connect(lambda evt: None)
            synthesizer.synthesizing.connect(stream_callback)
            
            # 开始合成
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: synthesizer.speak_text_async(text).get()
            )
            
            # 等待合成完成
            await done.wait()
            
            # 转换为AudioSegment
            audio_data.seek(0)
            audio = AudioSegment.from_wav(audio_data)
            
            # 转换为numpy数组
            samples = np.array(audio.get_array_of_samples())
            
            # 如果是立体声，转换为单声道
            if audio.channels == 2:
                samples = samples.reshape((-1, 2))
                samples = samples.mean(axis=1)
            
            # 转换为float32，范围为[-1, 1]
            samples = samples.astype(np.float32) / (2**15 if samples.dtype == np.int16 else 2**31)
            
            return samples
            
        except Exception as e:
            self.logger.error(f"Azure TTS合成出错: {str(e)}")
            return None 