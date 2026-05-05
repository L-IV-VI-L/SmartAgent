from __future__ import annotations

"""长期记忆提取与标准化。"""

import json
import time
from typing import Any, Dict, List, Optional

from ..core.context import Context
from ..prompts import LONG_MEMORY_EXTRACT_PROMPT
from ..Tools.BaseLLM import BaseLLMClient
from ..utils.json_utils import extract_json_from_text
from .memory_schema import (
    LongMemoryRecord,
    MIN_MEMORY_CONFIDENCE,
    MIN_MEMORY_IMPORTANCE,
    build_embedding_text,
    build_memory_doc_id,
    clamp_score,
    normalize_memory_type,
    normalize_status,
    normalize_tags,
)


class LongMemoryNormalizer:
    """将 LLM 输出的长期记忆候选清洗为标准结构。"""

    def normalize(
        self,
        raw_memories: List[Dict[str, Any]],
        user_id: str,
        session_id: Optional[str] = None,
    ) -> List[LongMemoryRecord]:
        now = time.time()
        records: List[LongMemoryRecord] = []

        for index, item in enumerate(raw_memories or []):
            if not isinstance(item, dict):
                continue

            content = str(item.get("content", "")).strip()
            if not content:
                continue

            importance = clamp_score(item.get("importance"), default=0.0)
            confidence = clamp_score(item.get("confidence"), default=0.0)
            if importance < MIN_MEMORY_IMPORTANCE or confidence < MIN_MEMORY_CONFIDENCE:
                continue

            memory_type = normalize_memory_type(item.get("memory_type", ""))
            tags = normalize_tags(item.get("tags", []))
            status = normalize_status(item.get("status", "active"))
            embedding_text = build_embedding_text(memory_type, tags, content)
            turn_ids_raw = item.get("turn_ids", [])

            records.append(
                LongMemoryRecord(
                    doc_id=str(item.get("doc_id") or build_memory_doc_id(user_id, index=index, now=now)),
                    user_id=user_id,
                    content=content,
                    embedding_text=embedding_text,
                    tags=tags,
                    memory_type=memory_type,
                    importance=importance,
                    confidence=confidence,
                    source=str(item.get("source") or "summary").strip() or "summary",
                    session_id=session_id or "",
                    turn_ids=[str(turn_id) for turn_id in turn_ids_raw] if isinstance(turn_ids_raw, list) else [],
                    raw_excerpt=str(item.get("raw_excerpt", "")).strip(),
                    status=status,
                    create_time=now,
                    update_time=now,
                    last_access_time=0.0,
                )
            )

        return records


class LongMemoryExtractor:
    """调用 LLM 从上下文中提取结构化长期记忆。"""

    def __init__(self, llm_client: Optional[BaseLLMClient] = None, normalizer: Optional[LongMemoryNormalizer] = None):
        self.llm_client = llm_client or BaseLLMClient()
        self.normalizer = normalizer or LongMemoryNormalizer()

    def extract(self, context: Context) -> List[LongMemoryRecord]:
        prompt = self._build_prompt(context)
        response = self.llm_client.chat_with_prompt(
            prompt=prompt,
            system_message=LONG_MEMORY_EXTRACT_PROMPT,
        )
        payload = self._parse_json(response)
        if not payload.get("should_save"):
            return []
        memories = payload.get("memories", [])
        if not isinstance(memories, list):
            return []
        return self.normalizer.normalize(memories, user_id=context.user_id, session_id=context.session_id)

    def _build_prompt(self, context: Context) -> str:
        short_history = context.memory.get("short_history", []) if getattr(context, "memory", None) else []
        long_retrieved = context.memory.get("long_retrieved", []) if getattr(context, "memory", None) else []
        response_text = getattr(context, "response_text", "") or getattr(context, "response", "") or ""

        return "\n".join(
            [
                "【用户ID】",
                context.user_id,
                "\n【本轮用户输入】",
                context.raw_input or context.user_input,
                "\n【本轮助手回复】",
                response_text,
                "\n【用户情绪】",
                json.dumps(getattr(context, "emotion", {}), ensure_ascii=False),
                "\n【最近对话】",
                json.dumps(short_history[-8:], ensure_ascii=False),
                "\n【本轮召回的相关长期记忆】",
                json.dumps(long_retrieved, ensure_ascii=False),
            ]
        )

    def _parse_json(self, text: str) -> Dict[str, Any]:
        result = extract_json_from_text(text)
        if result is None:
            return {"should_save": False, "memories": []}
        return result
