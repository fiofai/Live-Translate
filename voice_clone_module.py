import os
import sys
import logging
import asyncio
import numpy as np
import torch
import tempfile
import soundfile as sf
import json
import time
from typing import Dict, Optional, List, Any
from pathlib import Path
import shutil
from huggingface_hub import hf_hub_download
import io

# 导入配置
from config import Config

class VoiceCloneManager:
    """语音克隆管理器，封装Real-Time-Voice-Cloning的调用"""
    
    def __init__(self):
        self.config = Config()
        self.logger = logging.getLogger("voice_clone")
        
        # 临时目录
        self.temp_dir = self.config.temp_dir
        
        # 活跃的说话人ID（每种语言一个）
        self.active_speakers: Dict[str, str] = {}
        
        # 加载状态
        self.models_loaded = False
        self.loading_in_progress = False
        
        # 加载锁
        self.load_lock = asyncio.Lock()
        
        # 初始化模型
        asyncio.create_task(self._initialize_models())
        
        # 加载说话人映射
        self._load_speaker_mapping()
    
    async def _initialize_models(self):
        """初始化语音克隆模型"""
        if self.models_loaded or self.loading_in_progress:
            return
            
        async with self.load_lock:
            if self.models_loaded:
                return
                
            self.loading_in_progress = True
            
            try:
                self.logger.info("开始从Hugging Face Hub加载语音克隆模型...")
                
                # 确保Real-Time-Voice-Cloning目录在Python路径中
                rtvc_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                if rtvc_dir not in sys.path:
                    sys.path.append(rtvc_dir)
                
                # 下载模型文件
                model_paths = {}
                for model_type, model_file in self.config.model_files.items():
                    try:
                        self.logger.debug(f"正在下载{model_type}模型文件: {model_file}")
                        local_path = self._download_model(model_type)
                        if not local_path:
                            raise FileNotFoundError(f"无法下载模型文件: {model_file}")
                        model_paths[model_type] = local_path
                        self.logger.info(f"成功下载{model_type}模型文件到: {local_path}")
                    except Exception as e:
                        self.logger.error(f"下载{model_type}模型文件失败: {str(e)}")
                        raise
                
                # 导入Real-Time-Voice-Cloning模块
                try:
                    from encoder import inference as encoder
                    from synthesizer import inference as synthesizer
                    from vocoder import inference as vocoder
                    
                    self.encoder = encoder
                    self.synthesizer = synthesizer
                    self.vocoder = vocoder
                    
                    # 检查CUDA可用性
                    self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
                    self.logger.info(f"使用设备: {self.device}")
                    
                    # 加载编码器模型
                    self.logger.info(f"加载编码器模型: {model_paths['encoder']}")
                    self.encoder.load_model(model_paths["encoder"], device=self.device)
                    
                    # 加载合成器模型
                    self.logger.info(f"加载合成器模型: {model_paths['synthesizer']}")
                    self.synthesizer.load_model(model_paths["synthesizer"], device=self.device)
                    
                    # 加载声码器模型
                    self.logger.info(f"加载声码器模型: {model_paths['vocoder']}")
                    self.vocoder.load_model(model_paths["vocoder"], device=self.device)
                    
                    self.models_loaded = True
                    self.logger.info("语音克隆模型加载成功")
                    
                except Exception as e:
                    self.logger.error(f"加载语音克隆模型失败: {str(e)}")
                    raise
                    
            except Exception as e:
                self.logger.error(f"初始化语音克隆模型失败: {str(e)}")
            finally:
                self.loading_in_progress = False
    
    def _download_model(self, model_type: str) -> Optional[str]:
        """从Hugging Face Hub下载模型文件"""
        try:
            model_path = self.config.get_hf_model_path(model_type)
            if not model_path:
                self.logger.error(f"无效的模型类型: {model_type}")
                return None
                
            # 下载模型文件
            local_path = hf_hub_download(
                repo_id=self.config.hf_repo,
                filename=self.config.model_files[model_type],
                token=self.config.hf_token,
                cache_dir=self.temp_dir
            )
            
            return local_path
            
        except Exception as e:
            self.logger.error(f"下载模型文件失败: {str(e)}")
            return None
    
    def _load_speaker_mapping(self):
        """加载说话人映射"""
        try:
            # 尝试从Hugging Face Hub下载说话人映射
            mapping_path = hf_hub_download(
                repo_id=self.config.hf_repo,
                filename="speaker_mapping.json",
                token=self.config.hf_token,
                cache_dir=self.temp_dir
            )
            
            with open(mapping_path, "r") as f:
                self.active_speakers = json.load(f)
                
            self.logger.info(f"已从Hugging Face Hub加载说话人映射: {self.active_speakers}")
            
        except Exception as e:
            self.logger.warning(f"从Hugging Face Hub加载说话人映射失败: {str(e)}")
            self.active_speakers = {}
    
    def _save_speaker_mapping(self):
        """保存说话人映射到Hugging Face Hub"""
        try:
            # 创建临时文件
            mapping_path = os.path.join(self.temp_dir, "speaker_mapping.json")
            with open(mapping_path, "w") as f:
                json.dump(self.active_speakers, f)
                
            # TODO: 将文件上传到Hugging Face Hub
            # 这需要使用Hugging Face Hub API进行文件上传
            # 由于这超出了当前任务范围，我们暂时只保存到本地
            self.logger.info(f"已保存说话人映射到本地: {mapping_path}")
            
        except Exception as e:
            self.logger.error(f"保存说话人映射失败: {str(e)}")
    
    def get_active_speaker_id(self, lang_code: str) -> Optional[str]:
        """获取指定语言的活跃说话人ID"""
        return self.active_speakers.get(lang_code)
    
    def set_active_speaker(self, lang_code: str, speaker_id: str):
        """设置指定语言的活跃说话人"""
        self.active_speakers[lang_code] = speaker_id
        self._save_speaker_mapping()
        self.logger.info(f"已设置{lang_code}语言的活跃说话人为: {speaker_id}")
    
    async def _download_voice_sample(self, speaker_id: str) -> Optional[str]:
        """从Hugging Face Hub下载语音样本"""
        try:
            # 下载语音样本
            sample_path = hf_hub_download(
                repo_id=self.config.hf_repo,
                filename=f"voice_samples/{speaker_id}.wav",
                token=self.config.hf_token,
                cache_dir=self.temp_dir
            )
            
            self.logger.info(f"成功从Hugging Face Hub下载语音样本: {speaker_id}")
            return sample_path
            
        except Exception as e:
            self.logger.error(f"下载语音样本失败: {str(e)}")
            return None
    
    async def _download_voice_embedding(self, speaker_id: str) -> Optional[str]:
        """从Hugging Face Hub下载语音嵌入向量"""
        try:
            # 下载语音嵌入向量
            embedding_path = hf_hub_download(
                repo_id=self.config.hf_repo,
                filename=f"voice_embeddings/{speaker_id}.npy",
                token=self.config.hf_token,
                cache_dir=self.temp_dir
            )
            
            self.logger.info(f"成功从Hugging Face Hub下载语音嵌入向量: {speaker_id}")
            return embedding_path
            
        except Exception as e:
            self.logger.error(f"下载语音嵌入向量失败: {str(e)}")
            return None
    
    async def process_voice_sample(self, sample_path: str, speaker_id: str) -> bool:
        """
        处理语音样本，提取说话人嵌入向量
        
        Args:
            sample_path: 语音样本路径
            speaker_id: 说话人ID
            
        Returns:
            是否处理成功
        """
        if not os.path.exists(sample_path):
            self.logger.error(f"语音样本不存在: {sample_path}")
            return False
            
        # 确保模型已加载
        if not self.models_loaded:
            await self._initialize_models()
            if not self.models_loaded:
                self.logger.error("语音克隆模型未加载，无法处理语音样本")
                return False
        
        try:
            # 加载音频
            wav, sample_rate = self.encoder.preprocess_wav(sample_path)
            
            # 提取嵌入向量
            embedding = self.encoder.embed_utterance(wav)
            
            # 保存嵌入向量到临时文件
            embedding_path = os.path.join(self.temp_dir, f"{speaker_id}.npy")
            np.save(embedding_path, embedding)
            
            self.logger.info(f"已保存说话人嵌入向量: {embedding_path}")
            
            # TODO: 将嵌入向量上传到Hugging Face Hub
            # 这需要使用Hugging Face Hub API进行文件上传
            # 由于这超出了当前任务范围，我们暂时只保存到本地
            
            return True
            
        except Exception as e:
            self.logger.error(f"处理语音样本失败: {str(e)}")
            return False
    
    async def synthesize(self, text: str, speaker_id: str) -> Optional[np.ndarray]:
        """
        合成语音
        
        Args:
            text: 要合成的文本
            speaker_id: 说话人ID
            
        Returns:
            合成的音频数据，如果合成失败则返回None
        """
        if not text:
            return None
            
        # 尝试从Hugging Face Hub下载嵌入向量
        embedding_path = await self._download_voice_embedding(speaker_id)
        if not embedding_path:
            self.logger.error(f"无法找到说话人嵌入向量: {speaker_id}")
            return None
            
        # 确保模型已加载
        if not self.models_loaded:
            await self._initialize_models()
            if not self.models_loaded:
                self.logger.error("语音克隆模型未加载，无法合成语音")
                return None
        
        try:
            # 加载嵌入向量
            embedding = np.load(embedding_path)
            
            # 在事件循环中运行阻塞操作
            loop = asyncio.get_event_loop()
            
            # 合成语音
            result = await loop.run_in_executor(
                None,
                lambda: self._synthesize_speech(text, embedding)
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"合成语音失败: {str(e)}")
            return None
    
    def _synthesize_speech(self, text: str, embedding: np.ndarray) -> Optional[np.ndarray]:
        """
        合成语音（阻塞操作）
        
        Args:
            text: 要合成的文本
            embedding: 说话人嵌入向量
            
        Returns:
            合成的音频数据，如果合成失败则返回None
        """
        try:
            # 合成器输入
            texts = [text]
            embeds = [embedding]
            
            # 合成梅尔频谱图
            specs = self.synthesizer.synthesize_spectrograms(texts, embeds)
            spec = specs[0]
            
            # 使用声码器生成波形
            wav = self.vocoder.infer_waveform(spec)
            
            # 后处理
            wav = np.pad(wav, (0, self.synthesizer.sample_rate), mode="constant")
            wav = wav / np.abs(wav).max() * 0.97
            
            return wav
            
        except Exception as e:
            self.logger.error(f"合成语音失败: {str(e)}")
            return None
    
    async def clone_status(self, speaker_id: str) -> Dict[str, Any]:
        """
        获取语音克隆状态
        
        Args:
            speaker_id: 说话人ID
            
        Returns:
            状态信息
        """
        try:
            # 检查嵌入向量是否存在
            embedding_path = await self._download_voice_embedding(speaker_id)
            if embedding_path:
                return {
                    "status": "ready",
                    "message": "语音克隆已准备就绪"
                }
            
            # 检查语音样本是否存在
            sample_path = await self._download_voice_sample(speaker_id)
            if sample_path:
                if self.loading_in_progress:
                    return {
                        "status": "pending",
                        "message": "正在处理语音样本"
                    }
                else:
                    # 尝试处理语音样本
                    success = await self.process_voice_sample(sample_path, speaker_id)
                    if success:
                        return {
                            "status": "ready",
                            "message": "语音克隆已准备就绪"
                        }
                    else:
                        return {
                            "status": "failed",
                            "message": "处理语音样本失败"
                        }
            
            return {
                "status": "not_found",
                "message": "未找到语音样本或嵌入向量"
            }
            
        except Exception as e:
            self.logger.error(f"检查语音克隆状态失败: {str(e)}")
            return {
                "status": "error",
                "message": f"检查状态出错: {str(e)}"
            } 
