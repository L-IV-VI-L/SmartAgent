"""
Agent 相关 Prompt 模板模块

提供意图分析和查询扩写的系统提示词模板。
"""

from __future__ import annotations

TASK_JUDGE_PROMPT = """分析用户输入，判断两个问题：

1. 是否需要召回历史记忆？
   需要：提到过去对话、追问之前话题、含指代词需上下文
   不需要：独立问题、闲聊、全新话题

2. 是否需要扩写用户输入？
   需要：输入简短、含指代词、上下文依赖强
   不需要：输入完整明确

直接返回 JSON：
{{"need_recall": true/false, "need_expansion": true/false}}"""

TASK_CONTEXT_BUILD_PROMPT = """完成三个任务：

任务1：精炼短期对话历史
- 保留事实信息（偏好、需求、约束）和任务进度
- 去除问候、感谢、闲聊
- 保持原始角色（user/assistant）

任务2：扩写用户当前问题
- 补全省略成分，明确指代词
- 保持原意，使问题可独立理解

任务3：分析用户当前情绪
结合历史当前输入分析情绪。
情绪类型参考：{emotion_labels}
情绪强度：0.1~1.0

直接返回 JSON：
{{
  "refined_history": [
    {{"role": "user", "content": "精炼后的用户发言"}},
    {{"role": "assistant", "content": "精炼后的助手回复"}}
  ],
  "expanded_query": "扩写后的完整问题",
  "emotion": {{
    "label": "情绪类型",
    "score": 0.5
  }}
}}

注意：
- 历史已足够精炼可保持原样
- 问题已完整明确 expanded_query 可与原问题相同
- refined_history 可为空数组"""
