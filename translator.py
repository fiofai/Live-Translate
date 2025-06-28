import os
import logging
import asyncio
import json
import requests
from typing import Optional
import uuid

# 导入配置
from config import Config

class TranslationManager:
    """翻译管理器，支持DeepL和Microsoft Translator API"""
    
    def __init__(self):
        self.config = Config()
        self.logger = logging.getLogger("translator")
        
        # 检查API密钥
        self.deepl_available = bool(self.config.deepl_api_key)
        self.microsoft_available = bool(self.config.microsoft_translator_api_key)
        
        # 如果两个API都可用，优先使用DeepL
        self.primary_translator = "deepl" if self.deepl_available else "microsoft"
        
        # Microsoft Translator API配置
        self.ms_translator_endpoint = "https://api.cognitive.microsofttranslator.com"
        self.ms_translator_location = "global"
        
        # 初始化DeepL客户端（如果可用）
        if self.deepl_available:
            try:
                import deepl
                self.deepl_client = deepl.Translator(self.config.deepl_api_key)
                self.logger.info("DeepL翻译器初始化成功")
            except Exception as e:
                self.logger.error(f"DeepL翻译器初始化失败: {str(e)}")
                self.deepl_available = False
                if self.microsoft_available:
                    self.primary_translator = "microsoft"
        
        # 语言代码映射（DeepL和Microsoft使用不同的语言代码）
        self.lang_code_map = {
            # DeepL语言代码
            "deepl": {
                "en": "EN-US",  # 英语（美国）
                "zh": "ZH",     # 中文
                "id": "ID",     # 印尼语
                "ko": "KO",     # 韩语
                "th": "TH",     # 泰语
                # DeepL不支持越南语，将在翻译时回退到Microsoft
            },
            # Microsoft语言代码
            "microsoft": {
                "en": "en",     # 英语
                "zh": "zh-Hans", # 简体中文
                "id": "id",     # 印尼语
                "ko": "ko",     # 韩语
                "th": "th",     # 泰语
                "vi": "vi",     # 越南语
            }
        }
        
        # 检查翻译服务可用性
        if not self.deepl_available and not self.microsoft_available:
            self.logger.warning("警告: 没有可用的翻译服务")
    
    async def translate(self, text: str, source_lang: str, target_lang: str) -> Optional[str]:
        """
        翻译文本
        
        Args:
            text: 要翻译的文本
            source_lang: 源语言代码
            target_lang: 目标语言代码
            
        Returns:
            翻译后的文本，如果翻译失败则返回None
        """
        if not text:
            return None
            
        # 如果源语言和目标语言相同，直接返回原文
        if source_lang == target_lang:
            return text
            
        # 尝试使用主要翻译器
        result = None
        
        # 对于越南语，如果主要翻译器是DeepL（不支持越南语），则直接使用Microsoft
        if target_lang == "vi" and self.primary_translator == "deepl" and self.microsoft_available:
            result = await self._translate_microsoft(text, source_lang, target_lang)
        else:
            # 尝试使用主要翻译器
            if self.primary_translator == "deepl" and self.deepl_available:
                result = await self._translate_deepl(text, source_lang, target_lang)
            elif self.primary_translator == "microsoft" and self.microsoft_available:
                result = await self._translate_microsoft(text, source_lang, target_lang)
                
            # 如果主要翻译器失败，尝试使用备用翻译器
            if result is None:
                if self.primary_translator == "deepl" and self.microsoft_available:
                    self.logger.info(f"DeepL翻译失败，尝试使用Microsoft翻译")
                    result = await self._translate_microsoft(text, source_lang, target_lang)
                elif self.primary_translator == "microsoft" and self.deepl_available:
                    self.logger.info(f"Microsoft翻译失败，尝试使用DeepL翻译")
                    result = await self._translate_deepl(text, source_lang, target_lang)
        
        return result
    
    async def _translate_deepl(self, text: str, source_lang: str, target_lang: str) -> Optional[str]:
        """使用DeepL API翻译文本"""
        if not self.deepl_available:
            return None
            
        # 检查是否支持目标语言
        if target_lang not in self.lang_code_map["deepl"]:
            self.logger.warning(f"DeepL不支持目标语言: {target_lang}")
            return None
            
        try:
            # 转换语言代码
            deepl_source = self.lang_code_map["deepl"].get(source_lang)
            deepl_target = self.lang_code_map["deepl"].get(target_lang)
            
            # 执行翻译（在事件循环中运行阻塞操作）
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, 
                lambda: self.deepl_client.translate_text(
                    text,
                    source_lang=deepl_source,
                    target_lang=deepl_target
                )
            )
            
            return result.text
            
        except Exception as e:
            self.logger.error(f"DeepL翻译出错: {str(e)}")
            return None
    
    async def _translate_microsoft(self, text: str, source_lang: str, target_lang: str) -> Optional[str]:
        """使用Microsoft Translator API翻译文本"""
        if not self.microsoft_available:
            return None
            
        # 检查是否支持目标语言
        if target_lang not in self.lang_code_map["microsoft"]:
            self.logger.warning(f"Microsoft Translator不支持目标语言: {target_lang}")
            return None
            
        try:
            # 转换语言代码
            ms_source = self.lang_code_map["microsoft"].get(source_lang)
            ms_target = self.lang_code_map["microsoft"].get(target_lang)
            
            # 构建请求
            endpoint = f"{self.ms_translator_endpoint}/translate"
            params = {
                'api-version': '3.0',
                'from': ms_source,
                'to': ms_target
            }
            headers = {
                'Ocp-Apim-Subscription-Key': self.config.microsoft_translator_api_key,
                'Ocp-Apim-Subscription-Region': self.ms_translator_location,
                'Content-type': 'application/json',
                'X-ClientTraceId': str(uuid.uuid4())
            }
            body = [{
                'text': text
            }]
            
            # 执行翻译请求
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: requests.post(endpoint, params=params, headers=headers, json=body)
            )
            
            # 解析响应
            if response.status_code == 200:
                result = response.json()
                if result and len(result) > 0:
                    return result[0]["translations"][0]["text"]
            else:
                self.logger.error(f"Microsoft翻译API错误: {response.status_code} {response.text}")
                
            return None
            
        except Exception as e:
            self.logger.error(f"Microsoft翻译出错: {str(e)}")
            return None 