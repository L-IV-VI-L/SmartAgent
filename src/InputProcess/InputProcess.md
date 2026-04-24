# InputProcess 输入处理模块文档

## 概述

`InputProcess` 模块是智能体系统的输入处理核心模块，负责接收用户输入并进行智能化处理。该模块通过**双 Agent 架构**实现：
- **判断 Agent**：统一判断是否需要召回记忆 + 是否需要扩写
- **处理 Agent**：精炼记忆 + 扩写问题一次完成

通过召回历史记忆来增强对用户意图的理解，减少大模型幻觉。

## 文件位置

```
src/InputProcess/
├── __init__.py          # 模块导出
├── InputLMM.py          # 核心实现
└── InputProcess.md      # 本文档
```

## 依赖

- `Tools.BaseLLM.BaseLLMClient` - LLM 客户端
- `database.redis_client.RedisClient` - Redis 数据库客户端
- `database.milvus_client.MilvusClient` - Milvus 向量数据库客户端
- `core.context.Context` - 上下文对象
- `database.db_config` - 数据库配置
- `tiktoken` - Token 计算库

## 核心功能

### 1. 统一判断（判断 Agent）

同时判断两个维度，返回 `(need_recall: bool, need_expansion: bool)`：

- **规则预判断**：
  - 输入长度少于 5 个字 → 两者都需要
  - 输入长度超过 50 字且无关键词 → 两者都不需要
  - 包含召回关键词（上次、之前、说过等）→ 需要召回
  - 包含指代词（这个、那个、他等）且长度 <= 20 → 需要扩写

- **LLM 智能判断**：
  - JSON 格式返回判断结果
  - 上下文依赖强度分析
  - 意图明确程度分析

### 2. 记忆召回

采用两级召回策略：

1. **从 Redis 获取短期记忆**
   - 获取最近 5 轮对话
   - 包含 role（user/assistant）和 content

2. **从 Milvus 检索长期记忆**
   - 使用 LlamaIndex + DashScope text-embedding-v2 进行向量检索
   - 支持按 user_id 过滤
   - 返回包含相似度分数和记忆权重的结果
   - **权重重排机制**：
     - 综合评分 = 语义相似度 × 0.8 + 归一化权重 × 0.2
     - 权重范围：0~5，归一化后为 0~1
     - 检索时获取 top_k × 2 条记忆，重排后返回 top_k 条
     - 确保高权重记忆能够优先被召回
   - 默认返回 top 3 条记忆

### 3. 统一处理（处理 Agent）

精炼记忆 + 扩写问题一次 LLM 调用完成：

- **精炼对话历史**：
  - 保留事实性信息（用户偏好、需求、约束等）
  - 保留任务相关进度
  - 去除问候、感谢、闲聊等无实质内容
  - **保持原始角色信息（user/assistant）**

- **扩写用户问题**：
  - 补全省略的主语、宾语等成分
  - 明确指代词的具体所指
  - 保持原意不变
  - 使问题可独立理解

### 4. 记忆压缩

当 Token 超限时（> 120000），使用 LLM 将召回的多轮对话压缩成简洁摘要：

- 保留关键事实和信息
- 去除冗余和重复
- 100 字以内

## 架构设计

### 双 Agent 架构

```
┌─────────────────────────────────────────────────────┐
│                    process()                        │
├─────────────────────────────────────────────────────┤
│  1. 保存 raw_input 和 user_id                       │
│  2. 调用 _unified_judge() [判断 Agent]              │
│     └─ 返回 (need_recall, need_expansion)            │
│  3. if need_recall:                                 │
│     ├─ _get_redis_history()                         │
│     └─ _search_milvus_memories()                    │
│  4. if need_expansion and has_memories:             │
│     └─ _refine_and_expand() [处理 Agent]            │
│        ├─ 精炼短期记忆                               │
│        └─ 扩写用户问题                               │
│  5. if token 超限:                                  │
│     └─ _compress_memories()                         │
└─────────────────────────────────────────────────────┘
```

### LLM 调用次数优化

**优化前**（最多 4 次 LLM 调用）：
- `_llm_check_recall()` → 判断是否召回
- `_refine_short_history()` → 精炼记忆
- `_llm_check_expansion()` → 判断是否扩写
- `_expand_query()` → 扩写问题

**优化后**（最多 2 次 LLM 调用）：
- `_unified_judge()` → 同时判断召回 + 扩写
- `_refine_and_expand()` → 精炼记忆 + 扩写问题

## 主要类和函数

### InputProcessModule 类

