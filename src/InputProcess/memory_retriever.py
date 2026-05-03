from __future__ import annotations

"""记忆召回模块。"""

from typing import Any, Callable, Dict, List, Optional, Tuple

from ..utils.logger import get_logger
from ..database.memory_decay import MemoryDecayModule
from ..database.repositories import ConversationRepository, MemoryRepository
from .retrieval_strategies import RetrievalStrategy

logger = get_logger(__name__)



class MemoryRetriever:
    """负责短期记忆召回、长期记忆检索、重排与强化。"""

    def __init__(
        self,
        conversation_repo: ConversationRepository,
        memory_repo: MemoryRepository,
        max_short_history: int = 10,
        decay_module_factory: Callable[[], MemoryDecayModule] = MemoryDecayModule,
    ):
        self.conversation_repo = conversation_repo
        self.memory_repo = memory_repo
        self.max_short_history = max_short_history
        self.decay_module_factory = decay_module_factory

    def get_short_history(self, user_id: str) -> List[Dict[str, Any]]:
        try:
            return self.conversation_repo.get_recent(user_id, self.max_short_history)
        except Exception as e:
            logger.error("Redis 获取短期记忆失败: %s", e)
            return []

    def calculate_composite_score(
        self,
        semantic_score: float,
        weight: float,
        semantic_weight: float = 0.8,
        memory_weight_ratio: float = 0.2,
        importance: float = 0.0,
        confidence: float = 0.0,
    ) -> float:
        normalized_weight = weight / 5.0
        base_score = semantic_score * semantic_weight + normalized_weight * memory_weight_ratio
        return base_score + importance * 0.15 + confidence * 0.1

    def rerank_memories(self, memories: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not memories:
            return memories

        scored_memories = []
        for memory in memories:
            composite_score = self.calculate_composite_score(
                semantic_score=memory.get("score", 0.0),
                weight=memory.get("weight", 0.0),
                importance=memory.get("importance", 0.0),
                confidence=memory.get("confidence", 0.0),
            )
            memory_with_score = memory.copy()
            memory_with_score["composite_score"] = composite_score
            scored_memories.append(memory_with_score)

        return sorted(scored_memories, key=lambda x: x.get("composite_score", 0.0), reverse=True)

    def build_memory_items(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        memories = []
        doc_ids = [result.get("metadata", {}).get("doc_id") for result in results]
        structured_docs = {}
        try:
            docs = self.memory_repo.get_by_doc_ids([doc_id for doc_id in doc_ids if doc_id])
            structured_docs = {doc.get("doc_id"): doc for doc in docs}
        except Exception as e:
            logger.error("MongoDB 回查结构化记忆失败: %s", e)

        for result in results:
            metadata = result.get("metadata", {})
            doc_id = metadata.get("doc_id")
            structured_doc = structured_docs.get(doc_id, {})
            memories.append({
                "role": "memory",
                "doc_id": doc_id,
                "content": structured_doc.get("content") or result.get("content", ""),
                "score": result.get("score", 0.0),
                "weight": result.get("weight", metadata.get("weight", 0.0)),
                "create_time": structured_doc.get("create_time", metadata.get("create_time", 0.0)),
                "memory_type": structured_doc.get("memory_type", metadata.get("memory_type", "")),
                "tags": structured_doc.get("tags", metadata.get("tags", [])),
                "importance": structured_doc.get("importance", metadata.get("importance", 0.0)),
                "confidence": structured_doc.get("confidence", metadata.get("confidence", 0.0)),
                "metadata": {**metadata, **structured_doc},
            })
        return memories

    def search_long_memories(
        self,
        user_id: str,
        query: str,
        top_k: int = 3,
        strategy: Optional[RetrievalStrategy] = None,
    ) -> List[Dict[str, Any]]:
        """检索长期记忆。

        Args:
            user_id: 用户 ID。
            query: 查询文本。
            top_k: 最终返回的记忆数量。
            strategy: 检索策略，提供时 top_k 将被忽略。

        Returns:
            检索到的记忆列表。如果 Milvus 不可用，返回空列表并降级到只使用短期记忆。
        """
        effective_strategy = strategy or RetrievalStrategy(top_k=top_k)
        effective_top_k = effective_strategy.top_k

        filters: Dict[str, Any] = {"user_id": user_id} if user_id else {}
        filters.update(effective_strategy.milvus_filters)

        try:
            results = self.memory_repo.search(
                query=query,
                top_k=effective_top_k * 2,
                filters=filters if filters else None,
            )
            memories = self.build_memory_items(results)
            if not memories:
                logger.info("Milvus 检索未找到记忆, user_id=%s, query=%s", user_id, query)
                return []
            final_memories = self.rerank_memories(memories)[:effective_top_k]
            self.reinforce_selected_memories(final_memories)
            try:
                self.memory_repo.update_access_time([mem.get("doc_id") for mem in final_memories if mem.get("doc_id")])
            except Exception as e:
                logger.warning("访问时间更新失败: %s", e)
            logger.info(
                "Milvus 检索完成, user_id=%s, 找到 %d 条, 返回 %d 条",
                user_id, len(memories), len(final_memories)
            )
            return final_memories
        except Exception as e:
            logger.warning(
                "Milvus 长期记忆检索失败，已降级到仅使用短期记忆模式: %s", e
            )
            return []

    def reinforce_selected_memories(self, final_memories: List[Dict[str, Any]]) -> None:
        try:
            decay_module = self.decay_module_factory()
            for mem in final_memories:
                memory_id = mem.get("metadata", {}).get("id")
                current_weight = mem.get("weight", 0.0)
                if memory_id is not None:
                    new_weight = decay_module.reinforce_on_retrieval(memory_id, current_weight)
                    mem["weight"] = new_weight

        except Exception as e:
            logger.error("记忆强化处理失败: %s", e)

    def recall(self, user_id: str, query: str, need_recall: bool) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        if not need_recall:
            return [], []
        return self.get_short_history(user_id), self.search_long_memories(user_id, query)
