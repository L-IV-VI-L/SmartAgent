from __future__ import annotations

"""长期记忆相关 Agent。"""

from typing import Callable, List, Optional

from ..core.context import Context
from ..database.repositories import MemoryRepository
from ..InputProcess.long_memory_extractor import LongMemoryExtractor
from ..InputProcess.memory_schema import LongMemoryRecord
from ..utils.logger import get_logger
from .base import BaseAgent

logger = get_logger(__name__)


class LongMemoryExtractAgent(BaseAgent):
    """从本轮对话中提取结构化长期记忆并写入存储。
    
    职责：
    1. 从 ``Context`` 中提取本轮对话的回复文本
    2. 调用 ``LongMemoryExtractor`` 提取结构化长期记忆
    3. 调用 ``MemoryRepository`` 将提取的长期记忆写入存储
    4. 将写入的长期记忆记录写入 ``Context`` 中
    """

    name = "long_memory_extract_agent"
    uses_llm = True

    def __init__(
        self,
        extractor: Optional[LongMemoryExtractor] = None,
        memory_repo: Optional[MemoryRepository] = None,
        embedding_fn: Optional[Callable[[str], Optional[List[float]]]] = None,
        embedding_dimension: int = 1536,
    ):
        self.extractor = extractor or LongMemoryExtractor()
        self.memory_repo = memory_repo or MemoryRepository()
        self.embedding_fn = embedding_fn
        self.embedding_dimension = embedding_dimension

    def run(self, context: Context) -> Context:
        response_text = getattr(context, "response_text", "") or getattr(context, "response", "") or ""
        if not response_text:
            context.memory["saved_long_memories"] = []
            return context

        try:
            memories = self.extractor.extract(context)
        except Exception as e:
            logger.error("结构化长期记忆提取失败: %s", e)
            context.memory["saved_long_memories"] = []
            return context

        saved: List[dict] = []
        for memory in memories:
            try:
                self._attach_embedding(memory)
                self.memory_repo.append_structured(memory)
                saved.append(
                    {
                        "doc_id": memory.doc_id,
                        "content": memory.content,
                        "memory_type": memory.memory_type,
                        "tags": memory.tags,
                        "importance": memory.importance,
                        "confidence": memory.confidence,
                    }
                )
            except Exception as e:
                logger.error("结构化长期记忆写入失败 doc_id=%s: %s", memory.doc_id, e)

        context.memory["saved_long_memories"] = saved
        if saved:
            logger.info("已写入 %d 条结构化长期记忆", len(saved))
        return context

    def _attach_embedding(self, memory: LongMemoryRecord) -> None:
        if memory.embedding is not None:
            return
        if self.embedding_fn is None:
            memory.embedding = [0.0] * self.embedding_dimension
            return
        vector = self.embedding_fn(memory.embedding_text)
        memory.embedding = vector or [0.0] * self.embedding_dimension