核心处理类，提供完整的输入处理流程。

#### 初始化

```python
module = InputProcessModule()
```

#### process 方法

```python
def process(
    self,
    user_id: str,
    query: str,
    context: Context
) -> Context:
    """
    处理用户输入

    Args:
        user_id: 用户唯一标识
        query: 用户输入的问题
        context: Context 对象

    Returns:
        处理后的 Context 对象
    """
```

**处理流程**：

1. 保存原始输入到 `context.raw_input`
2. 保存 user_id 到 `context.user_id`
3. 判断 Agent：统一判断是否需要召回记忆 + 是否需要扩写
4. 如果需要召回 → 召回记忆（短期 + 长期）
5. 处理 Agent：精炼记忆 + 扩写问题（如有需要）
6. Token 超限检查 → 压缩记忆（如有需要）
7. 返回处理后的 Context

### process_input 函数

便捷函数，可直接调用。

```python
def process_input(
    user_id: str,
    query: str,
    context: Optional[Context] = None
) -> Context:
    """
    便捷的输入处理函数

    Args:
        user_id: 用户 ID
        query: 用户输入
        context: 现有的 Context 对象，如果为 None 则创建新的

    Returns:
        处理后的 Context 对象
    """
```

## 使用示例

### 示例 1：使用便捷函数

```python
from src.InputProcess import process_input
from src.core.context import Context

# 直接调用（自动创建 Context）
context = process_input(
    user_id="user_123",
    query="这个多少钱？"
)

print(f"原始输入：{context.raw_input}")
print(f"扩写后：{context.user_input}")
```

### 示例 2：使用类实例

```python
from src.InputProcess import InputProcessModule
from src.core.context import Context

# 创建 Context
context = Context(user_id="user_123")

# 创建模块实例
module = InputProcessModule()

# 处理输入
context = module.process(
    user_id="user_123",
    query="帮我推荐一家餐厅",
    context=context
)
```

### 示例 3：集成到主流程

```python
from src.InputProcess import process_input
from src.core.context import Context

def main():
    user_id = "user_456"
    query = "那个地方怎么样？"

    # 处理输入
    context = process_input(user_id, query)

    # 后续处理...
    # 1. CoreState 处理人格语气
    # 2. 调度器执行计划
    # 3. LLM 生成回复

    return context
```

## Context 写入说明

处理后的数据会写入 Context 的以下字段：

| 字段 | 说明 | 写入内容 |
|------|------|----------|
| `raw_input` | 原始输入 | 用户的原始问题 |
| `user_id` | 用户 ID | 用户唯一标识 |
| `user_input` | 扩写后的输入 | 扩写后的完整问题 |
| `memory["short_history"]` | 短期记忆 | 精炼后的对话历史或原始历史 |
| `memory["long_retrieved"]` | 长期记忆 | Milvus 检索的记忆 |
| `memory["compressed"]` | 压缩摘要 | Token 超限时记忆的压缩版本 |

## 内部方法

### _unified_judge(query: str) -> tuple[bool, bool]

**判断 Agent**：统一判断是否需要召回记忆 + 是否需要扩写

**返回**：
- `(need_recall: bool, need_expansion: bool)`

**特点**：
- 一次 LLM 调用同时完成两个判断
- JSON 格式返回结果
- 保留规则预判断作为快速路径

### _refine_and_expand(
    query: str,
    short_history: List[Dict],
    long_memories: List[Dict]
) -> tuple[str, Optional[List[Dict]]]

**处理 Agent**：精炼记忆 + 扩写问题一次完成

**返回**：
- `(expanded_query: str, refined_short_history: Optional[List[Dict]])`

**特点**：
- 一次 LLM 调用同时完成精炼和扩写
- JSON 格式返回结果
- 精炼后保留原始角色信息（user/assistant）

### _get_redis_history(user_id: str) -> List[Dict]

从 Redis 获取短期对话历史

### _search_milvus_memories(user_id: str, query: str, top_k: int) -> List[Dict]

从 Milvus 检索长期记忆

**实现细节**：
- 使用 LlamaIndex 集成 DashScope text-embedding-v2 模型
- 支持向量相似度检索
- 可通过 user_id 进行过滤
- 返回结果包含 score（相似度分数）和 weight（记忆权重 0~5）
- 检索 top_k × 2 条记忆，重排后返回 top_k 条
- 默认 top_k=3

### _calculate_composite_score(semantic_score: float, weight: float) -> float

计算综合评分

**公式**：
```
综合评分 = 语义相似度 × 0.8 + 归一化权重 × 0.2
```

