"""记忆检索策略。

定义不同场景的记忆检索配置，包括记忆类型过滤、召回数量等。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


class RetrievalStrategy:
    """记忆检索策略。
    
    封装记忆检索时的过滤条件、召回数量等配置。
    
    Attributes:
        memory_types: 需要召回的记忆类型列表，None 表示不限制。
        top_k: 最终返回的记忆数量。
        enable_expansion: 是否启用 query 扩写。
    """
    
    def __init__(
        self,
        memory_types: Optional[List[str]] = None,
        top_k: int = 3,
        enable_expansion: bool = True,
    ):
        self.memory_types = memory_types
        self.top_k = top_k
        self.enable_expansion = enable_expansion
    
    @property
    def milvus_filters(self) -> Dict[str, Any]:
        """生成 Milvus 过滤条件。
        
        Returns:
            用于 Milvus search 的 filters 字典。
        """
        if self.memory_types:
            return {"metadata.memory_type": self.memory_types}
        return {}


# ========== 预定义策略 ==========

BASE_STRATEGY = RetrievalStrategy(
    memory_types=None,
    top_k=2,
    enable_expansion=False,
)
"""基础对话策略：少量记忆，不扩写，适用于日常对话默认路径。"""

TASK_STRATEGY = RetrievalStrategy(
    memory_types=["plan", "fact"],
    top_k=5,
    enable_expansion=True,
)
"""任务规划策略：计划和事实型记忆，top_k=5。"""

EMOTION_STRATEGY = RetrievalStrategy(
    memory_types=["emotion", "relationship"],
    top_k=5,
    enable_expansion=True,
)
"""情感陪伴策略：情绪和关系型记忆，top_k=5。"""
