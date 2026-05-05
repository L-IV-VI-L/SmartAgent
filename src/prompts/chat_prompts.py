"""
聊天相关 Prompt 模板模块

提供情绪分析的系统提示词模板。
"""

from __future__ import annotations

CHAT_EMOTION_PROMPT = """分析用户输入的当前情绪状态。

情绪类型参考：{emotion_labels}
情绪强度：0.1~1.0，数值越高越强烈

直接返回 JSON，不要解释：
{{"label": "情绪类型", "score": 强度值}}"""
