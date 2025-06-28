"""
音频输入模块，负责从麦克风捕获实时音频
同时支持模拟音频输入，用于在没有麦克风的环境（如云部署）中使用
"""

import queue
import threading
import numpy as np
import time
import os
import random
try:
    import pyaudio
except ImportError:
    print("警告：PyAudio导入失败，将无法使用麦克风输入")
try:
    import sounddevice as sd
except ImportError:
    print("警告：SoundDevice导入失败，将无法使用麦克风输入")
from config import SAMPLE_RATE, CHUNK_SIZE, CHANNELS

class AudioInput:
    def __init__(self, use_pyaudio=True, use_simulation=False, simulation_interval=3.0):
        """
        初始化音频输入模块
        
        Args:
            use_pyaudio: 是否使用PyAudio库，否则使用sounddevice库
            use_simulation: 是否使用模拟音频（用于无麦克风环境，如云部署）
            simulation_interval: 模拟音频输入的间隔时间（秒）
        """
        self.sample_rate = SAMPLE_RATE
        self.chunk_size = CHUNK_SIZE
        self.channels = CHANNELS
        self.audio_queue = queue.Queue()
        self.stopped = True
        self.use_pyaudio = use_pyaudio
        self.use_simulation = use_simulation
        self.simulation_interval = simulation_interval
        self.simulation_thread = None
        self.stream = None
        self.pyaudio_instance = None
        
        # 检测是否在云环境中运行
        if os.environ.get("RENDER") or os.environ.get("HEROKU_APP_ID") or os.environ.get("DYNO"):
            print("检测到云部署环境，将使用模拟音频输入")
            self.use_simulation = True
        
    def callback(self, indata, frames, time, status):
        """sounddevice回调函数"""
        if status:
            print(f"音频输入状态: {status}")
        self.audio_queue.put(indata.copy())
        
    def pyaudio_callback(self, in_data, frame_count, time_info, status):
        """PyAudio回调函数"""
        self.audio_queue.put(np.frombuffer(in_data, dtype=np.int16))
        return (in_data, pyaudio.paContinue)
    
    def _simulation_thread_func(self):
        """模拟音频输入线程函数"""
        print("已启动模拟音频输入")
        
        # 测试文本（将在日志中显示，但不会真正生成声音）
        test_texts = [
            "这是一个测试句子，用于模拟音频输入。",
            "欢迎使用实时翻译系统，这是一条模拟的语音消息。",
            "当前系统运行在云环境中，正在使用模拟音频输入。",
            "如果您看到这条消息，说明系统正在正常工作。",
            "这是一条测试消息，将被翻译成多种语言。",
            "感谢您使用我们的翻译系统，希望它能帮助您打破语言障碍。"
        ]
        
        while not self.stopped:
            try:
                # 生成随机长度的模拟音频数据（白噪声）
                duration = random.uniform(1.5, 4.0)  # 随机持续时间
                num_samples = int(duration * self.sample_rate)
                
                # 创建随机音频数据（白噪声）
                audio_data = np.random.normal(0, 0.1, num_samples).astype(np.float32)
                
                # 将数据放入队列
                self.audio_queue.put(audio_data)
                
                # 打印模拟的文本（仅用于日志）
                text = random.choice(test_texts)
                print(f"[模拟音频] 发送了 {duration:.2f} 秒的音频，理论文本: \"{text}\"")
                
                # 等待一段时间
                time.sleep(self.simulation_interval)
            except Exception as e:
                print(f"模拟音频线程出错: {e}")
                time.sleep(1)
    
    def start(self):
        """开始音频捕获"""
        self.stopped = False
        
        if self.use_simulation:
            # 使用模拟音频输入
            self.simulation_thread = threading.Thread(
                target=self._simulation_thread_func,
                daemon=True
            )
            self.simulation_thread.start()
        elif self.use_pyaudio:
            # 使用PyAudio
            try:
                self.pyaudio_instance = pyaudio.PyAudio()
                self.stream = self.pyaudio_instance.open(
                    format=pyaudio.paInt16,
                    channels=self.channels,
                    rate=self.sample_rate,
                    input=True,
                    frames_per_buffer=self.chunk_size,
                    stream_callback=self.pyaudio_callback
                )
                self.stream.start_stream()
                print("已启动PyAudio麦克风输入")
            except Exception as e:
                print(f"启动PyAudio失败: {e}")
                print("将回退到模拟音频输入")
                self.use_simulation = True
                self.start()  # 重新调用start()使用模拟音频
        else:
            # 使用SoundDevice
            try:
                self.stream = sd.InputStream(
                    samplerate=self.sample_rate,
                    blocksize=self.chunk_size,
                    channels=self.channels,
                    callback=self.callback
                )
                self.stream.start()
                print("已启动SoundDevice麦克风输入")
            except Exception as e:
                print(f"启动SoundDevice失败: {e}")
                print("将回退到模拟音频输入")
                self.use_simulation = True
                self.start()  # 重新调用start()使用模拟音频
            
    def stop(self):
        """停止音频捕获"""
        if self.stopped:
            return
            
        self.stopped = True
        
        if self.use_simulation:
            if self.simulation_thread and self.simulation_thread.is_alive():
                # 不需要特别操作，设置stopped=True后线程会自行结束
                print("已停止模拟音频输入")
        elif self.stream:
            if self.use_pyaudio:
                self.stream.stop_stream()
                self.stream.close()
                self.pyaudio_instance.terminate()
                print("已停止PyAudio麦克风输入")
            else:
                self.stream.stop()
                self.stream.close()
                print("已停止SoundDevice麦克风输入")
                
        self.stream = None
        self.pyaudio_instance = None
        
    def get_audio_chunk(self, block=True, timeout=None):
        """
        从队列获取一个音频块
        
        Args:
            block: 是否阻塞等待
            timeout: 超时时间（秒）
            
        Returns:
            numpy数组形式的音频数据
        """
        try:
            return self.audio_queue.get(block=block, timeout=timeout)
        except queue.Empty:
            return None
            
    def clear_queue(self):
        """清空音频队列"""
        while not self.audio_queue.empty():
            self.audio_queue.get()
            
    def is_running(self):
        """检查音频捕获是否正在运行"""
        return not self.stopped

# 简单测试代码
if __name__ == "__main__":
    import time
    
    # 测试模拟音频输入
    print("测试模拟音频输入...")
    audio_input = AudioInput(use_simulation=True)
    audio_input.start()
    
    print("正在接收模拟音频5秒...")
    for i in range(5):
        chunk = audio_input.get_audio_chunk(timeout=1.0)
        if chunk is not None:
            print(f"接收到音频块，形状: {chunk.shape}")
        time.sleep(1)
    
    audio_input.stop()
    print("模拟音频测试结束")
    
    # 测试真实麦克风（如果可用）
    try:
        print("\n测试真实麦克风...")
        audio_input = AudioInput(use_pyaudio=True, use_simulation=False)
        audio_input.start()
        
        print("正在录音5秒...")
        for i in range(5):
            chunk = audio_input.get_audio_chunk(timeout=1.0)
            if chunk is not None:
                print(f"接收到麦克风音频块，形状: {chunk.shape}")
            time.sleep(1)
        
        audio_input.stop()
        print("麦克风测试结束")
    except Exception as e:
        print(f"麦克风测试失败: {e}") 