from __future__ import annotations

"""输入处理相关 Agent。"""

from typing import Any, Dict, List, Optional

from ..core.context import Context
from ..InputProcess.emotion_analyzer import EmotionAnalyzer
from ..InputProcess.mainline_memory import MainlineMemoryUpdater
from ..InputProcess.memory_compressor import MemoryCompressor
from ..InputProcess.memory_retriever import MemoryRetriever
from ..InputProcess.query_expander import QueryExpander
from ..InputProcess.retrieval_strategies import RetrievalStrategy
from .base import BaseAgent


class ContextBuildAgent(BaseAgent):
    """负责召回判断、记忆召回和 query 扩写。
    
    职责：
    1. 从 ``Context`` 中提取用户输入
    2. 调用 ``QueryExpander`` 判断是否需要召回和扩展
    3. 如果需要召回，调用 ``MemoryRetriever`` 从短期记忆中获取
    4. 如果需要扩展，调用 ``QueryExpander`` 扩展 query
    """

    name = "context_build_agent"
    uses_llm = True

    def __init__(
        self,
        query_expander: QueryExpander,
        memory_retriever: MemoryRetriever,
        retrieval_strategy: Optional[RetrievalStrategy] = None,
    ):
        self.query_expander = query_expander
        self.memory_retriever = memory_retriever
        self.retrieval_strategy = retrieval_strategy or RetrievalStrategy()

    def run(self, context: Context) -> Context:
        query = context.raw_input or context.user_input
        context.raw_input = query

        need_recall, need_expansion = self.query_expander.unified_judge(query)
        context.memory["need_recall"] = need_recall
        context.memory["need_expansion"] = need_expansion and self.retrieval_strategy.enable_expansion

        short_history: List[Dict[str, Any]] = []
        long_memories: List[Dict[str, Any]] = []

        if need_recall:
            short_history = self.memory_retriever.get_short_history(context.user_id)
            long_memories = self.memory_retriever.search_long_memories(
                context.user_id,
                query,
                strategy=self.retrieval_strategy,
            )

        context.memory["_context_build_short_history"] = short_history
        context.memory["_context_build_long_memories"] = long_memories

        if need_expansion and (short_history or long_memories):
            expanded_query, refined_short_history, emotion = self.query_expander.refine_and_expand(
                query,
                short_history,
                long_memories,
            )
            context.user_input = expanded_query
            context.emotion = emotion
            if refined_short_history:
                context.memory["short_history"] = refined_short_history
            if long_memories:
                context.memory["long_retrieved"] = long_memories
        else:
            context.user_input = query
            if short_history:
                context.memory["short_history"] = short_history
            if long_memories:
                context.memory["long_retrieved"] = long_memories

        return context


class EmotionAndStateSeedAgent(BaseAgent):
    """负责补充情绪分析，为后续状态处理提供基础情绪。
    
    职责：
    1. 从 ``Context`` 中提取用户输入
    2. 调用 ``EmotionAnalyzer`` 分析用户输入中的情绪
    3. 将分析结果写入 ``Context`` 中
    """

    name = "emotion_state_seed_agent"
    uses_llm = True

    def __init__(self, emotion_analyzer: EmotionAnalyzer, format_history_text):
        self.emotion_analyzer = emotion_analyzer
        self.format_history_text = format_history_text

    def run(self, context: Context) -> Context:
        if context.emotion and context.emotion.get("label"):
            return context

        query = context.user_input or context.raw_input
        short_history = context.memory.get("short_history", [])
        emotion_context = self.format_history_text(short_history=short_history) if short_history else None
        context.emotion = self.emotion_analyzer.analyze(query, emotion_context)
        return context


class MainlineMemoryAgent(BaseAgent):
    """负责主线摘要、阶段规划和记忆压缩。
    
    职责：
    1. 从 ``Context`` 中提取短期记忆和长期记忆
    2. 调用 ``MainlineMemoryUpdater`` 更新主线记忆
    3. 调用 ``MemoryCompressor`` 压缩记忆
    """

    name = "mainline_memory_agent"
    uses_llm = True

    def __init__(
        self,
        mainline_memory_updater: MainlineMemoryUpdater,
        memory_compressor: MemoryCompressor,
    ):
        self.mainline_memory_updater = mainline_memory_updater
        self.memory_compressor = memory_compressor

    def run(self, context: Context) -> Context:
        short_history = context.memory.get("short_history", [])
        long_retrieved = context.memory.get("long_retrieved", [])

        self.mainline_memory_updater.update_mainline_memory(context, short_history, long_retrieved)
        if not context.memory.get("mainline_summary") and short_history:
            context.memory["mainline_summary"] = "\n".join(
                [
                    "最近上下文：" + " | ".join(msg.get("content", "") for msg in short_history[-4:] if msg.get("content"))
                ]
            )

        self.memory_compressor.maybe_compress(context)
        return context
