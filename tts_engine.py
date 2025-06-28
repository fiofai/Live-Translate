"""
TTS语音合成模块，负责将翻译后的文本转换为语音
支持Edge TTS（离线）、Google Cloud TTS（在线）和语音克隆
"""

import os
import asyncio
import tempfile
from typing import Dict, Optional
import edge_tts
import numpy as np
from pydub import AudioSegment
from config import TTS_ENGINE, GOOGLE_CREDENTIALS_FILE, SAMPLE_RATE
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 每种语言的语音配置
VOICE_CONFIGS = {
    "en": {
        "edge": "en-US-ChristopherNeural",
        "google": "en-US-Neural2-J"
    },
    "vi": {
        "edge": "vi-VN-HoaiMyNeural",
        "google": "vi-VN-Neural2-A"
    },
    "ms": {
        "edge": "ms-MY-YasminNeural",
        "google": "ms-MY-Neural2-A"
    },
    "th": {
        "edge": "th-TH-PremwadeeNeural",
        "google": "th-TH-Neural2-C"
    },
    "ko": {
        "edge": "ko-KR-SunHiNeural",
        "google": "ko-KR-Neural2-C"
    }
}

class TTSEngine:
    def __init__(self, engine_type=TTS_ENGINE):
        """
        初始化TTS引擎
        
        Args:
            engine_type: TTS引擎类型，"edge-tts"或"google"或"voice-clone"
        """
        self.engine_type = engine_type
        self.google_client = None
        self.temp_dir = tempfile.mkdtemp(prefix="live_translator_tts_")
        logger.info(f"已初始化TTS引擎: {engine_type}")
        
        # 如果使用Google TTS，初始化客户端
        if engine_type == "google":
            try:
                from google.cloud import texttospeech
                
                # 检查环境变量是否已设置
                if "GOOGLE_APPLICATION_CREDENTIALS" not in os.environ:
                    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = GOOGLE_CREDENTIALS_FILE
                
                self.google_client = texttospeech.TextToSpeechClient()
                logger.info("已初始化Google Cloud TTS客户端")
            except Exception as e:
                logger.error(f"初始化Google TTS客户端时出错: {e}")
                logger.info("将回退使用Edge TTS")
                self.engine_type = "edge-tts"
    
    async def _synthesize_edge_tts(self, text: str, lang: str) -> np.ndarray:
        """
        使用Edge TTS合成语音
        
        Args:
            text: 要合成的文本
            lang: 语言代码
            
        Returns:
            包含音频数据的numpy数组
        """
        if not text:
            return np.array([])
            
        # 获取该语言的语音配置
        voice = VOICE_CONFIGS.get(lang, {}).get("edge", "en-US-ChristopherNeural")
        
        # 创建临时文件
        temp_file = os.path.join(self.temp_dir, f"edge_tts_{lang}_{hash(text)}.mp3")
        
        try:
            # 使用Edge TTS合成语音
            communicate = edge_tts.Communicate(text, voice)
            await communicate.save(temp_file)
            
            # 读取音频文件并转换为numpy数组
            audio = AudioSegment.from_file(temp_file)
            audio = audio.set_frame_rate(SAMPLE_RATE)
            audio = audio.set_channels(1)
            
            # 转换为numpy数组
            samples = np.array(audio.get_array_of_samples())
            
            # 删除临时文件
            if os.path.exists(temp_file):
                os.remove(temp_file)
                
            return samples
        except Exception as e:
            logger.error(f"Edge TTS合成失败: {e}")
            return np.array([])
    
    def _synthesize_google_tts(self, text: str, lang: str) -> np.ndarray:
        """
        使用Google Cloud TTS合成语音
        
        Args:
            text: 要合成的文本
            lang: 语言代码
            
        Returns:
            包含音频数据的numpy数组
        """
        if not text or not self.google_client:
            return np.array([])
            
        from google.cloud import texttospeech
        
        # 获取该语言的语音配置
        voice_name = VOICE_CONFIGS.get(lang, {}).get("google", "en-US-Neural2-J")
        
        try:
            # 设置合成输入
            synthesis_input = texttospeech.SynthesisInput(text=text)
            
            # 设置语音参数
            language_code = "-".join(voice_name.split("-")[:2])
            voice = texttospeech.VoiceSelectionParams(
                language_code=language_code,
                name=voice_name
            )
            
            # 设置音频配置
            audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.LINEAR16,
                sample_rate_hertz=SAMPLE_RATE
            )
            
            # 执行TTS请求
            response = self.google_client.synthesize_speech(
                input=synthesis_input,
                voice=voice,
                audio_config=audio_config
            )
            
            # 转换音频数据为numpy数组
            audio_data = response.audio_content
            temp_file = os.path.join(self.temp_dir, f"google_tts_{lang}_{hash(text)}.wav")
            
            # 保存临时文件
            with open(temp_file, "wb") as f:
                f.write(audio_data)
                
            # 读取音频文件并转换为numpy数组
            audio = AudioSegment.from_file(temp_file)
            samples = np.array(audio.get_array_of_samples())
            
            # 删除临时文件
            if os.path.exists(temp_file):
                os.remove(temp_file)
                
            return samples
        except Exception as e:
            logger.error(f"Google TTS合成失败: {e}")
            return np.array([])
    
    def _synthesize_voice_clone(self, text: str, speaker_embedding: np.ndarray) -> np.ndarray:
        """
        使用语音克隆合成语音
        
        Args:
            text: 要合成的文本
            speaker_embedding: 说话人特征向量
            
        Returns:
            包含音频数据的numpy数组
        """
        if not text or speaker_embedding is None:
            return np.array([])
        
        try:
            # 导入语音克隆模块
            try:
                # 尝试从子模块导入
                from clone_modules.voice_cloning.voice_clone_module import synthesize_speech
                logger.info("从clone_modules.voice_cloning.voice_clone_module导入synthesize_speech成功")
            except ImportError:
                # 如果失败，尝试从兼容层导入
                try:
                    from voice_clone import synthesize_speech
                    logger.info("从voice_clone导入synthesize_speech成功")
                except ImportError as e:
                    logger.error(f"导入synthesize_speech失败: {e}")
                    return np.array([])
            
            # 使用语音克隆合成语音
            waveform = synthesize_speech(text, speaker_embedding)
            if waveform is None:
                logger.warning("语音克隆合成失败，回退到Edge TTS")
                return np.array([])
            
            # 确保采样率正确
            if len(waveform.shape) > 1:
                waveform = waveform.flatten()
            
            return waveform
        except Exception as e:
            logger.error(f"语音克隆合成失败: {e}")
            return np.array([])

    def synthesize_with_voice_clone(self, text, speaker_id):
        """
        使用语音克隆合成语音（通过speaker_id）
        
        Args:
            text: 要合成的文本
            speaker_id: 说话人ID
            
        Returns:
            包含音频数据的numpy数组，如果失败则返回None
        """
        try:
            # 获取说话人特征向量
            try:
                # 尝试从子模块导入
                from clone_modules.voice_cloning.voice_clone_module import get_speaker_embedding
                logger.info("从clone_modules.voice_cloning.voice_clone_module导入get_speaker_embedding成功")
            except ImportError:
                # 如果失败，尝试从兼容层导入
                try:
                    from voice_clone import get_speaker_embedding
                    logger.info("从voice_clone导入get_speaker_embedding成功")
                except ImportError as e:
                    logger.error(f"导入get_speaker_embedding失败: {e}")
                    return None
            
            # 获取说话人特征向量
            speaker_embedding = get_speaker_embedding(speaker_id)
            if speaker_embedding is None:
                logger.error(f"无法获取用户{speaker_id}的特征向量")
                return None
            
            # 使用_synthesize_voice_clone方法合成语音
            waveform = self._synthesize_voice_clone(text, speaker_embedding)
            if len(waveform) == 0:
                logger.error("语音克隆合成失败")
                return None
            
            # 将波形转换为音频数据
            audio_data = (waveform * 32767).astype(np.int16)
            return audio_data
            
        except Exception as e:
            logger.error(f"使用语音克隆合成语音时出错: {e}")
            return None
    
    async def synthesize(self, text: str, lang: str, speaker_embedding: Optional[np.ndarray] = None) -> np.ndarray:
        """
        将文本转换为语音
        
        Args:
            text: 要合成的文本
            lang: 语言代码
            speaker_embedding: 可选的说话人特征向量，用于语音克隆
            
        Returns:
            包含音频数据的numpy数组
        """
        if not text:
            return np.array([])
        
        # 如果提供了speaker_embedding，尝试使用语音克隆
        if speaker_embedding is not None:
            try:
                logger.info("使用语音克隆合成语音")
                samples = self.synthesize_with_voice_clone(text, speaker_embedding)
                if len(samples) > 0:
                    return samples
                logger.warning("语音克隆失败，回退到默认TTS")
            except Exception as e:
                logger.error(f"语音克隆出错，回退到默认TTS: {e}")
        
        # 使用默认TTS引擎
        if self.engine_type == "google" and self.google_client:
            try:
                return self._synthesize_google_tts(text, lang)
            except Exception as e:
                logger.error(f"Google TTS失败，回退到Edge TTS: {e}")
                # 回退到Edge TTS
                return await self._synthesize_edge_tts(text, lang)
        else:
            # 使用Edge TTS
            return await self._synthesize_edge_tts(text, lang)
    
    async def synthesize_multiple(self, texts: Dict[str, str], speaker_embedding: Optional[np.ndarray] = None) -> Dict[str, np.ndarray]:
        """
        将多种语言的文本同时转换为语音
        
        Args:
            texts: 字典，键为语言代码，值为要合成的文本
            speaker_embedding: 可选的说话人特征向量，用于语音克隆
            
        Returns:
            字典，键为语言代码，值为包含音频数据的numpy数组
        """
        results = {}
        
        for lang, text in texts.items():
            if text:
                audio_data = await self.synthesize(text, lang, speaker_embedding)
                results[lang] = audio_data
                
        return results
    
    def cleanup(self):
        """清理临时文件"""
        try:
            import shutil
            if os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir)
                logger.info(f"已清理TTS临时目录: {self.temp_dir}")
        except Exception as e:
            logger.error(f"清理TTS临时目录时出错: {e}")

