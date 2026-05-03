from __future__ import annotations

"""场景分类器 - 根据用户输入自动选择记忆检索策略。"""

import logging
import os
from typing import Optional

from src.Tools.BaseLLM import BaseLLMClient
from src.InputProcess.retrieval_strategies import (
    RetrievalStrategy,
    STANDARD_STRATEGY,
    TASK_STRATEGY,
    EMOTION_STRATEGY,
    KNOWLEDGE_STRATEGY,
)
from src.utils.json_utils import extract_json_from_text

logger = logging.getLogger(__name__)

CLASSIFIER_SYSTEM_PROMPT = """你是一个场景分类器。根据用户输入，判断应该使用哪种记忆检索策略。

可用的策略及适用场景：
- standard: 标准对话场景。适用于日常问候、简单闲聊、确认信息等无需检索外部信息即可完成的标准对话。
- task: 任务规划与信息查询场景。适用于需要搜索外部信息、查询实时数据（天气/交通/景点等）、制定计划、推荐建议（周末去哪玩/吃什么/看什么）等需要工具辅助完成的任务。
- emotion: 情感陪伴场景。适用于用户表达情绪、寻求安慰、倾诉烦恼、分享喜悦等需要共情回应的场景。
- knowledge: 知识问答场景。适用于询问概念、原理、定义、解释、学术问题等需要知识性回答的场景。

判断规则：
1. 如果用户询问需要"搜索/查询/推荐/规划"等外部信息，选择 task
2. 如果用户只是简单问候或闲聊，选择 standard
3. 如果用户表达情绪（正面或负面），选择 emotion
4. 如果用户询问知识性问题（是什么/为什么/怎么做），选择 knowledge

输出 JSON 格式：
{"strategy": "standard|task|emotion|knowledge", "reason": "判断原因（简短说明）"}"""

STRATEGY_MAP = {
    "standard": STANDARD_STRATEGY,
    "task": TASK_STRATEGY,
    "emotion": EMOTION_STRATEGY,
    "knowledge": KNOWLEDGE_STRATEGY,
}


class SceneClassifier:
    """根据用户输入判断场景类型并返回对应的检索策略。
    
    职责：
    1. 接收用户输入
    2. 调用 LLM 分类器判断场景类型
    3. 根据判断结果返回对应的检索策略
    """

    def __init__(self, llm_client: Optional[BaseLLMClient] = None):
        if llm_client is not None:
            self.llm_client = llm_client
        else:
            self.llm_client = self._create_default_client()

    def _create_default_client(self) -> BaseLLMClient:
        """创建默认的 DeepSeek LLM 客户端。"""
        api_key = os.getenv("SmartAgentDeepseekAPI")
        if not api_key:
            logger.warning("环境变量 SmartAgentDeepseekAPI 未设置，将使用默认 LLM")
            api_key = os.getenv("DASHSCOPE_API_KEY")

        return BaseLLMClient(
            system_prompt=CLASSIFIER_SYSTEM_PROMPT,
            model="deepseek-v4-flash",
            api_key=api_key,
            base_url="https://api.deepseek.com",
            temperature=0.1,
            timeout=10,
        )

    def classify(self, user_input: str) -> RetrievalStrategy:
        """根据用户输入分类并返回对应的检索策略。

        Args:
            user_input: 用户的输入文本。

        Returns:
            对应的 RetrievalStrategy，失败时返回默认的 STANDARD_STRATEGY。
        """
        try:
            response = self.llm_client.chat_with_prompt(
                prompt=user_input,
                system_message=CLASSIFIER_SYSTEM_PROMPT,
            )

            if not response:
                logger.warning("LLM 返回空响应，使用默认策略")
                return STANDARD_STRATEGY

            result = extract_json_from_text(response)
            if result is None:
                logger.warning("JSON 解析失败，使用默认策略。原始响应: %s", response)
                return STANDARD_STRATEGY

            strategy_name = result.get("strategy", "").lower()
            strategy = STRATEGY_MAP.get(strategy_name)

            if strategy is None:
                logger.warning("未知策略: %s，使用默认策略", strategy_name)
                return STANDARD_STRATEGY

            logger.info(
                "场景分类完成: strategy=%s, reason=%s",
                strategy_name,
                result.get("reason", ""),
            )
            return strategy

        except Exception as e:
            logger.warning("场景分类失败，使用默认策略: %s", e)
            return STANDARD_STRATEGY
