#!/usr/bin/env python
"""
部署环境检查脚本，用于验证所有必要的依赖项是否正确安装
"""

import os
import sys
import importlib
import subprocess
import logging
from pathlib import Path

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/dependency_check.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("dependency_checker")

def check_directory_exists(dir_path):
    """检查目录是否存在"""
    exists = os.path.isdir(dir_path)
    logger.info(f"检查目录 {dir_path}: {'存在' if exists else '不存在'}")
    return exists

def check_file_exists(file_path):
    """检查文件是否存在"""
    exists = os.path.isfile(file_path)
    logger.info(f"检查文件 {file_path}: {'存在' if exists else '不存在'}")
    return exists

def check_module_importable(module_name):
    """检查模块是否可导入"""
    try:
        importlib.import_module(module_name)
        logger.info(f"模块 {module_name} 可以成功导入")
        return True
    except ImportError as e:
        logger.error(f"导入模块 {module_name} 失败: {e}")
        return False

def check_ffmpeg_available():
    """检查ffmpeg是否可用"""
    try:
        result = subprocess.run(['ffmpeg', '-version'], 
                               stdout=subprocess.PIPE, 
                               stderr=subprocess.PIPE,
                               text=True)
        if result.returncode == 0:
            logger.info(f"ffmpeg 可用: {result.stdout.splitlines()[0]}")
            return True
        else:
            logger.error(f"ffmpeg 不可用: {result.stderr}")
            return False
    except Exception as e:
        logger.error(f"检查 ffmpeg 时出错: {e}")
        return False

def check_torch_available():
    """检查PyTorch是否可用"""
    try:
        import torch
        logger.info(f"PyTorch 版本: {torch.__version__}")
        logger.info(f"CUDA 可用: {torch.cuda.is_available()}")
        if torch.cuda.is_available():
            logger.info(f"CUDA 版本: {torch.version.cuda}")
            logger.info(f"GPU 数量: {torch.cuda.device_count()}")
            for i in range(torch.cuda.device_count()):
                logger.info(f"GPU {i}: {torch.cuda.get_device_name(i)}")
        return True
    except Exception as e:
        logger.error(f"检查 PyTorch 时出错: {e}")
        return False

def check_rtvc_dependencies():
    """检查Real-Time-Voice-Cloning依赖"""
    # 检查目录
    encoder_dir = check_directory_exists("encoder")
    synthesizer_dir = check_directory_exists("synthesizer")
    vocoder_dir = check_directory_exists("vocoder")
    
    # 检查模型文件
    encoder_model = check_file_exists("encoder/saved_models/pretrained.pt")
    synthesizer_model = check_file_exists("synthesizer/saved_models/pretrained/pretrained.pt")
    vocoder_model = check_file_exists("vocoder/saved_models/pretrained/pretrained.pt")
    
    # 检查模块是否可导入
    encoder_importable = check_module_importable("encoder.inference")
    synthesizer_importable = check_module_importable("synthesizer.inference")
    vocoder_importable = check_module_importable("vocoder.inference")
    
    # 汇总结果
    all_passed = all([
        encoder_dir, synthesizer_dir, vocoder_dir,
        encoder_model, synthesizer_model, vocoder_model,
        encoder_importable, synthesizer_importable, vocoder_importable
    ])
    
    if all_passed:
        logger.info("所有Real-Time-Voice-Cloning依赖检查通过")
    else:
        logger.error("Real-Time-Voice-Cloning依赖检查失败")
    
    return all_passed

def check_voice_clone_module():
    """检查voice_clone_module.py是否可用"""
    try:
        import voice_clone_module
        logger.info("成功导入voice_clone_module")
        
        # 检查模块是否可用
        if hasattr(voice_clone_module, 'module_available'):
            logger.info(f"voice_clone_module.module_available = {voice_clone_module.module_available}")
        else:
            logger.warning("voice_clone_module没有module_available属性")
        
        # 检查关键函数
        functions = [
            'get_processing_status', 
            'process_voice_sample', 
            'synthesize_speech', 
            'get_speaker_embedding'
        ]
        
        for func in functions:
            if hasattr(voice_clone_module, func):
                logger.info(f"voice_clone_module.{func} 存在")
            else:
                logger.error(f"voice_clone_module.{func} 不存在")
        
        return True
    except Exception as e:
        logger.error(f"检查voice_clone_module时出错: {e}")
        return False

def check_compatibility_module():
    """检查兼容性模块voice_clone.py是否可用"""
    try:
        import voice_clone
        logger.info("成功导入兼容性模块voice_clone")
        
        # 检查关键函数
        functions = [
            'get_processing_status', 
            'process_voice_sample', 
            'synthesize_speech', 
            'get_speaker_embedding'
        ]
        
        for func in functions:
            if hasattr(voice_clone, func):
                logger.info(f"voice_clone.{func} 存在")
            else:
                logger.error(f"voice_clone.{func} 不存在")
        
        return True
    except Exception as e:
        logger.error(f"检查兼容性模块voice_clone时出错: {e}")
        return False

def main():
    """主函数"""
    logger.info("=== 开始依赖项检查 ===")
    
    # 确保日志目录存在
    os.makedirs("logs", exist_ok=True)
    
    # 检查Python版本
    logger.info(f"Python版本: {sys.version}")
    
    # 检查当前工作目录
    logger.info(f"当前工作目录: {os.getcwd()}")
    
    # 检查环境变量
    logger.info(f"RENDER环境变量: {'存在' if 'RENDER' in os.environ else '不存在'}")
    
    # 检查ffmpeg
    check_ffmpeg_available()
    
    # 检查PyTorch
    check_torch_available()
    
    # 检查Real-Time-Voice-Cloning依赖
    rtvc_ok = check_rtvc_dependencies()
    
    # 检查voice_clone_module
    vcm_ok = check_voice_clone_module()
    
    # 检查兼容性模块
    compat_ok = check_compatibility_module()
    
    # 汇总结果
    logger.info("=== 依赖项检查结果 ===")
    logger.info(f"Real-Time-Voice-Cloning依赖: {'通过' if rtvc_ok else '失败'}")
    logger.info(f"voice_clone_module模块: {'通过' if vcm_ok else '失败'}")
    logger.info(f"兼容性模块voice_clone: {'通过' if compat_ok else '失败'}")
    
    if rtvc_ok and vcm_ok and compat_ok:
        logger.info("所有依赖项检查通过")
        return 0
    else:
        logger.warning("部分依赖项检查失败，可能会影响应用功能")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 