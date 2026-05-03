# Prompts 模块文档

## 概述

Prompts 模块集中管理所有 LLM 调用的 Prompt 模板，便于维护和优化。

## 文件结构

```
src/prompts/
├── agent_prompts.py      # Agent 相关 Prompt
├── chat_prompts.py       # 对话相关 Prompt
├── memory_prompts.py     # 记忆相关 Prompt
├── responsen_prompts.py  # 回复生成 Prompt
├── state_prompts.py      # 状态管理 Prompt
├── tool_prompts.py       # 工具相关 Prompt
└── __init__.py
```

---

## 1. Agent Prompts (agent_prompts.py)

包含各 Agent 使用的 Prompt 模板：

| Prompt | 说明 |
|--------|------|
| `TASK_JUDGE_PROMPT` | 任务判断 Prompt |
| `TASK_CONTEXT_BUILD_PROMPT` | 上下文构建 Prompt |

---

## 2. 对话 Prompts (chat_prompts.py)

包含对话相关的 Prompt 模板：

| Prompt | 说明 |
|--------|------|
| `CHAT_EMOTION_PROMPT` | 情绪分析 Prompt |

---

## 3. 记忆 Prompts (memory_prompts.py)

包含记忆管理相关的 Prompt 模板：

| Prompt | 说明 |
|--------|------|
| `MEMORY_COMPRESS_PROMPT` | 记忆压缩 Prompt |

---

## 4. 状态管理 Prompts (state_prompts.py)

包含状态和人格调整相关的 Prompt 模板。

---

## 5. 工具 Prompts (tool_prompts.py)

包含工具调用决策相关的 Prompt 模板。

---

## 设计原则

- 所有 Prompt 集中管理，便于统一优化
- 使用常量定义，避免硬编码字符串
- 支持多语言扩展（可在模板中添加语言参数）