# 简单测试代码
if __name__ == "__main__":
    async def test_tts():
        # 初始化TTS引擎
        tts_engine = TTSEngine(engine_type="edge-tts")
        
        # 测试文本（多语言）
        test_texts = {
            "en": "Hello, this is a test of the text-to-speech system.",
            "vi": "Xin chào, đây là bài kiểm tra của hệ thống chuyển văn bản thành giọng nói.",
            "ms": "Helo, ini adalah ujian sistem teks ke ucapan.",
            "th": "สวัสดี นี่คือการทดสอบระบบการแปลงข้อความเป็นเสียงพูด",
            "ko": "안녕하세요, 텍스트 음성 변환 시스템의 테스트입니다."
        }
        
        # 测试每种语言
        for lang, text in test_texts.items():
            print(f"正在为{lang}合成语音: {text[:30]}...")
            audio_data = await tts_engine.synthesize(text, lang)
            print(f"已生成{lang}语音，样本数: {len(audio_data)}")
            
        # 测试多语言同时合成
        print("\n测试多语言同时合成...")
        results = await tts_engine.synthesize_multiple(test_texts)
        for lang, audio_data in results.items():
            print(f"已生成{lang}语音，样本数: {len(audio_data)}")
        
        # 测试语音克隆（如果可用）
        try:
            from clone_modules.voice_cloning.voice_clone_module import get_speaker_embedding
            print("\n测试语音克隆...")
            # 尝试获取一个测试用的speaker embedding
            embedding = get_speaker_embedding("test_user")
            if embedding is not None:
                print("找到测试用户的特征向量，测试语音克隆...")
                audio_data = await tts_engine.synthesize(
                    "This is a test of voice cloning technology.", "en", embedding
                )
                print(f"已生成克隆语音，样本数: {len(audio_data)}")
            else:
                print("未找到测试用户的特征向量，跳过语音克隆测试")
        except Exception as e:
            print(f"测试语音克隆时出错: {e}")
        
        # 清理
        tts_engine.cleanup()
    
    # 运行测试
    asyncio.run(test_tts()) 