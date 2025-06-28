import os
import logging
import asyncio
import time
import numpy as np
from typing import Dict, Optional, Any
import json
import base64
from livekit import rtc, api
import soundfile as sf
import tempfile

class LiveKitStreamer:
    """LiveKit流媒体模块，用于推送音频流到LiveKit服务"""
    
    def __init__(self, livekit_url: str, api_key: str, api_secret: str):
        self.logger = logging.getLogger("livekit_streamer")
        
        # LiveKit配置
        self.livekit_url = livekit_url
        self.api_key = api_key
        self.api_secret = api_secret
        
        # 房间和参与者信息
        self.rooms: Dict[str, rtc.Room] = {}
        self.publishers: Dict[str, rtc.LocalParticipant] = {}
        
        # 音频参数
        self.sample_rate = 16000
        
        # 初始化标志
        self.initialized = False
    
    async def initialize(self):
        """初始化LiveKit流媒体"""
        if self.initialized:
            return
            
        try:
            # 检查LiveKit配置
            if not self.livekit_url or not self.api_key or not self.api_secret:
                self.logger.error("LiveKit配置不完整，无法初始化")
                return
                
            # 创建LiveKit客户端
            self.livekit_client = api.LiveKitAPI(
                url=self.livekit_url,
                api_key=self.api_key,
                api_secret=self.api_secret
            )
            
            # 初始化RTC
            rtc.init_logging()
            
            self.initialized = True
            self.logger.info("LiveKit流媒体初始化成功")
            
        except Exception as e:
            self.logger.error(f"LiveKit流媒体初始化失败: {str(e)}")
            raise
    
    async def cleanup(self):
        """清理资源"""
        # 断开所有房间连接
        for lang_code, room in self.rooms.items():
            try:
                await room.disconnect()
                self.logger.info(f"已断开与{lang_code}房间的连接")
            except Exception as e:
                self.logger.error(f"断开{lang_code}房间连接时出错: {str(e)}")
        
        self.rooms = {}
        self.publishers = {}
        self.logger.info("LiveKit流媒体已清理")
    
    async def _ensure_room_exists(self, lang_code: str) -> bool:
        """确保房间存在"""
        try:
            # 房间名格式：translate_<lang_code>
            room_name = f"translate_{lang_code}"
            
            # 检查房间是否存在
            try:
                await self.livekit_client.get_room(room_name)
            except Exception:
                # 如果房间不存在，创建房间
                await self.livekit_client.create_room(
                    name=room_name,
                    empty_timeout=30,  # 30秒无人自动关闭
                    max_participants=100
                )
                self.logger.info(f"已创建房间: {room_name}")
                
            return True
            
        except Exception as e:
            self.logger.error(f"确保房间存在时出错: {str(e)}")
            return False
    
    async def _ensure_connected(self, lang_code: str) -> bool:
        """确保已连接到指定语言的房间"""
        if lang_code in self.rooms and self.rooms[lang_code].connection_state == rtc.ConnectionState.CONNECTED:
            return True
            
        try:
            # 确保房间存在
            if not await self._ensure_room_exists(lang_code):
                return False
                
            # 房间名
            room_name = f"translate_{lang_code}"
            
            # 创建发布者令牌
            publisher_identity = f"translator_{lang_code}"
            token = await self.livekit_client.create_token(
                room_name=room_name,
                identity=publisher_identity,
                ttl=3600,  # 1小时
                can_publish=True,
                can_subscribe=False
            )
            
            # 创建房间
            room = rtc.Room()
            
            # 连接到房间
            await room.connect(self.livekit_url, token)
            self.logger.info(f"已连接到房间: {room_name}")
            
            # 保存房间和参与者
            self.rooms[lang_code] = room
            self.publishers[lang_code] = room.local_participant
            
            return True
            
        except Exception as e:
            self.logger.error(f"连接到{lang_code}房间时出错: {str(e)}")
            return False
    
    async def publish_audio(self, audio_data: np.ndarray, lang_code: str) -> bool:
        """
        发布音频到指定语言的房间
        
        Args:
            audio_data: 音频数据
            lang_code: 语言代码
            
        Returns:
            是否发布成功
        """
        if not self.initialized or audio_data is None:
            return False
            
        try:
            # 确保已连接
            if not await self._ensure_connected(lang_code):
                return False
                
            # 获取本地参与者
            publisher = self.publishers[lang_code]
            
            # 创建临时WAV文件
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                temp_path = temp_file.name
                
            # 写入音频数据
            sf.write(temp_path, audio_data, self.sample_rate)
            
            # 创建音频源
            source = rtc.AudioFileSource(temp_path)
            
            # 创建音频轨道
            track = await publisher.publish_audio(source)
            
            # 等待音频播放完成
            await asyncio.sleep(len(audio_data) / self.sample_rate)
            
            # 停止轨道
            await track.stop()
            
            # 删除临时文件
            try:
                os.unlink(temp_path)
            except:
                pass
                
            return True
            
        except Exception as e:
            self.logger.error(f"发布音频到{lang_code}房间时出错: {str(e)}")
            return False
    
    def generate_client_connection_info(self) -> str:
        """
        生成客户端连接信息
        
        Returns:
            Base64编码的连接信息JSON字符串
        """
        if not self.initialized:
            self.logger.error("LiveKit流媒体未初始化，无法生成连接信息")
            return ""
            
        try:
            # 支持的语言
            languages = {
                "zh": {"name": "中文（原声）"},
                "en": {"name": "English"},
                "vi": {"name": "Tiếng Việt"},
                "id": {"name": "Bahasa Indonesia"},
                "ko": {"name": "한국어"},
                "th": {"name": "ภาษาไทย"}
            }
            
            # 为每种语言创建令牌
            for lang_code in languages:
                room_name = f"translate_{lang_code}"
                
                # 创建订阅者令牌
                subscriber_identity = f"listener_{int(time.time())}_{lang_code}"
                token = asyncio.run(self.livekit_client.create_token(
                    room_name=room_name,
                    identity=subscriber_identity,
                    ttl=3600,  # 1小时
                    can_publish=False,
                    can_subscribe=True
                ))
                
                # 保存令牌
                languages[lang_code]["token"] = token
            
            # 创建连接信息
            connection_info = {
                "server": self.livekit_url,
                "languages": languages
            }
            
            # Base64编码
            json_str = json.dumps(connection_info)
            encoded = base64.b64encode(json_str.encode()).decode()
            
            return encoded
            
        except Exception as e:
            self.logger.error(f"生成客户端连接信息时出错: {str(e)}")
            return "" 