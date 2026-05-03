from __future__ import annotations

"""工作流依赖配置管理器。

负责统一初始化工作流执行所需的各类依赖实例，
包括 LLM 客户端、数据库连接、Agent 依赖组件等。
"""

import logging
import os
from typing import Any, Callable, Dict, List, Optional

from src.Tools.BaseLLM import BaseLLMClient
from src.InputProcess.query_expander import QueryExpander
from src.InputProcess.memory_retriever import MemoryRetriever
from src.InputProcess.emotion_analyzer import EmotionAnalyzer
from src.InputProcess.mainline_memory import MainlineMemoryUpdater
from src.InputProcess.memory_compressor import MemoryCompressor
from src.InputProcess.retrieval_strategies import RetrievalStrategy
from src.database.repositories import ConversationRepository, MemoryRepository
from src.prompts.agent_prompts import TASK_JUDGE_PROMPT, TASK_CONTEXT_BUILD_PROMPT
from src.prompts.memory_prompts import MEMORY_COMPRESS_PROMPT
from src.utils.json_utils import parse_json_response
from src.utils.logger import get_logger

logger = get_logger(__name__)

EMOTION_LABELS = "neutral, positive, negative, anxious, angry, confused, sad, happy, excited"
PRONOUNS = ["它", "他", "她", "这个", "那个", "那件事", "这"]
RECALL_KEYWORDS = ["之前", "上次", "说过", "记得", "以前", "还记得"]


def normalize_emotion(emotion_data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """标准化情绪数据。"""
    default = {"label": "neutral", "score": 0.5}
    if not emotion_data:
        return default
    try:
        return {
            "label": emotion_data.get("label", "neutral"),
            "score": min(1.0, max(0.1, float(emotion_data.get("score", 0.5))))
        }
    except (ValueError, TypeError):
        return default


def format_history_text(
    short_history: Optional[List[Dict[str, Any]]] = None,
    long_memories: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """格式化历史记录为文本。"""
    parts = []
    for msg in (short_history or []):
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        parts.append(f"{role}: {content}")
    for mem in (long_memories or []):
        content = mem.get("content", "")
        if content:
            parts.append(f"memory: {content}")
    return "\n".join(parts)


class WorkflowDependencies:
    """工作流依赖容器。

    统一管理并初始化工作流所需的所有依赖组件。
    """

    def __init__(
        self,
        main_llm_client: Optional[BaseLLMClient] = None,
        conversation_repo: Optional[ConversationRepository] = None,
        memory_repo: Optional[MemoryRepository] = None,
    ):
        self.main_llm_client = main_llm_client or self._create_main_llm_client()
        self.conversation_repo = conversation_repo or ConversationRepository()
        self.memory_repo = memory_repo or MemoryRepository()

        self._query_expander: Optional[QueryExpander] = None
        self._memory_retriever: Optional[MemoryRetriever] = None
        self._emotion_analyzer: Optional[EmotionAnalyzer] = None
        self._mainline_memory_updater: Optional[MainlineMemoryUpdater] = None
        self._memory_compressor: Optional[MemoryCompressor] = None

    def _create_main_llm_client(self) -> BaseLLMClient:
        """创建主 LLM 客户端。"""
        return BaseLLMClient()

    def _create_classifier_llm_client(self) -> BaseLLMClient:
        """创建场景分类器专用的 LLM 客户端。"""
        api_key = os.getenv("SmartAgentDeepseekAPI") or os.getenv("DASHSCOPE_API_KEY")
        return BaseLLMClient(
            model="deepseek-v4-flash",
            api_key=api_key,
            base_url="https://api.deepseek.com",
            temperature=0.1,
        )

    @property
    def query_expander(self) -> QueryExpander:
        """延迟初始化 QueryExpander。"""
        if self._query_expander is None:
            self._query_expander = QueryExpander(
                call_llm_json=lambda user_prompt, system_prompt: parse_json_response(
                    self.main_llm_client.chat_with_prompt(prompt=user_prompt, system_message=system_prompt)
                ),
                judge_prompt=TASK_JUDGE_PROMPT,
                expand_prompt=TASK_CONTEXT_BUILD_PROMPT,
                emotion_labels=EMOTION_LABELS,
                pronouns=PRONOUNS,
                recall_keywords=RECALL_KEYWORDS,
                normalize_emotion=normalize_emotion,
                format_history_text=format_history_text,
            )
        return self._query_expander

    @property
    def memory_retriever(self) -> MemoryRetriever:
        """延迟初始化 MemoryRetriever。"""
        if self._memory_retriever is None:
            self._memory_retriever = MemoryRetriever(
                conversation_repo=self.conversation_repo,
                memory_repo=self.memory_repo,
                max_short_history=10,
            )
        return self._memory_retriever

    @property
    def emotion_analyzer(self) -> EmotionAnalyzer:
        """延迟初始化 EmotionAnalyzer。"""
        if self._emotion_analyzer is None:
            from src.prompts.chat_prompts import CHAT_EMOTION_PROMPT

            self._emotion_analyzer = EmotionAnalyzer(
                call_llm_json=lambda user_prompt, system_prompt: parse_json_response(
                    self.main_llm_client.chat_with_prompt(prompt=user_prompt, system_message=system_prompt)
                ),
                emotion_prompt=CHAT_EMOTION_PROMPT,
                emotion_labels=EMOTION_LABELS,
            )
        return self._emotion_analyzer

    @property
    def mainline_memory_updater(self) -> MainlineMemoryUpdater:
        """获取 MainlineMemoryUpdater 实例。"""
        if self._mainline_memory_updater is None:
            self._mainline_memory_updater = MainlineMemoryUpdater()
        return self._mainline_memory_updater

    @property
    def memory_compressor(self) -> MemoryCompressor:
        """延迟初始化 MemoryCompressor。"""
        if self._memory_compressor is None:
            from src.prompts.memory_prompts import MEMORY_COMPRESS_PROMPT

            self._memory_compressor = MemoryCompressor(
                llm_client=self.main_llm_client,
                count_tokens=self.main_llm_client.count_tokens,
                format_history_text=format_history_text,
                compress_prompt=MEMORY_COMPRESS_PROMPT,
                soft_limit=8000,
                hard_limit=18000,
                recent_history_keep=6,
                max_anchor_turns=4,
                max_long_retrieved_after_compress=2,
            )
        return self._memory_compressor
