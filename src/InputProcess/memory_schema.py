from __future__ import annotations

"""结构化长期记忆的数据模型与标准化工具。"""

import time
from dataclasses import dataclass, field
from typing import List, Optional


MEMORY_TYPES = {
    "profile",
    "preference",
    "goal",
    "constraint",
    "event",
    "relationship",
    "emotion",
    "task",
    "knowledge",
    "decision",
    "boundary",
}

MEMORY_STATUSES = {
    "active",
    "outdated",
    "contradicted",
    "deleted",
}

MIN_MEMORY_IMPORTANCE = 0.5
MIN_MEMORY_CONFIDENCE = 0.65
MAX_MEMORY_TAGS = 8
DEFAULT_MEMORY_TYPE = "event"
DEFAULT_MEMORY_STATUS = "active"


@dataclass
class LongMemoryRecord:
    """结构化长期记忆单元。

    content 是给大模型阅读的记忆正文；embedding_text 是用于向量化检索的文本。
    """

    doc_id: str
    user_id: str
    content: str
    embedding_text: str
    memory_type: str
    importance: float
    confidence: float
    embedding: Optional[List[float]] = None
    tags: List[str] = field(default_factory=list)
    source: str = "summary"
    session_id: str = ""
    turn_ids: List[str] = field(default_factory=list)
    raw_excerpt: str = ""
    status: str = DEFAULT_MEMORY_STATUS
    weight: float = 0.0
    create_time: float = 0.0
    update_time: float = 0.0
    last_access_time: float = 0.0

    def to_mongo_document(self) -> dict:
        return {
            "doc_id": self.doc_id,
            "user_id": self.user_id,
            "content": self.content,
            "embedding_text": self.embedding_text,
            "tags": self.tags,
            "memory_type": self.memory_type,
            "importance": self.importance,
            "confidence": self.confidence,
            "source": self.source,
            "session_id": self.session_id,
            "turn_ids": self.turn_ids,
            "raw_excerpt": self.raw_excerpt,
            "status": self.status,
            "weight": self.weight,
            "create_time": self.create_time,
            "update_time": self.update_time,
            "last_access_time": self.last_access_time,
        }


def clamp_score(value, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = default
    return max(0.0, min(1.0, number))


def normalize_memory_type(memory_type: str) -> str:
    memory_type = (memory_type or "").strip().lower()
    return memory_type if memory_type in MEMORY_TYPES else DEFAULT_MEMORY_TYPE


def normalize_status(status: str) -> str:
    status = (status or "").strip().lower()
    return status if status in MEMORY_STATUSES else DEFAULT_MEMORY_STATUS


def normalize_tags(tags) -> List[str]:
    if not isinstance(tags, list):
        return []

    normalized: List[str] = []
    seen = set()
    for tag in tags:
        text = str(tag).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        normalized.append(text)
        if len(normalized) >= MAX_MEMORY_TAGS:
            break
    return normalized


def build_embedding_text(memory_type: str, tags: List[str], content: str) -> str:
    tag_text = "、".join(tags) if tags else "无"
    return f"类型：{memory_type}\n标签：{tag_text}\n内容：{content}"


def build_memory_doc_id(user_id: str, index: int = 0, now: Optional[float] = None) -> str:
    now = now or time.time()
    return f"{user_id}_{int(now * 1000)}_{index}"