**参数**：
- `semantic_score`: 语义相似度分数（0~1）
- `weight`: 记忆权重（0~5）
- `semantic_weight`: 语义分数权重，默认 0.8
- `memory_weight_ratio`: 记忆权重占比，默认 0.2

**返回**：
- 综合评分（0~1）

### _rerank_memories(memories: List[Dict]) -> List[Dict]

重排记忆列表

**功能**：
- 根据综合评分（语义相似度 + 权重）重新排序
- 为每条记忆添加 `composite_score` 字段
- 按综合评分降序排列

### _compress_memories(memories: List[Dict]) -> str

压缩记忆摘要

### _count_tokens(text: str) -> int

使用 tiktoken 计算 Token 数量

**特点**：
- 使用 `cl100k_base` 编码器
- 比简单估算更准确
- 保留降级方案

## 数据格式

### 精炼后的短期记忆格式

```json
[
  {"role": "user", "content": "我想去吃火锅"},
  {"role": "assistant", "content": "好啊，我知道一家不错的火锅店"}
]
```

**注意**：精炼后保持原始角色信息（user/assistant），与 `Context.build_prompt()` 格式兼容。

### Redis 记忆格式

```json
{
  "role": "user",
  "content": "今天天气真好",
  "time": 1775899942.123
}
```

### Milvus 记忆格式

```json
{
  "role": "memory",
  "content": "用户喜欢吃川菜",
  "score": 0.85,
  "weight": 3.5,
  "composite_score": 0.78,
  "create_time": 1775899942.123,
  "metadata": {
    "user_id": "user_123",
    "weight": 3.5,
    "create_time": 1775899942.123
  }
}
```

**字段说明**：
- `score`: 向量相似度分数（0~1）
- `weight`: 记忆权重（0~5），表示重要程度
- `composite_score`: 综合评分（0~1），用于重排
  - 计算公式：`score × 0.8 + (weight/5) × 0.2`
- `create_time`: 记忆创建时间戳
- `metadata`: 元数据信息

### 精炼 + 扩写示例

**输入**：
```
短期对话历史：
user: 我想去吃火锅
assistant: 好啊，我知道一家不错的火锅店

长期记忆：
用户喜欢吃川菜和火锅

用户当前问题：那个地方怎么样？
```

**Agent 返回**：
```json
{
  "refined_history": [
    {"role": "user", "content": "我想去吃火锅"},
    {"role": "assistant", "content": "好啊，我知道一家不错的火锅店"}
  ],
  "expanded_query": "那家火锅店怎么样？味道好吗？位置在哪里？"
}
```

## 注意事项

1. **双 Agent 架构**
   - `_unified_judge()` 统一判断召回和扩写需求
   - `_refine_and_expand()` 统一处理精炼和扩写
   - 减少 LLM 调用次数（从 4 次优化到 2 次）

2. **Milvus 检索已实现**
   - `_search_milvus_memories` 方法已完整实现
   - 使用 LlamaIndex + DashScope text-embedding-v2 进行向量检索
   - 支持按 user_id 过滤
   - **权重重排机制**：
     - 综合评分 = 语义相似度 × 0.8 + 归一化权重 × 0.2
     - 权重占比 20%，确保不会过度影响语义相似度排序
     - 检索时获取 top_k × 2 条记忆，重排后返回 top_k 条
     - 高权重记忆能够优先被召回，但不会完全改变语义排序

3. **Token 计算**
   - 使用 tiktoken 库进行准确计算
   - 超过 120000 token 时触发压缩

4. **Redis 连接异常处理**
   - Redis 获取失败时会自动降级，不影响主流程
   - 会打印错误日志

5. **LLM 调用失败降级**
   - 判断 Agent 失败时使用规则判断
   - 处理 Agent 失败时返回原始问题和原始历史

6. **精炼格式兼容**
   - 精炼后的记忆保持 `{"role": "...", "content": "..."}` 格式
   - 与 `Context.build_prompt()` 完全兼容

## 相关文件

- `src/core/context.py` - Context 上下文对象
- `src/core/context.md` - Context 文档
- `src/Tools/BaseLLM.py` - LLM 客户端
- `src/database/redis_client.py` - Redis 客户端
- `src/database/milvus_client.py` - Milvus 客户端
- `src/database/db_config.py` - 数据库配置

## 待实现功能

- [ ] 多轮对话的上下文窗口管理
- [ ] 记忆压缩的自定义长度配置
- [ ] 支持更多记忆元数据字段
