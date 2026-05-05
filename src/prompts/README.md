# Prompts 模块文档

## 概述

Prompts 模块集中管理所有 LLM 调用的 Prompt 模板，便于维护和优化。

## 文件结构

```
src/prompts/
├── agent_prompts.py      # 意图分析、查询扩写 Prompt
├── chat_prompts.py       # 情绪分析 Prompt
├── memory_prompts.py     # 记忆压缩 Prompt
├── response_prompts.py   # 回复生成 Prompt
├── scene_prompts.py      # 场景分类器、情绪状态分析 Prompt
├── state_prompts.py      # 人格和语气调整 Prompt
├── tool_prompts.py       # 工具调用决策 Prompt
└── __init__.py
```

---

## 1. Agent Prompts (agent_prompts.py)

| Prompt | 说明 |
|--------|------|
| `TASK_JUDGE_PROMPT` | 判断是否需要召回记忆和扩写查询 |
| `TASK_CONTEXT_BUILD_PROMPT` | 精炼历史、扩写查询、分析情绪 |

---

## 2. 对话 Prompts (chat_prompts.py)

| Prompt | 说明 |
|--------|------|
| `CHAT_EMOTION_PROMPT` | 分析用户输入的情绪 |

---

## 3. 记忆 Prompts (memory_prompts.py)

| Prompt | 说明 |
|--------|------|
| `MEMORY_COMPRESS_PROMPT` | 压缩对话历史 |

---

## 4. 回复 Prompts (response_prompts.py)

| Prompt | 说明 |
|--------|------|
| `RESPONSE_SYSTEM_PROMPT` | 生成自然、简洁、像真人一样的回复 |

---

## 5. 场景 Prompts (scene_prompts.py)

| Prompt | 说明 |
|--------|------|
| `CLASSIFIER_SYSTEM_PROMPT` | 场景分类器，判断记忆检索策略 |
| `EMOTION_STATE_SYSTEM_PROMPT` | 情绪状态分析 |

---

## 6. 状态 Prompts (state_prompts.py)

| Prompt | 说明 |
|--------|------|
| `PERSONA_ADJUSTMENT_PROMPT` | 根据情绪调整人格和语气 |

---

## 7. 工具 Prompts (tool_prompts.py)

| Prompt | 说明 |
|--------|------|
| `TOOL_DECISION_PROMPT` | 判断是否需要调用工具 |

---

## 设计原则

- 所有 Prompt 集中管理，便于统一优化
- 使用常量定义，避免硬编码字符串
- 支持通过 `__init__.py` 统一导入
