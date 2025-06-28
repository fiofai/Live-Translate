import os
import logging
import asyncio
import numpy as np
import soundfile as sf
from typing import Optional, List, Dict, Any
import tempfile
import queue
import threading
import time

# 导入配置
from config import Config

class AudioInputManager:
    """音频输入管理器，处理麦克风输入和语音识别"""
    
    def __init__(self):
        self.config = Config()
        self.logger = logging.getLogger("audio_input")
        
        # 音频参数
        self.sample_rate = 16000  # Whisper要求16kHz
        self.chunk_size = 4096
        self.channels = 1
        
        # 音频队列
        self.audio_queue = asyncio.Queue(maxsize=100)
        
        # 语音识别模型
        self.whisper_model = None
        self.whisper_model_name = self.config.whisper_model
        
        # 模拟麦克风输入的标志
        self.use_mock_input = os.environ.get("USE_MOCK_INPUT", "false").lower() == "true"
        
        # 初始化标志
        self.initialized = False
        self.running = False
        
        # 音频输入线程
        self.input_thread = None
    
    async def initialize(self):
        """初始化音频输入和语音识别"""
        if self.initialized:
            return
            
        try:
            # 初始化语音识别模型
            await self._initialize_whisper()
            
            # 启动音频输入线程
            self.running = True
            if self.use_mock_input:
                self.input_thread = threading.Thread(target=self._mock_audio_input_thread)
            else:
                self.input_thread = threading.Thread(target=self._audio_input_thread)
                
            self.input_thread.daemon = True
            self.input_thread.start()
            
            self.initialized = True
            self.logger.info("音频输入管理器初始化成功")
            
        except Exception as e:
            self.logger.error(f"音频输入管理器初始化失败: {str(e)}")
            raise
    
    async def cleanup(self):
        """清理资源"""
        self.running = False
        if self.input_thread and self.input_thread.is_alive():
            self.input_thread.join(timeout=2.0)
            
        # 清空队列
        while not self.audio_queue.empty():
            try:
                self.audio_queue.get_nowait()
            except:
                pass
                
        self.logger.info("音频输入管理器已清理")
    
    async def _initialize_whisper(self):
        """初始化Whisper模型"""
        try:
            # 优先使用Faster-Whisper
            try:
                from faster_whisper import WhisperModel
                
                # 检查CUDA可用性
                import torch
                device = "cuda" if torch.cuda.is_available() else "cpu"
                compute_type = "float16" if device == "cuda" else "int8"
                
                self.logger.info(f"加载Faster-Whisper模型 {self.whisper_model_name} 到 {device}...")
                self.whisper_model = WhisperModel(
                    self.whisper_model_name,
                    device=device,
                    compute_type=compute_type
                )
                self.whisper_type = "faster"
                self.logger.info(f"Faster-Whisper模型加载成功，使用{device}和{compute_type}计算")
                
            except ImportError:
                # 回退到原始Whisper
                import whisper
                
                self.logger.info(f"加载原始Whisper模型 {self.whisper_model_name}...")
                self.whisper_model = whisper.load_model(self.whisper_model_name)
                self.whisper_type = "original"
                self.logger.info("原始Whisper模型加载成功")
                
        except Exception as e:
            self.logger.error(f"Whisper模型加载失败: {str(e)}")
            raise
    
    def _audio_input_thread(self):
        """音频输入线程，从麦克风获取音频"""
        try:
            import pyaudio
            
            # 初始化PyAudio
            p = pyaudio.PyAudio()
            
            # 打开音频流
            stream = p.open(
                format=pyaudio.paFloat32,
                channels=self.channels,
                rate=self.sample_rate,
                input=True,
                frames_per_buffer=self.chunk_size
            )
            
            self.logger.info("麦克风输入已启动")
            
            # 读取音频数据
            while self.running:
                try:
                    # 读取音频数据
                    data = stream.read(self.chunk_size, exception_on_overflow=False)
                    
                    # 转换为numpy数组
                    audio_chunk = np.frombuffer(data, dtype=np.float32)
                    
                    # 添加到队列
                    asyncio.run_coroutine_threadsafe(
                        self.audio_queue.put(audio_chunk),
                        asyncio.get_event_loop()
                    )
                    
                except Exception as e:
                    self.logger.error(f"读取音频数据出错: {str(e)}")
                    time.sleep(0.1)
            
            # 关闭流
            stream.stop_stream()
            stream.close()
            p.terminate()
            
        except Exception as e:
            self.logger.error(f"音频输入线程出错: {str(e)}")
            self.logger.info("切换到模拟音频输入模式")
            
            # 切换到模拟输入
            self._mock_audio_input_thread()
    
    def _mock_audio_input_thread(self):
        """模拟音频输入线程，生成静音或测试音频"""
        self.logger.info("使用模拟音频输入")
        
        # 生成静音
        silence = np.zeros(self.chunk_size, dtype=np.float32)
        
        while self.running:
            try:
                # 添加到队列
                asyncio.run_coroutine_threadsafe(
                    self.audio_queue.put(silence.copy()),
                    asyncio.get_event_loop()
                )
                
                # 模拟音频帧率
                time.sleep(self.chunk_size / self.sample_rate)
                
            except Exception as e:
                self.logger.error(f"模拟音频输入出错: {str(e)}")
                time.sleep(0.1)
    
    async def get_audio_chunk(self) -> Optional[np.ndarray]:
        """获取音频数据块"""
        if not self.initialized:
            return None
            
        try:
            # 从队列获取音频数据
            return await self.audio_queue.get()
        except Exception as e:
            self.logger.error(f"获取音频数据出错: {str(e)}")
            return None
    
    async def transcribe_audio(self, audio_data: np.ndarray) -> Optional[str]:
        """
        使用Whisper识别音频
        
        Args:
            audio_data: 音频数据
            
        Returns:
            识别结果文本，如果识别失败则返回None
        """
        if self.whisper_model is None or audio_data is None:
            return None
            
        try:
            # 创建临时文件
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                temp_path = temp_file.name
                
            # 写入音频数据
            sf.write(temp_path, audio_data, self.sample_rate)
            
            # 使用Whisper识别
            if self.whisper_type == "faster":
                # Faster-Whisper
                segments, _ = self.whisper_model.transcribe(
                    temp_path,
                    language="zh",
                    task="transcribe",
                    vad_filter=True
                )
                
                # 收集文本
                text = " ".join([segment.text for segment in segments])
                
            else:
                # 原始Whisper
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None,
                    lambda: self.whisper_model.transcribe(
                        temp_path,
                        language="zh",
                        task="transcribe"
                    )
                )
                
                text = result["text"]
            
            # 删除临时文件
            try:
                os.unlink(temp_path)
            except:
                pass
                
            # 返回识别结果
            return text.strip() if text else None
            
        except Exception as e:
            self.logger.error(f"音频识别出错: {str(e)}")
            return None 