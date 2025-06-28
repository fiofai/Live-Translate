"""
现场实时语音翻译系统主程序
实现语音识别 → 翻译 → TTS合成 → LiveKit推流的完整流程
"""

import os
import sys
import time
import asyncio
import threading
import queue
import numpy as np
import argparse
import whisper
import torch
from faster_whisper import WhisperModel
import qrcode
from PIL import Image

from audio_input import AudioInput
from translator import Translator
from tts_engine import TTSEngine
from streamer import LiveKitStreamer
from config import TARGET_LANGUAGES, WHISPER_MODEL, SAMPLE_RATE

class LiveTranslator:
    def __init__(self, 
                 use_faster_whisper=True, 
                 use_google_translate=True,
                 whisper_model=WHISPER_MODEL,
                 room_name="live-translator",
                 use_simulation=False):
        """
        初始化实时翻译系统
        
        Args:
            use_faster_whisper: 是否使用Faster-Whisper模型
            use_google_translate: 是否使用Google翻译
            whisper_model: Whisper模型大小
            room_name: LiveKit房间名称
            use_simulation: 是否使用模拟音频输入
        """
        self.room_name = room_name
        self.running = False
        self.text_queue = queue.Queue()  # 识别结果队列
        self.translation_queue = queue.Queue()  # 翻译结果队列
        self.audio_buffer = []  # 音频缓冲
        self.last_text = ""  # 上一次识别的文本
        self.transcribe_thread = None
        self.translate_thread = None
        self.tts_thread = None
        self.audio_input = None
        self.streamer = None
        self.use_faster_whisper = use_faster_whisper
        self.whisper_model_name = whisper_model
        self.whisper_model = None
        self.translator = None
        self.tts_engine = None
        self.use_simulation = use_simulation
        
        # 检测是否在云环境中运行
        if os.environ.get("RENDER") or os.environ.get("HEROKU_APP_ID") or os.environ.get("DYNO"):
            print("检测到云部署环境，将使用模拟音频输入")
            self.use_simulation = True
        
        print("正在初始化实时翻译系统...")
        
        # 初始化Whisper模型
        if use_faster_whisper:
            # 使用Faster-Whisper
            print(f"正在加载Faster-Whisper模型({whisper_model})...")
            try:
                self.whisper_model = WhisperModel(whisper_model, device="cuda" if torch.cuda.is_available() else "cpu")
                print(f"已加载Faster-Whisper模型({whisper_model})，设备: {'GPU' if torch.cuda.is_available() else 'CPU'}")
            except Exception as e:
                print(f"加载Faster-Whisper模型失败: {e}")
                print("回退到标准Whisper模型...")
                self.use_faster_whisper = False
                
        if not self.use_faster_whisper:
            # 使用标准Whisper
            print(f"正在加载标准Whisper模型({whisper_model})...")
            try:
                self.whisper_model = whisper.load_model(whisper_model)
                print(f"已加载标准Whisper模型({whisper_model})，设备: {'GPU' if torch.cuda.is_available() else 'CPU'}")
            except Exception as e:
                print(f"加载标准Whisper模型失败: {e}")
                sys.exit(1)
                
        # 初始化翻译器
        self.translator = Translator()  # 默认使用 DeepL → Microsoft → LibreTranslate 的自动 fallback 顺序
        
        # 初始化TTS引擎
        self.tts_engine = TTSEngine()
        
        # 初始化LiveKit推流器
        self.streamer = LiveKitStreamer(room_name=room_name)
        
        print("实时翻译系统初始化完成")
        
    def _transcribe_thread_func(self):
        """语音识别线程函数"""
        print("语音识别线程已启动")
        
        audio_buffer = []  # 本地音频缓冲
        last_transcription_time = time.time()
        silence_threshold = 0.01  # 静音阈值
        min_audio_length = 1.0  # 最小音频长度（秒）
        max_audio_length = 10.0  # 最大音频长度（秒）
        
        while self.running:
            try:
                # 从音频输入获取数据
                audio_chunk = self.audio_input.get_audio_chunk(timeout=0.1)
                
                if audio_chunk is not None:
                    # 添加到缓冲区
                    audio_buffer.append(audio_chunk)
                    
                    # 计算当前缓冲区长度（秒）
                    buffer_seconds = len(np.concatenate(audio_buffer)) / SAMPLE_RATE
                    
                    # 判断是否需要处理音频
                    current_time = time.time()
                    time_since_last = current_time - last_transcription_time
                    
                    # 检查是否有足够长度的音频 或 是否已经很久没有处理
                    if buffer_seconds >= min_audio_length and (buffer_seconds >= max_audio_length or time_since_last >= 3.0):
                        # 连接所有音频块
                        audio_data = np.concatenate(audio_buffer)
                        
                        # 检查是否是静音（根据均方根值）
                        rms = np.sqrt(np.mean(audio_data.astype(np.float32)**2))
                        
                        if rms > silence_threshold:
                            # 转换为float32并标准化到[-1, 1]
                            if audio_data.dtype == np.int16:
                                audio_data = audio_data.astype(np.float32) / 32768.0
                                
                            # 使用Whisper进行语音识别
                            text = self._transcribe_audio(audio_data)
                            
                            if text and text.strip():
                                print(f"识别结果: {text}")
                                # 将文本放入队列
                                self.text_queue.put(text)
                                
                        # 重置缓冲区和计时器
                        audio_buffer = []
                        last_transcription_time = current_time
                        
            except queue.Empty:
                # 超时，继续
                continue
            except Exception as e:
                print(f"语音识别线程出错: {e}")
                time.sleep(1)
                
    def _transcribe_audio(self, audio_data):
        """
        使用Whisper模型转录音频
        
        Args:
            audio_data: 音频数据（numpy数组，float32，范围[-1, 1]）
            
        Returns:
            识别出的文本
        """
        try:
            if self.use_faster_whisper:
                # 使用Faster-Whisper
                segments, _ = self.whisper_model.transcribe(
                    audio_data, 
                    language="zh",
                    task="transcribe"
                )
                text = " ".join([s.text for s in segments])
            else:
                # 使用标准Whisper
                result = self.whisper_model.transcribe(
                    audio_data, 
                    language="zh",
                    task="transcribe"
                )
                text = result["text"]
                
            return text.strip()
        except Exception as e:
            print(f"转录音频出错: {e}")
            return ""
            
    def _translate_thread_func(self):
        """翻译线程函数"""
        print("翻译线程已启动")
        
        while self.running:
            try:
                # 从文本队列获取识别结果
                text = self.text_queue.get(timeout=1.0)
                
                if text:
                    # 翻译成多种语言
                    translations = self.translator.translate_all(text)
                    
                    # 添加原文（中文）
                    translations["zh"] = text
                    
                    # 将翻译结果放入队列
                    self.translation_queue.put(translations)
                    
            except queue.Empty:
                # 超时，继续
                continue
            except Exception as e:
                print(f"翻译线程出错: {e}")
                time.sleep(1)
                
    async def _process_tts(self):
        """TTS处理函数（异步）"""
        print("TTS处理器已启动")
        
        while self.running:
            try:
                # 从翻译队列获取翻译结果
                translations = self.translation_queue.get(timeout=1.0)
                
                if translations:
                    # 将文本转换为语音
                    audio_data_dict = await self.tts_engine.synthesize_multiple(translations)
                    
                    # 将音频推送到LiveKit
                    self.streamer.push_audio_multiple(audio_data_dict)
                    
            except queue.Empty:
                # 超时，继续
                await asyncio.sleep(0.1)
                continue
            except Exception as e:
                print(f"TTS处理出错: {e}")
                await asyncio.sleep(1)
                
    def _tts_thread_func(self):
        """TTS线程函数（运行异步处理函数）"""
        asyncio.run(self._process_tts())
        
    def start(self):
        """启动实时翻译系统"""
        if self.running:
            print("实时翻译系统已在运行")
            return
            
        self.running = True
        
        # 启动音频输入
        self.audio_input = AudioInput(use_pyaudio=True, use_simulation=self.use_simulation)
        self.audio_input.start()
        
        # 启动LiveKit推流
        self.streamer.start()
        
        # 启动语音识别线程
        self.transcribe_thread = threading.Thread(target=self._transcribe_thread_func, daemon=True)
        self.transcribe_thread.start()
        
        # 启动翻译线程
        self.translate_thread = threading.Thread(target=self._translate_thread_func, daemon=True)
        self.translate_thread.start()
        
        # 启动TTS线程
        self.tts_thread = threading.Thread(target=self._tts_thread_func, daemon=True)
        self.tts_thread.start()
        
        print("实时翻译系统已启动")
        
        # 生成连接URL和二维码
        self._generate_qrcode()
        
    def stop(self):
        """停止实时翻译系统"""
        if not self.running:
            return
            
        self.running = False
        
        # 等待线程结束
        if self.transcribe_thread and self.transcribe_thread.is_alive():
            self.transcribe_thread.join(timeout=2.0)
            
        if self.translate_thread and self.translate_thread.is_alive():
            self.translate_thread.join(timeout=2.0)
            
        if self.tts_thread and self.tts_thread.is_alive():
            self.tts_thread.join(timeout=2.0)
            
        # 停止音频输入
        if self.audio_input:
            self.audio_input.stop()
            
        # 停止LiveKit推流
        if self.streamer:
            self.streamer.stop()
            
        # 清理TTS临时文件
        if self.tts_engine:
            self.tts_engine.cleanup()
            
        print("实时翻译系统已停止")
        
    def _generate_qrcode(self):
        """生成连接二维码"""
        # 获取连接URL
        url = self.streamer.generate_connection_url()
        print(f"连接URL: {url}")
        
        # 生成二维码
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(url)
        qr.make(fit=True)
        
        # 创建图像
        img = qr.make_image(fill_color="black", back_color="white")
        
        # 保存图像
        img.save("translator_qrcode.png")
        print("已生成二维码: translator_qrcode.png")
        
        # 显示连接信息
        connection_info = self.streamer.get_connection_info()
        print("\n=== 连接信息 ===")
        print(f"房间: {connection_info['room']}")
        print(f"服务器: {connection_info['server']}")
        print("支持的语言:")
        for lang_code, lang_info in connection_info['languages'].items():
            print(f"  - {lang_info['name']} ({lang_code}): 频道 {lang_info['channel']}")
        print("=================\n")

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="现场实时语音翻译系统")
    parser.add_argument("--use-faster-whisper", action="store_true", help="使用Faster-Whisper模型")
    parser.add_argument("--use-google-translate", action="store_true", help="使用Google翻译")
    parser.add_argument("--whisper-model", type=str, default=WHISPER_MODEL, help="Whisper模型大小")
    parser.add_argument("--room-name", type=str, default="live-translator", help="LiveKit房间名称")
    parser.add_argument("--use-simulation", action="store_true", help="使用模拟音频输入（无麦克风环境）")
    args = parser.parse_args()
    
    # 创建并启动翻译系统
    translator = LiveTranslator(
        use_faster_whisper=args.use_faster_whisper,
        use_google_translate=args.use_google_translate,
        whisper_model=args.whisper_model,
        room_name=args.room_name,
        use_simulation=args.use_simulation
    )
    
    try:
        translator.start()
        
        print("\n系统已启动，按 Ctrl+C 停止...\n")
        
        # 保持主线程运行
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n接收到停止信号，正在关闭系统...")
        translator.stop()
        print("系统已关闭")
    except Exception as e:
        print(f"系统出错: {e}")
        translator.stop()
        
if __name__ == "__main__":
    main()