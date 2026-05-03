class Context:
    def __init__(self, user_id: str, session_id: str = None):
        self.user_id = user_id
        self.session_id = session_id
        self.raw_input = ""
        self.user_input = ""
        self.response = ""
        self.response_text = ""
        self.persona = {
            "nickname": "",
            "custom_persona": "",
            "personality_weights": {},
            "tone_weights": {},
        }
        self.emotion = {"label": "neutral", "score": 0.5}
        self.memory = {
            "short_history": [],
            "compressed": "",
            "long_retrieved": [],
            "mainline_summary": "",
            "stage_plan": [],
            "anchor_turns": [],
            "compressed_history": [],
            "saved_long_memories": [],
            "need_recall": False,
            "need_expansion": False,
        }
        self.tools = {"decision": {}, "results": [], "error": None}
        self.text = ""

    @staticmethod
    def _sanitize_weights(weights):
        sanitized = {}
        for key, value in (weights or {}).items():
            try:
                sanitized[key] = max(0.0, float(value))
            except (TypeError, ValueError):
                sanitized[key] = 0.0
        return sanitized

    def normalize_persona(self):
        self.persona["personality_weights"] = self._sanitize_weights(self.persona.get("personality_weights"))
        self.persona["tone_weights"] = self._sanitize_weights(self.persona.get("tone_weights"))
        try:
            self.emotion["score"] = max(0.0, float(self.emotion.get("score", 0.0) or 0.0))
        except (TypeError, ValueError):
            self.emotion["score"] = 0.0
        return self

    def build_prompt(self):
        self.normalize_persona()

        lines = ["【助手基础设定】"]
        lines.append(self.persona["custom_persona"] or "你是用户的朋友，一个温柔、体贴、善解人意的贴心朋友。")

        positive_personality = [(k, v) for k, v in self.persona["personality_weights"].items() if v > 0]
        if positive_personality:
            lines.append("\n【当前人格】")
            for k, _ in positive_personality:
                lines.append(f"- {k}")

        positive_tone = [(k, v) for k, v in self.persona["tone_weights"].items() if v > 0]
        if positive_tone:
            lines.append("\n【当前语气】")
            for k, _ in positive_tone:
                lines.append(f"- {k}")

        lines.append(f"\n【用户情绪】{self.emotion['label']}")
        if self.memory.get("mainline_summary"):
            lines.append("\n【对话主线摘要】")
            lines.append(self.memory["mainline_summary"])
        elif self.memory.get("compressed"):
            lines.append("\n【对话主线摘要】")
            lines.append(self.memory["compressed"])

        if self.memory.get("anchor_turns"):
            lines.append("\n【关键锚点】")
            for msg in self.memory["anchor_turns"]:
                lines.append(f"{msg.get('role', 'unknown')}：{msg.get('content', '')}")

        if self.memory.get("stage_plan"):
            lines.append("\n【阶段计划】")
            for item in self.memory["stage_plan"]:
                stage = item.get("stage", "unknown")
                keywords = item.get("keywords", "")
                lines.append(f"- {stage}: {keywords}")

        lines.append("\n【最近对话】")
        for msg in self.memory["short_history"]:
            lines.append(f"{msg.get('role', 'unknown')}：{msg.get('content', '')}")

        if self.memory["long_retrieved"]:
            lines.append("\n【以往相关记忆】")
            for m in self.memory["long_retrieved"]:
                content = m.get("content", str(m)) if isinstance(m, dict) else str(m)
                lines.append(f"- {content}")

        if self.tools["results"]:
            lines.append("\n【工具信息】")
            for r in self.tools["results"]:
                lines.append(f"- {r}")

        lines.append(f"\n【用户输入】{self.user_input}")
        self.text = "\n".join(lines)
        return self.text
