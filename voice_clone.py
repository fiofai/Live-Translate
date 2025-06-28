"""
兼容性模块，用于重定向导入到子模块中的voice_clone_module
这样即使有代码尝试从voice_clone导入，也能正确重定向
"""

import logging
logger = logging.getLogger(__name__)

try:
    from clone_modules.voice_cloning.voice_clone_module import *
    logger.info("成功从clone_modules.voice_cloning.voice_clone_module导入所有函数")
except Exception as e:
    logger.error(f"从clone_modules.voice_cloning.voice_clone_module导入时出错: {e}")
    
    # 提供基本的兼容性函数，避免导入错误导致整个应用崩溃
    def get_processing_status(user_id):
        logger.warning(f"使用兼容性模块中的get_processing_status函数，用户ID: {user_id}")
        return {"status": "error", "message": "语音克隆模块未正确加载"}
    
    def process_voice_sample(audio_path, user_id):
        logger.warning(f"使用兼容性模块中的process_voice_sample函数，音频: {audio_path}, 用户ID: {user_id}")
        return False
    
    def synthesize_speech(text, speaker_embedding):
        logger.warning(f"使用兼容性模块中的synthesize_speech函数，文本: {text}")
        return None
    
    def get_speaker_embedding(user_id):
        logger.warning(f"使用兼容性模块中的get_speaker_embedding函数，用户ID: {user_id}")
        return None 