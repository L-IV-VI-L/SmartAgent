from __future__ import annotations

"""记忆压缩模块。

负责在上下文超过阈值时，将较早历史与长期召回压缩成摘要，
同时保留最近对话和关键锚点，避免丢失局部语义。
"""

from typing import Any, Callable, Dict, List, Optional

from ..Tools.BaseLLM import BaseLLMClient
from ..core.context import Context


class MemoryCompressor:
    """根据 token 阈值对 context 中的记忆进行轻量压缩。"""

    def __init__(
        self,
        llm_client: BaseLLMClient,
        count_tokens: Callable[[str], int],
        format_history_text: Callable[..., str],
        compress_prompt: str,
        soft_limit: int = 8000,
        hard_limit: int = 18000,
        recent_history_keep: int = 6,
        max_anchor_turns: int = 4,
        max_long_retrieved_after_compress: int = 2,
    ):
        self.llm_client = llm_client
        self.count_tokens = count_tokens
        self.format_history_text = format_history_text
        self.compress_prompt = compress_prompt
        self.soft_limit = soft_limit
        self.hard_limit = hard_limit
        self.recent_history_keep = recent_history_keep
        self.max_anchor_turns = max_anchor_turns
        self.max_long_retrieved_after_compress = max_long_retrieved_after_compress

    def _call_llm_text(self, user_prompt: str, system_prompt: str) -> Optional[str]:
        try:
            return self.llm_client.chat_with_prompt(
                prompt=user_prompt,
                system_message=system_prompt,
            ).strip()
        except Exception:
            return None

    def _prompt_token_count(self, context: Context) -> int:
        return self.count_tokens(context.build_prompt())

    def _should_compress(self, context: Context) -> bool:
        token_count = self._prompt_token_count(context)
        short_history = context.memory.get("short_history", []) or []
        long_retrieved = context.memory.get("long_retrieved", []) or []

        if token_count >= self.hard_limit:
            return bool(short_history or long_retrieved)

        if token_count <= self.soft_limit:
            return False

        compressible_history = short_history[:-self.recent_history_keep]
        return (
            len(compressible_history) >= 4
            or len(long_retrieved) > self.max_long_retrieved_after_compress
        )

    def _compress_memories(self, memories: List[Dict[str, Any]]) -> str:
        if not memories:
            return ""
        memory_text = self.format_history_text(short_history=memories)
        compressed = self._call_llm_text(
            user_prompt=(
                "请压缩以下对话，并务必保留：主线任务、已确认约束、已形成计划、关键因果关系、用户偏好或目标。\n"
                f"\n对话内容：\n{memory_text}"
            ),
            system_prompt=self.compress_prompt,
        )
        if compressed:
            return compressed
        fallback = memory_text[:200]
        return f"主线摘要：{fallback}"

    def _deduplicate_messages(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        seen = set()
        deduplicated: List[Dict[str, Any]] = []
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            if not content:
                continue
            key = (role, content)
            if key in seen:
                continue
            seen.add(key)
            deduplicated.append(msg)
        return deduplicated

    def _merge_compressed_summary(self, old_summary: str, new_summary: str) -> str:
        if old_summary and new_summary:
            return f"{old_summary}\n{new_summary}"
        return new_summary or old_summary

    def maybe_compress(self, context: Context) -> None:
        if not self._should_compress(context):
            return

        short_history = context.memory.get("short_history", []) or []
        long_retrieved = context.memory.get("long_retrieved", []) or []
        recent_turns = short_history[-self.recent_history_keep:] if short_history else []
        history_to_compress = short_history[:-self.recent_history_keep]

        if not history_to_compress and self._prompt_token_count(context) >= self.hard_limit:
            history_to_compress = short_history
            recent_turns = short_history[-4:] if len(short_history) > 4 else short_history

        if (
            not history_to_compress
            and len(long_retrieved) <= self.max_long_retrieved_after_compress
        ):
            return

        memories_to_compress = history_to_compress + long_retrieved
        compressed = self._compress_memories(memories_to_compress)
        if not compressed:
            return

        context.memory["compressed_history"] = memories_to_compress
        context.memory["compressed"] = self._merge_compressed_summary(
            context.memory.get("compressed", ""),
            compressed,
        )

        summary_message = {
            "role": "system",
            "content": f"历史对话摘要：{context.memory['compressed']}",
        }
        anchor_turns = context.memory.get("anchor_turns", [])[-self.max_anchor_turns:]
        context.memory["anchor_turns"] = anchor_turns
        context.memory["short_history"] = self._deduplicate_messages(
            [summary_message] + anchor_turns + recent_turns
        )
        context.memory["long_retrieved"] = long_retrieved[:self.max_long_retrieved_after_compress]
        context.memory["mainline_summary"] = self._merge_compressed_summary(
            context.memory.get("mainline_summary", ""),
            compressed,
        )
