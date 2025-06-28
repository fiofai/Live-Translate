"""
LiveKit推流模块，负责将音频流推送到LiveKit服务
支持按语言推送到不同的频道
"""

import asyncio
import time
import numpy as np
from typing import Dict, Optional, List
import base64
import json
import requests
import jwt
from datetime import datetime, timedelta
import threading
import queue
from config import LIVEKIT_API_KEY, LIVEKIT_API_SECRET, LIVEKIT_URL, TARGET_LANGUAGES, SAMPLE_RATE

class LiveKitStreamer:
    def __init__(self, room_name="live-translator"):
        """
        初始化LiveKit推流模块
        
        Args:
            room_name: LiveKit房间名称
        """
        self.api_key = LIVEKIT_API_KEY
        self.api_secret = LIVEKIT_API_SECRET
        self.livekit_url = LIVEKIT_URL
        self.room_name = room_name
        self.audio_queues = {}  # 每种语言一个音频队列
        self.streaming_threads = {}  # 每种语言一个推流线程
        self.running = False
        self.sample_rate = SAMPLE_RATE
        
        # 初始化每种语言的音频队列
        for lang in TARGET_LANGUAGES.keys():
            self.audio_queues[lang] = queue.Queue()
            
        print(f"已初始化LiveKit推流模块，目标URL: {self.livekit_url}")
        
    def _generate_token(self, identity, room_name=None):
        """
        生成LiveKit访问令牌
        
        Args:
            identity: 用户标识
            room_name: 房间名称
            
        Returns:
            JWT令牌
        """
        if not room_name:
            room_name = self.room_name
            
        # 设置令牌有效期（24小时）
        exp = datetime.utcnow() + timedelta(hours=24)
        
        # 构建声明
        claims = {
            "iss": self.api_key,  # 发行者
            "sub": identity,  # 用户标识
            "exp": int(exp.timestamp()),  # 过期时间
            "nbf": int(datetime.utcnow().timestamp()),  # 生效时间
            "video": {
                "room": room_name,  # 房间名称
                "roomJoin": True,  # 允许加入房间
                "canPublish": True,  # 允许发布流
                "canSubscribe": True,  # 允许订阅流
            }
        }
        
        # 生成JWT令牌
        token = jwt.encode(claims, self.api_secret, algorithm="HS256")
        return token
        
    def _create_or_check_room(self):
        """
        创建LiveKit房间或检查房间是否存在
        
        Returns:
            bool: 是否成功
        """
        # 生成服务令牌
        token = self._generate_token("server-api")
        
        # 检查房间是否存在
        try:
            check_url = f"{self.livekit_url.replace('wss://', 'https://')}/twirp/livekit.RoomService/ListRooms"
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            response = requests.post(check_url, headers=headers, json={})
            rooms = response.json().get("rooms", [])
            
            # 检查我们的房间是否存在
            for room in rooms:
                if room.get("name") == self.room_name:
                    print(f"LiveKit房间已存在: {self.room_name}")
                    return True
                    
            # 房间不存在，创建房间
            create_url = f"{self.livekit_url.replace('wss://', 'https://')}/twirp/livekit.RoomService/CreateRoom"
            response = requests.post(create_url, headers=headers, json={"name": self.room_name})
            
            if response.status_code == 200:
                print(f"已创建LiveKit房间: {self.room_name}")
                return True
            else:
                print(f"创建LiveKit房间失败: {response.text}")
                return False
                
        except Exception as e:
            print(f"LiveKit房间操作失败: {e}")
            return False
            
    def _stream_audio_thread(self, lang):
        """
        为特定语言的音频推流线程
        
        Args:
            lang: 语言代码
        """
        # 语言标识
        identity = f"translator-{lang}"
        
        # 频道名称（使用语言代码作为频道标识）
        channel_name = f"{self.room_name}-{lang}"
        
        # 生成令牌
        token = self._generate_token(identity, channel_name)
        
        print(f"启动{TARGET_LANGUAGES[lang]}推流线程，频道: {channel_name}")
        
        # TODO: 实现WebRTC推流
        # 由于WebRTC推流实现比较复杂，这里使用简化的方式模拟推流
        # 实际项目中，应使用LiveKit的客户端SDK进行真实推流
        
        while self.running:
            try:
                # 从队列获取音频数据（阻塞，超时1秒）
                audio_data = self.audio_queues[lang].get(block=True, timeout=1.0)
                
                if audio_data is not None and len(audio_data) > 0:
                    # 打印音频数据信息（调试用）
                    print(f"推送{TARGET_LANGUAGES[lang]}音频数据，样本数: {len(audio_data)}")
                    
                    # TODO: 将音频数据推送到LiveKit
                    # 这里只是模拟推送，实际项目需要使用WebRTC推送
                    
                    # 模拟处理时间
                    time.sleep(0.1)
            except queue.Empty:
                # 队列为空，继续等待
                continue
            except Exception as e:
                print(f"{TARGET_LANGUAGES[lang]}推流线程出错: {e}")
                time.sleep(1)  # 出错后等待一段时间再继续
    
    def start(self):
        """开始所有语言的推流"""
        if self.running:
            print("推流模块已在运行")
            return
            
        # 检查或创建房间
        if not self._create_or_check_room():
            print("LiveKit房间准备失败，无法启动推流")
            return
            
        self.running = True
        
        # 为每种语言启动推流线程
        for lang in TARGET_LANGUAGES.keys():
            thread = threading.Thread(
                target=self._stream_audio_thread,
                args=(lang,),
                daemon=True
            )
            self.streaming_threads[lang] = thread
            thread.start()
            
        print(f"已启动LiveKit推流，目标语言: {', '.join(TARGET_LANGUAGES.values())}")
    
    def stop(self):
        """停止所有推流"""
        if not self.running:
            return
            
        self.running = False
        
        # 等待所有线程结束
        for lang, thread in self.streaming_threads.items():
            if thread.is_alive():
                thread.join(timeout=2.0)
                
        self.streaming_threads.clear()
        
        # 清空所有队列
        for lang in self.audio_queues:
            while not self.audio_queues[lang].empty():
                try:
                    self.audio_queues[lang].get_nowait()
                except:
                    pass
                    
        print("已停止所有LiveKit推流")
    
    def push_audio(self, lang: str, audio_data: np.ndarray):
        """
        将音频数据推送到指定语言的队列
        
        Args:
            lang: 语言代码
            audio_data: 音频数据（numpy数组）
        """
        if not self.running:
            print("推流模块未启动，无法推送音频")
            return
            
        if lang not in self.audio_queues:
            print(f"未知语言代码: {lang}")
            return
            
        if audio_data is None or len(audio_data) == 0:
            return
            
        # 将音频数据放入队列
        self.audio_queues[lang].put(audio_data)
    
    def push_audio_multiple(self, audio_data_dict: Dict[str, np.ndarray]):
        """
        将多种语言的音频数据同时推送到对应队列
        
        Args:
            audio_data_dict: 字典，键为语言代码，值为音频数据
        """
        for lang, audio_data in audio_data_dict.items():
            self.push_audio(lang, audio_data)
    
    def get_connection_info(self):
        """
        获取客户端连接信息（用于生成QR码和网页客户端）
        
        Returns:
            字典，包含房间名、支持的语言等信息
        """
        languages = {}
        for lang_code, lang_name in TARGET_LANGUAGES.items():
            channel_name = f"{self.room_name}-{lang_code}"
            token = self._generate_token(f"listener-{lang_code}", channel_name)
            languages[lang_code] = {
                "name": lang_name,
                "channel": channel_name,
                "token": token
            }
            
        info = {
            "room": self.room_name,
            "server": self.livekit_url,
            "languages": languages
        }
        
        return info
        
    def generate_connection_url(self):
        """
        生成连接URL（包含所有连接信息的编码URL）
        
        Returns:
            字符串，连接URL
        """
        info = self.get_connection_info()
        
        # 将连接信息编码为JSON，然后Base64编码
        info_json = json.dumps(info)
        info_b64 = base64.b64encode(info_json.encode()).decode()
        
        # 生成URL（网页可以解析这个URL获取连接信息）
        # 注意：实际部署时应替换为真实的Web服务URL
        url = f"http://localhost:8080/?info={info_b64}"
        
        return url

# 简单测试代码
if __name__ == "__main__":
    streamer = LiveKitStreamer(room_name="test-room")
    
    # 启动推流
    streamer.start()
    
    # 模拟音频数据
    test_audio = {
        "en": np.random.randint(-32768, 32767, 16000, dtype=np.int16),
        "vi": np.random.randint(-32768, 32767, 16000, dtype=np.int16),
        "ms": np.random.randint(-32768, 32767, 16000, dtype=np.int16),
        "th": np.random.randint(-32768, 32767, 16000, dtype=np.int16),
        "ko": np.random.randint(-32768, 32767, 16000, dtype=np.int16)
    }
    
    # 推送音频数据
    streamer.push_audio_multiple(test_audio)
    
    # 获取连接信息
    connection_info = streamer.get_connection_info()
    print(f"连接信息: {json.dumps(connection_info, indent=2)}")
    
    # 生成连接URL
    url = streamer.generate_connection_url()
    print(f"连接URL: {url}")
    
    # 等待5秒
    time.sleep(5)
    
    # 停止推流
    streamer.stop() 