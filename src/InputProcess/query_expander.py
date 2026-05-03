from __future__ import annotations

"""查询判断、扩写与状态构建模块。"""

from typing import Any, Callable, Dict, List, Optional, Tuple


class QueryExpander:
    """负责意图判断、查询扩写与用户状态构建。"""

    def __init__(
        self,
        call_llm_json: Callable[[str, str], Optional[Dict[str, Any]]],
        judge_prompt: str,
        expand_prompt: str,
        emotion_labels: str,
        pronouns: List[str],
        recall_keywords: List[str],
        normalize_emotion: Callable[[Optional[Dict[str, Any]]], Dict[str, Any]],
        format_history_text: Callable[[Optional[List[Dict[str, Any]]], Optional[List[Dict[str, Any]]]], str],
    ):
        self.call_llm_json = call_llm_json
        self.judge_prompt = judge_prompt
        self.expand_prompt = expand_prompt
        self.emotion_labels = emotion_labels
        self.pronouns = pronouns
        self.recall_keywords = recall_keywords
        self.normalize_emotion = normalize_emotion
        self.format_history_text = format_history_text

    def unified_judge(self, query: str) -> Tuple[bool, bool]:
        query = query.strip()
        need_recall_keywords = False
        need_expansion_keywords = False

        if len(query) >= 5:
            for keyword in self.recall_keywords:
                if keyword in query:
                    need_recall_keywords = True
                    break

            if len(query) <= 20:
                for pronoun in self.pronouns:
                    if pronoun in query:
                        need_expansion_keywords = True
                        break

        if len(query) < 5:
            return True, True

        if len(query) > 50 and not need_recall_keywords and not need_expansion_keywords:
            return False, False

        result = self.call_llm_json(
            user_prompt=f"用户输入：{query}",
            system_prompt=self.judge_prompt,
        )

        if result:
            return bool(result.get("need_recall", False)), bool(result.get("need_expansion", False))

        return need_recall_keywords, (need_expansion_keywords or len(query) < 10)

    def refine_and_expand(
        self,
        query: str,
        short_history: List[Dict[str, Any]],
        long_memories: List[Dict[str, Any]],
    ) -> Tuple[str, Optional[List[Dict[str, Any]]], Dict[str, Any]]:
        history_text = self.format_history_text(short_history=short_history, long_memories=long_memories)

        system_prompt = self.expand_prompt.format(emotion_labels=self.emotion_labels)
        user_prompt = f"短期对话历史：\n{history_text}\n\n用户当前问题：{query}\n\n请精炼历史、扩写问题并分析情绪："

        result = self.call_llm_json(user_prompt, system_prompt)

        if result:
            expanded_query = result.get("expanded_query", query)

            refined_history = result.get("refined_history", [])
            if isinstance(refined_history, list) and refined_history:
                refined_history = [
                    {"role": item["role"], "content": item["content"]}
                    for item in refined_history
                    if isinstance(item, dict) and "role" in item and "content" in item
                ]

            emotion = self.normalize_emotion(result.get("emotion"))

            return expanded_query, refined_history if refined_history else None, emotion

        return query, None, {"label": "neutral", "score": 0.5}

    def build_user_state(
        self,
        query: str,
        short_history: List[Dict[str, Any]],
        long_memories: List[Dict[str, Any]],
        need_expansion: bool,
    ) -> Tuple[str, Dict[str, Any]]:
        if need_expansion and (short_history or long_memories):
            expanded_query, refined_short_history, emotion = self.refine_and_expand(query, short_history, long_memories)
            if refined_short_history:
                short_history = refined_short_history
            return expanded_query, emotion
        return query, {"label": "neutral", "score": 0.5}
