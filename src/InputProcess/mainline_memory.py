from __future__ import annotations

"""主线记忆与阶段规划模块。"""

from typing import Any, Dict, List

from ..core.context import Context


class MainlineMemoryUpdater:
    """负责关键锚点提取、阶段规划与主线摘要维护。"""

    def extract_anchor_turns(self, short_history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not short_history:
            return []

        anchor_keywords = ["安排", "计划", "总结", "沿用", "继续", "开会", "时间紧", "赶", "约束", "午饭", "运动", "睡觉"]
        anchors: List[Dict[str, Any]] = []
        for msg in short_history:
            content = msg.get("content", "")
            if any(keyword in content for keyword in anchor_keywords):
                anchors.append(msg)

        if not anchors:
            anchors = short_history[:2]

        return anchors[-4:]

    def build_stage_plan(self, context: Context, short_history: List[Dict[str, Any]], long_memories: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        text = self._format_history_text(short_history=short_history, long_memories=long_memories)
        combined = f"{text}\n{context.raw_input}".strip()
        if not combined:
            return []

        stages: List[Dict[str, str]] = []
        stage_specs = [
            ("morning", ["早上", "上午", "起床", "安排", "节奏"]),
            ("meeting_prep", ["开会", "会议", "准备", "汇报", "进度"]),
            ("lunch_recovery", ["午饭", "中午", "专注", "恢复", "走神"]),
            ("evening_exercise", ["晚上", "下班", "运动", "睡觉", "睡眠"]),
            ("next_day", ["明天", "继续", "沿用", "复用", "总结"]),
        ]
        for stage_name, keywords in stage_specs:
            matched = [kw for kw in keywords if kw in combined]
            if matched:
                stages.append({"stage": stage_name, "keywords": ",".join(matched[:3])})

        if not stages and context.raw_input:
            stages.append({"stage": "general", "keywords": context.raw_input[:20]})
        return stages[:5]

    def update_mainline_memory(
        self,
        context: Context,
        short_history: List[Dict[str, Any]],
        long_memories: List[Dict[str, Any]],
    ) -> None:
        summary_parts: List[str] = []

        anchors = self.extract_anchor_turns(short_history)
        if anchors:
            context.memory["anchor_turns"] = anchors
            first_anchor = anchors[0].get("content", "")
            last_anchor = anchors[-1].get("content", "")
            if first_anchor:
                summary_parts.append(f"起点：{first_anchor}")
            if last_anchor and last_anchor != first_anchor:
                summary_parts.append(f"延续：{last_anchor}")

        stage_plan = self.build_stage_plan(context, short_history, long_memories)
        if stage_plan:
            context.memory["stage_plan"] = stage_plan
            stage_text = "; ".join(f"{item.get('stage')}: {item.get('keywords', '')}" for item in stage_plan)
            summary_parts.append("阶段：" + stage_text)

        if long_memories:
            memory_preview = [mem.get("content", "") for mem in long_memories[:2] if mem.get("content")]
            if memory_preview:
                summary_parts.append("相关记忆：" + " | ".join(memory_preview))

        if short_history:
            recent_user_turns = [msg.get("content", "") for msg in short_history[-4:] if msg.get("content")]
            if recent_user_turns:
                summary_parts.append("最近上下文：" + " | ".join(recent_user_turns[:4]))
        elif context.raw_input:
            summary_parts.append(f"当前输入：{context.raw_input}")

        if summary_parts:
            context.memory["mainline_summary"] = "\n".join(summary_parts)

    @staticmethod
    def _format_history_text(
        short_history: List[Dict[str, Any]],
        long_memories: List[Dict[str, Any]],
    ) -> str:
        parts: List[str] = []
        for msg in short_history:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            parts.append(f"{role}: {content}")

        for mem in long_memories:
            parts.append(mem.get("content", ""))

        return "\n".join(parts)
