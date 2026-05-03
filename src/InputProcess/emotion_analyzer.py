from __future__ import annotations

"""情绪分析模块。"""

from typing import Any, Callable, Dict, Optional


class EmotionAnalyzer:
    """负责情绪分析与情绪结果归一化。"""

    def __init__(
        self,
        call_llm_json: Callable[[str, str], Optional[Dict[str, Any]]],
        emotion_prompt: str,
        emotion_labels: str,
    ):
        self.call_llm_json = call_llm_json
        self.emotion_prompt = emotion_prompt
        self.emotion_labels = emotion_labels

    def normalize(self, emotion_data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
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

    def analyze(
        self,
        query: str,
        context_text: Optional[str] = None,
    ) -> Dict[str, Any]:
        system_prompt = self.emotion_prompt.format(emotion_labels=self.emotion_labels)
        user_prompt = f"用户输入：{query}"
        if context_text:
            user_prompt = f"短期对话历史：\n{context_text}\n\n{user_prompt}"

        result = self.call_llm_json(user_prompt, system_prompt)
        return self.normalize(result)
