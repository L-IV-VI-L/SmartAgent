# Core 模块文档

## 概述

Core 模块定义 SmartAgent 系统的核心数据结构和上下文对象。

## 文件结构

```
src/core/
├── context.py      # Context 上下文对象
└── __init__.py
```

---

## 1. Context 上下文对象 (context.py)

### Context

**功能**: 贯穿整个工作流的数据容器，携带用户输入和所有中间处理结果。

### 核心属性

| 属性 | 类型 | 说明 |
|------|------|------|
| `user_id` | str | 用户唯一标识 |
| `session_id` | str | 会话 ID |
| `raw_input` | str | 用户原始输入 |
| `user_input` | str | 处理后的用户输入 |
| `response_text` | str | AI 回复内容 |
| `current_emotion` | dict | 当前情绪分析结果 |
| `user_state` | str | 用户当前状态 |
| `persona` | dict | 用户人格配置 |
| `custom_persona` | str | 自定义人格 |
| `short_history` | list | 短期历史记忆 |
| `long_memories` | list | 长期记忆 |
| `memory_compression` | str | 记忆压缩结果 |
| `memory_compress_switch` | bool | 记忆压缩开关 |
| `tools` | dict | 工具调用结果 |

### 使用方式

Context 对象在工作流中依次传递给各个 Agent：

```python
context = Context(user_id="123")
context.raw_input = "你好"

# 工作流执行
context = context_build_agent.run(context)
context = emotion_agent.run(context)
# ... 更多 Agent

# 最终获取回复
print(context.response_text)
```

### 设计原则

- Context 是**不可变引用**，每个 Agent 返回新的 Context 实例
- 所有状态通过属性传递，不依赖全局变量
- 支持任意扩展属性（通过 `__dict__`）
