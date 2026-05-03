# InputProcess 模块文档

## 概述

InputProcess 模块处理用户输入的预处理和记忆检索相关逻辑，包括查询扩展、情绪分析、记忆检索、主线摘要等。

## 文件结构

```
src/InputProcess/
├── common.py                    # 通用工具函数
├── emotion_analyzer.py          # 情绪分析器
├── long_memory_extractor.py     # 长期记忆提取器
├── mainline_memory.py           # 主线记忆管理
├── memory_compressor.py         # 记忆压缩器
├── memory_retriever.py          # 记忆检索器
├── memory_schema.py             # 记忆数据模型
├── query_expander.py            # 查询扩展器
├── retrieval_strategies.py      # 检索策略定义
└── __init__.py
```

---

## 1. 查询扩展器 (query_expander.py)

### QueryExpander

**功能**: 对用户输入进行查询扩展，包括任务判断、上下文构建等。

### 核心方法

| 方法 | 说明 |
|------|------|
| `unified_judge(query)` | 判断是否需要长期记忆检索 |
| `expand_query(query, context)` | 扩展查询以获取更好的检索结果 |

---

## 2. 记忆检索器 (memory_retriever.py)

### MemoryRetriever

**功能**: 统一的记忆检索接口，支持短期记忆和长期记忆检索。

### 依赖

- `conversation_repo: ConversationRepository` - 会话仓库
- `memory_repo: MemoryRepository` - 记忆仓库
- `decay_module_factory: Callable` - 衰减模块工厂

### 核心方法

| 方法 | 说明 |
|------|------|
| `search_short_memories(user_id, limit)` | 检索短期记忆（Redis） |
| `search_long_memories(user_id, query, top_k, memory_types)` | 检索长期记忆（Milvus） |

### 注意事项

- `search_long_memories()` 需要处理 Milvus 不可用的情况，应添加 `try/except` 来捕获异常

---

## 3. 情绪分析器 (emotion_analyzer.py)

### EmotionAnalyzer

**功能**: 分析用户输入的情绪，返回情绪标签和分数。

### 依赖

- `call_llm_json: Callable` - LLM JSON 解析函数
- `emotion_prompt: str` - 情绪分析 Prompt
- `emotion_labels: str` - 情绪标签列表

### 核心方法

| 方法 | 说明 |
|------|------|
| `analyze(text, history)` | 分析文本情绪 |

---

## 4. 记忆压缩器 (memory_compressor.py)

### MemoryCompressor

**功能**: 压缩对话历史，减少上下文长度。

### 依赖

- `llm_client: BaseLLMClient` - LLM 客户端
- `count_tokens: Callable` - Token 计数函数
- `format_history_text: Callable` - 历史格式化函数

### 核心方法

| 方法 | 说明 |
|------|------|
| `compress(history, limit)` | 压缩历史到指定长度 |

---

## 5. 主线记忆管理 (mainline_memory.py)

### MainlineMemoryUpdater

**功能**: 管理用户的主线摘要记忆，记录长期对话要点。

### 核心方法

| 方法 | 说明 |
|------|------|
| `update_mainline_memory(user_id, context)` | 更新主线摘要 |

---

## 6. 长期记忆提取器 (long_memory_extractor.py)

### 功能

从当前对话中提取关键信息作为长期记忆存储。

---

## 7. 记忆数据模型 (memory_schema.py)

### 功能

定义记忆的数据模型和类型。

---

## 8. 检索策略 (retrieval_strategies.py)

### 功能

定义不同场景的记忆检索策略。

### 预定义策略

| 策略 | 记忆类型 | Top K | 说明 |
|------|---------|-------|------|
| `STANDARD_STRATEGY` | None（全类型） | 3 | 标准对话场景 |
| `TASK_STRATEGY` | plan, fact | 5 | 任务规划场景 |
| `EMOTION_STRATEGY` | emotion, relationship | 5 | 情感陪伴场景 |
| `KNOWLEDGE_STRATEGY` | fact | 3 | 知识问答场景 |

### RetrievalStrategy 类

| 属性 | 类型 | 说明 |
|------|------|------|
| `memory_types` | Optional[List[str]] | 要检索的记忆类型 |
| `top_k` | int | 检索数量 |
| `context_build_strategy` | str | 上下文构建策略 |

---

## 模块间关系图

```
ContextBuildAgent
  ├── QueryExpander
  │     └── unified_judge() → 判断是否需要长期记忆
  │
  └── MemoryRetriever
        ├── search_short_memories() → Redis
        └── search_long_memories() → Milvus

EmotionAndStateSeedAgent
  └── EmotionAnalyzer
        └── analyze() → 情绪分析

MainlineMemoryAgent
  ├── MainlineMemoryUpdater
  │     └── update_mainline_memory()
  └── MemoryCompressor
        └── compress() → 压缩历史
```
