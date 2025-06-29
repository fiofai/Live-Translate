import os
import logging
import asyncio
import uuid
import json
from typing import Dict, Optional, Any
from fastapi import APIRouter, Request, Response, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import aiofiles
import soundfile as sf
import tempfile
from huggingface_hub import HfApi

# 导入配置和其他模块
from config import Config
from voice_clone_module import VoiceCloneManager
from streamer import LiveKitStreamer

# 创建路由器
router = APIRouter()

# 配置日志
logger = logging.getLogger("web_server")

# 全局配置
config = Config()

# 语音克隆管理器
voice_clone_manager = VoiceCloneManager()

# LiveKit流媒体
livekit_streamer = LiveKitStreamer(
    config.livekit_url,
    config.livekit_api_key,
    config.livekit_api_secret
)

# Hugging Face API
hf_api = HfApi(token=config.hf_token)

# 挂载静态文件
def mount_static_files(app):
    """挂载静态文件"""
    # 挂载web目录
    app.mount("/web", StaticFiles(directory="web"), name="web")

# 主页路由
@router.get("/", response_class=HTMLResponse)
async def index():
    """主页，重定向到web/index.html"""
    return RedirectResponse(url="/web/index.html")

# 获取连接信息
@router.get("/connection_info")
async def get_connection_info():
    """获取LiveKit连接信息"""
    try:
        # 初始化LiveKit流媒体（如果尚未初始化）
        if not livekit_streamer.initialized:
            await livekit_streamer.initialize()
        
        # 生成连接信息
        connection_info = livekit_streamer.generate_client_connection_info()
        
        if not connection_info:
            raise HTTPException(status_code=500, detail="生成连接信息失败")
            
        return JSONResponse(content={"info": connection_info})
        
    except Exception as e:
        logger.error(f"获取连接信息时出错: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# 上传语音样本
@router.post("/upload_voice_sample")
async def upload_voice_sample(audio_file: UploadFile = File(...)):
    """上传语音样本到Hugging Face Hub"""
    try:
        # 生成唯一ID
        speaker_id = str(uuid.uuid4())
        
        # 创建临时文件
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
            temp_path = temp_file.name
            
            # 保存上传的文件
            content = await audio_file.read()
            with open(temp_path, "wb") as f:
                f.write(content)
                
        logger.info(f"已保存语音样本到临时文件: {temp_path}")
        
        # 上传到Hugging Face Hub
        try:
            # 确保目录存在
            sample_path = f"voice_samples/{speaker_id}.wav"
            
            # 上传文件
            hf_api.upload_file(
                path_or_fileobj=temp_path,
                path_in_repo=sample_path,
                repo_id=config.hf_repo,
                repo_type="dataset"
            )
            
            logger.info(f"已上传语音样本到Hugging Face Hub: {sample_path}")
            
            # 异步处理语音样本
            asyncio.create_task(voice_clone_manager.process_voice_sample(temp_path, speaker_id))
            
            # 删除临时文件
            os.unlink(temp_path)
            
            return JSONResponse(content={"speaker_id": speaker_id, "status": "processing"})
            
        except Exception as e:
            logger.error(f"上传语音样本到Hugging Face Hub失败: {str(e)}")
            # 删除临时文件
            try:
                os.unlink(temp_path)
            except:
                pass
            raise HTTPException(status_code=500, detail=f"上传到Hugging Face Hub失败: {str(e)}")
        
    except Exception as e:
        logger.error(f"上传语音样本时出错: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# 检查语音克隆状态
@router.get("/clone_status")
async def check_clone_status(speaker_id: str):
    """检查语音克隆状态"""
    try:
        status = await voice_clone_manager.clone_status(speaker_id)
        return JSONResponse(content=status)
        
    except Exception as e:
        logger.error(f"检查语音克隆状态时出错: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# 设置语言的活跃说话人
@router.post("/set_active_speaker")
async def set_active_speaker(lang_code: str = Form(...), speaker_id: str = Form(...)):
    """设置语言的活跃说话人"""
    try:
        # 检查说话人是否存在
        try:
            # 尝试从Hugging Face Hub下载嵌入向量
            embedding_path = await voice_clone_manager._download_voice_embedding(speaker_id)
            if not embedding_path:
                raise HTTPException(status_code=404, detail=f"说话人{speaker_id}不存在")
        except Exception as e:
            logger.error(f"检查说话人时出错: {str(e)}")
            raise HTTPException(status_code=404, detail=f"说话人{speaker_id}不存在")
            
        # 设置活跃说话人
        voice_clone_manager.set_active_speaker(lang_code, speaker_id)
        
        return JSONResponse(content={"status": "success"})
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"设置活跃说话人时出错: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# 获取二维码
@router.get("/qrcode")
async def get_qrcode():
    """获取连接二维码"""
    try:
        # 获取连接信息
        if not livekit_streamer.initialized:
            await livekit_streamer.initialize()
            
        connection_info = livekit_streamer.generate_client_connection_info()
        
        if not connection_info:
            raise HTTPException(status_code=500, detail="生成连接信息失败")
            
        # 生成二维码
        import qrcode
        import io
        
        # 构建URL
        base_url = os.environ.get("BASE_URL", "https://your-app-url.com")
        qr_url = f"{base_url}?info={connection_info}"
        
        # 创建二维码
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(qr_url)
        qr.make(fit=True)
        
        # 创建图像
        img = qr.make_image(fill_color="black", back_color="white")
        
        # 保存到内存
        img_io = io.BytesIO()
        img.save(img_io, format='PNG')
        img_io.seek(0)
        
        return Response(content=img_io.getvalue(), media_type="image/png")
        
    except Exception as e:
        logger.error(f"生成二维码时出错: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# 健康检查
@router.get("/health")
async def health_check():
    """健康检查"""
    return JSONResponse(content={"status": "ok"}) 
