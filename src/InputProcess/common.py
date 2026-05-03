from __future__ import annotations

"""InputProcess 通用工具函数。"""

from typing import Any, Dict, List, Optional

try:
    import tiktoken  # type: ignore
except Exception:  # pragma: no cover - fallback for incompatible runtime/deps
    tiktoken = None

from ..utils.json_utils import parse_json_response as _parse_json_response


class InputProcessCommon:
    def __init__(self):
        self._tiktoken_encoder = None

    def _get_tiktoken_encoder(self):
        if tiktoken is None:
            return None
        if self._tiktoken_encoder is None:
            try:
                self._tiktoken_encoder = tiktoken.encoding_for_model("gpt-3.5-turbo")
            except Exception:
                self._tiktoken_encoder = tiktoken.get_encoding("cl100k_base")
        return self._tiktoken_encoder

    def count_tokens(self, text: str) -> int:
        if not text:
            return 0
        try:
            encoder = self._get_tiktoken_encoder()
            if encoder is not None:
                return len(encoder.encode(text))
        except Exception:
            pass
        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        other_chars = len(text) - chinese_chars
        return int(chinese_chars / 1.5 + other_chars / 4)

    @staticmethod
    def parse_json_response(response: str) -> Optional[Dict[str, Any]]:
        return _parse_json_response(response)

    @staticmethod
    def normalize_emotion(emotion_data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
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

    @staticmethod
    def format_history_text(
        short_history: Optional[List[Dict[str, Any]]] = None,
        long_memories: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        parts = []

        if short_history:
            for msg in short_history:
                role = msg.get("role", "unknown")
                content = msg.get("content", "")
                parts.append(f"{role}: {content}")

        if long_memories:
            for mem in long_memories:
                parts.append(mem.get("content", ""))

        return "\n".join(parts)
