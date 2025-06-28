import os
import asyncio
import logging
from typing import Dict, List, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydub import AudioSegment
import numpy as np

# 导入自定义模块
from audio_input import AudioInputManager
from translator import TranslationManager
from voice_clone_module import VoiceCloneManager
from tts_engine import TTSEngine
from streamer import LiveKitStreamer
from config import Config

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("main")

# 创建FastAPI应用
app = FastAPI(title="实时语音翻译系统")

# 全局配置
config = Config()

# 初始化各个模块
audio_manager = AudioInputManager()
translation_manager = TranslationManager()
voice_clone_manager = VoiceCloneManager()
tts_engine = TTSEngine()
livekit_streamer = LiveKitStreamer(config.livekit_url, config.livekit_api_key, config.livekit_api_secret)

# 支持的目标语言
TARGET_LANGUAGES = {
    "vi": "Vietnamese",
    "id": "Indonesian",
    "ko": "Korean",
    "th": "Thai",
    "en": "English",
    "zh": "Chinese"  # 原声
}

# 存储活跃的WebSocket连接
active_websockets: Dict[str, List[WebSocket]] = {lang: [] for lang in TARGET_LANGUAGES}

# 存储每种语言的最新翻译结果
latest_translations: Dict[str, str] = {lang: "" for lang in TARGET_LANGUAGES}

@app.on_event("startup")
async def startup_event():
    """应用启动时执行的操作"""
    logger.info("启动实时语音翻译系统...")
    
    # 初始化音频输入
    await audio_manager.initialize()
    
    # 初始化LiveKit流媒体
    await livekit_streamer.initialize()
    
    # 启动主处理循环
    asyncio.create_task(main_processing_loop())

@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时执行的操作"""
    logger.info("关闭实时语音翻译系统...")
    
    # 清理资源
    await audio_manager.cleanup()
    await livekit_streamer.cleanup()

async def main_processing_loop():
    """主处理循环，处理音频流、识别、翻译和合成"""
    logger.info("启动主处理循环...")
    
    while True:
        try:
            # 获取音频数据
            audio_data = await audio_manager.get_audio_chunk()
            if audio_data is None:
                await asyncio.sleep(0.01)
                continue
                
            # 语音识别 (中文)
            text_zh = await audio_manager.transcribe_audio(audio_data)
            if not text_zh:
                continue
                
            logger.info(f"识别到中文: {text_zh}")
            
            # 广播原始中文音频到中文频道
            await livekit_streamer.publish_audio(audio_data, "zh")
            
            # 更新中文文本
            latest_translations["zh"] = text_zh
            
            # 广播中文文本到WebSocket客户端
            await broadcast_to_websockets("zh", text_zh)
            
            # 对每种目标语言进行翻译和语音合成
            tasks = []
            for lang_code in TARGET_LANGUAGES:
                if lang_code != "zh":  # 跳过中文
                    tasks.append(process_language(text_zh, lang_code))
                    
            # 等待所有语言处理完成
            await asyncio.gather(*tasks)
            
        except Exception as e:
            logger.error(f"处理循环出错: {str(e)}")
            await asyncio.sleep(1)  # 出错后暂停一下

async def process_language(text_zh: str, lang_code: str):
    """处理单个语言的翻译和语音合成"""
    try:
        # 翻译文本
        translated_text = await translation_manager.translate(text_zh, "zh", lang_code)
        if not translated_text:
            logger.warning(f"翻译到{lang_code}失败")
            return
            
        logger.info(f"翻译到{lang_code}: {translated_text}")
        
        # 更新该语言的最新翻译
        latest_translations[lang_code] = translated_text
        
        # 广播翻译文本到WebSocket客户端
        await broadcast_to_websockets(lang_code, translated_text)
        
        # 尝试使用语音克隆合成语音
        audio_data = None
        try:
            speaker_id = voice_clone_manager.get_active_speaker_id(lang_code)
            if speaker_id:
                audio_data = await voice_clone_manager.synthesize(translated_text, speaker_id)
        except Exception as e:
            logger.error(f"语音克隆失败: {str(e)}")
        
        # 如果语音克隆失败，使用普通TTS引擎
        if audio_data is None:
            audio_data = await tts_engine.synthesize(translated_text, lang_code)
            
        # 广播合成的音频到LiveKit
        if audio_data is not None:
            await livekit_streamer.publish_audio(audio_data, lang_code)
        
    except Exception as e:
        logger.error(f"处理{lang_code}语言时出错: {str(e)}")

@app.websocket("/ws/{lang_code}")
async def websocket_endpoint(websocket: WebSocket, lang_code: str):
    """WebSocket端点，用于实时更新翻译文本"""
    if lang_code not in TARGET_LANGUAGES:
        await websocket.close(code=1000, reason=f"不支持的语言: {lang_code}")
        return
        
    await websocket.accept()
    active_websockets[lang_code].append(websocket)
    
    try:
        # 发送最新的翻译结果
        if latest_translations[lang_code]:
            await websocket.send_text(latest_translations[lang_code])
            
        # 保持连接直到客户端断开
        while True:
            data = await websocket.receive_text()
            # 这里我们只是保持连接，不处理接收到的数据
            await asyncio.sleep(1)
            
    except WebSocketDisconnect:
        active_websockets[lang_code].remove(websocket)
    except Exception as e:
        logger.error(f"WebSocket错误: {str(e)}")
        if websocket in active_websockets[lang_code]:
            active_websockets[lang_code].remove(websocket)

async def broadcast_to_websockets(lang_code: str, message: str):
    """向特定语言的所有WebSocket连接广播消息"""
    if lang_code not in active_websockets:
        return
        
    # 创建要删除的连接列表
    to_remove = []
    
    # 向所有活跃的连接发送消息
    for websocket in active_websockets[lang_code]:
        try:
            await websocket.send_text(message)
        except Exception:
            to_remove.append(websocket)
            
    # 删除失败的连接
    for websocket in to_remove:
        if websocket in active_websockets[lang_code]:
            active_websockets[lang_code].remove(websocket)

# 导入web_server模块中的路由
from web_server import router as web_router

# 注册Web路由
app.include_router(web_router)

# 主入口点
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True) 