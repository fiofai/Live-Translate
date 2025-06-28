"""
翻译模块，负责将中文文本翻译成多种目标语言
支持Deepl、Microsoft和LibreTranslate翻译，自动切换
"""

import os
import time
import json
import requests
import logging
from typing import Dict, Optional
from config import TARGET_LANGUAGES

# 确保日志目录存在
os.makedirs("logs", exist_ok=True)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("logs/translator.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class Translator:
    def __init__(self, source_lang="zh-CN"):
        """
        初始化翻译器
        
        Args:
            source_lang: 源语言，默认为中文
        """
        self.source_lang = source_lang
        self.target_languages = list(TARGET_LANGUAGES.keys())
        
        # 获取环境变量中的API密钥
        self.deepl_api_key = os.environ.get('DEEPL_API_KEY')
        self.ms_translator_key = os.environ.get('MS_TRANSLATOR_KEY')
        self.ms_region = os.environ.get('MS_REGION', 'eastasia')
        
        # 检查可用的翻译服务
        self.services_available = {
            'deepl': False,
            'microsoft': False,
            'libre': True  # LibreTranslate是公共服务，默认可用
        }
        
        # 测试API可用性
        if self.deepl_api_key:
            self.services_available['deepl'] = self._test_deepl_api()
            if self.services_available['deepl']:
                logger.info("已初始化DeepL翻译（优先）")
            else:
                logger.warning("DeepL API密钥无效或服务不可用")
        else:
            logger.info("未设置DeepL API密钥，将跳过DeepL翻译")
        
        if self.ms_translator_key:
            self.services_available['microsoft'] = self._test_microsoft_api()
            if self.services_available['microsoft']:
                logger.info("已初始化Microsoft翻译（备用）")
            else:
                logger.warning("Microsoft Translator API密钥无效或服务不可用")
        else:
            logger.info("未设置Microsoft Translator API密钥，将跳过Microsoft翻译")
        
        logger.info("已初始化LibreTranslate翻译（最后备用）")
    
    def _test_deepl_api(self) -> bool:
        """
        测试DeepL API是否可用
        
        Returns:
            API是否可用
        """
        try:
            # 简单的测试翻译
            logger.info("正在测试DeepL API连接...")
            result = self._translate_deepl("test", "en")
            if result is not None:
                logger.info("DeepL API连接测试成功")
                return True
            else:
                logger.warning("DeepL API连接测试失败")
                return False
        except Exception as e:
            logger.error(f"测试DeepL API时出错: {e}")
            return False
    
    def _test_microsoft_api(self) -> bool:
        """
        测试Microsoft Translator API是否可用
        
        Returns:
            API是否可用
        """
        try:
            # 简单的测试翻译
            logger.info("正在测试Microsoft Translator API连接...")
            result = self._translate_microsoft("test", "en")
            if result is not None:
                logger.info("Microsoft Translator API连接测试成功")
                return True
            else:
                logger.warning("Microsoft Translator API连接测试失败")
                return False
        except Exception as e:
            logger.error(f"测试Microsoft Translator API时出错: {e}")
            return False
    
    def _translate_deepl(self, text: str, target_lang: str) -> str:
        """
        使用DeepL API翻译文本
        
        Args:
            text: 要翻译的文本
            target_lang: 目标语言代码
            
        Returns:
            翻译后的文本
        """
        if not self.deepl_api_key:
            return None
        
        # DeepL API接口
        url = "https://api-free.deepl.com/v2/translate"
        if not self.deepl_api_key.startswith(":fx"):  # 判断是否为免费API
            url = "https://api.deepl.com/v2/translate"
        
        # 转换语言代码（DeepL使用不同的语言代码格式）
        lang_mapping = {
            "en": "EN",
            "vi": "VI",
            "ms": "MS",
            "th": "TH",
            "ko": "KO",
            "zh": "ZH"
        }
        target = lang_mapping.get(target_lang, target_lang.upper())
        
        # 构建请求
        params = {
            "auth_key": self.deepl_api_key,
            "text": text,
            "source_lang": self.source_lang.split('-')[0].upper(),
            "target_lang": target
        }
        
        try:
            logger.debug(f"正在使用DeepL翻译: [{self.source_lang}→{target_lang}] {text[:30]}...")
            response = requests.post(url, data=params, timeout=5)
            response.raise_for_status()
            result = response.json()
            translation = result["translations"][0]["text"]
            logger.debug(f"DeepL翻译成功: {translation[:30]}...")
            return translation
        except Exception as e:
            logger.warning(f"DeepL翻译失败: {e}")
            return None
    
    def _translate_microsoft(self, text: str, target_lang: str) -> str:
        """
        使用Microsoft Translator API翻译文本
        
        Args:
            text: 要翻译的文本
            target_lang: 目标语言代码
            
        Returns:
            翻译后的文本
        """
        if not self.ms_translator_key:
            return None
        
        # Microsoft Translator API接口
        url = f"https://api.cognitive.microsofttranslator.com/translate?api-version=3.0&to={target_lang}"
        
        # 构建请求头
        headers = {
            'Ocp-Apim-Subscription-Key': self.ms_translator_key,
            'Ocp-Apim-Subscription-Region': self.ms_region,
            'Content-type': 'application/json'
        }
        
        # 构建请求体
        body = [{
            'text': text
        }]
        
        try:
            logger.debug(f"正在使用Microsoft翻译: [{self.source_lang}→{target_lang}] {text[:30]}...")
            response = requests.post(url, headers=headers, json=body, timeout=5)
            response.raise_for_status()
            result = response.json()
            translation = result[0]["translations"][0]["text"]
            logger.debug(f"Microsoft翻译成功: {translation[:30]}...")
            return translation
        except Exception as e:
            logger.warning(f"Microsoft翻译失败: {e}")
            return None
    
    def _translate_libre(self, text: str, target_lang: str) -> str:
        """
        使用LibreTranslate翻译文本
        
        Args:
            text: 要翻译的文本
            target_lang: 目标语言代码
            
        Returns:
            翻译后的文本
        """
        # LibreTranslate API接口
        url = "https://libretranslate.de/translate"
        
        # 构建请求体
        data = {
            "q": text,
            "source": self.source_lang.split('-')[0],
            "target": target_lang,
            "format": "text"
        }
        
        try:
            logger.debug(f"正在使用LibreTranslate翻译: [{self.source_lang}→{target_lang}] {text[:30]}...")
            headers = {"Content-Type": "application/json"}
            response = requests.post(url, json=data, headers=headers, timeout=10)
            response.raise_for_status()
            result = response.json()
            translation = result.get("translatedText")
            logger.debug(f"LibreTranslate翻译成功: {translation[:30]}...")
            return translation
        except Exception as e:
            logger.warning(f"LibreTranslate翻译失败: {e}")
            return None
    
    def translate(self, text: str, target_lang: Optional[str] = None) -> Dict[str, str]:
        """
        将文本翻译成一种或多种目标语言
        
        Args:
            text: 要翻译的文本
            target_lang: 目标语言代码，如果为None，则翻译成所有目标语言
            
        Returns:
            字典，键为语言代码，值为翻译后的文本
        """
        if not text:
            return {}
            
        # 确定要翻译的目标语言
        targets = [target_lang] if target_lang else self.target_languages
        translations = {}
        
        # 为每种目标语言进行翻译
        for lang in targets:
            try:
                translation = None
                service_used = "未知"
                
                # 尝试使用DeepL翻译（优先）
                if self.services_available['deepl'] and self.deepl_api_key:
                    translation = self._translate_deepl(text, lang)
                    if translation:
                        service_used = "DeepL"
                    else:
                        logger.info(f"DeepL翻译失败，尝试使用Microsoft翻译")
                
                # 如果DeepL失败，尝试使用Microsoft翻译
                if translation is None and self.services_available['microsoft'] and self.ms_translator_key:
                    translation = self._translate_microsoft(text, lang)
                    if translation:
                        service_used = "Microsoft"
                    else:
                        logger.info(f"Microsoft翻译失败，尝试使用LibreTranslate翻译")
                
                # 如果Microsoft也失败，使用LibreTranslate作为最后备用
                if translation is None and self.services_available['libre']:
                    translation = self._translate_libre(text, lang)
                    if translation:
                        service_used = "LibreTranslate"
                
                # 如果所有翻译服务都失败，使用原文
                if translation is None:
                    translation = text
                    service_used = "失败-使用原文"
                    logger.warning(f"所有翻译服务都失败，使用原文")
                
                translations[lang] = translation
                logger.info(f"[{self.source_lang}->{lang}] 原文: {text[:30]}... → 翻译: {translation[:30]}... (使用{service_used})")
            except Exception as e:
                logger.error(f"翻译到{lang}时出错: {e}")
                translations[lang] = text  # 失败时使用原文
                
            # 添加小延迟，避免API速率限制
            time.sleep(0.5)
                
        return translations
        
    def translate_all(self, text: str) -> Dict[str, str]:
        """
        将文本翻译成所有配置的目标语言
        
        Args:
            text: 要翻译的文本
            
        Returns:
            字典，键为语言代码，值为翻译后的文本
        """
        return self.translate(text)

# 简单测试代码
if __name__ == "__main__":
    # 测试翻译
    translator = Translator()
    result = translator.translate_all("你好，这是一个测试。我想测试翻译功能是否正常工作。")
    print("翻译结果:")
    for lang, translated in result.items():
        print(f"{TARGET_LANGUAGES[lang]}: {translated}") 