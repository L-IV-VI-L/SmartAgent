# Agents 模块文档

## 概述

Agents 模块是 SmartAgent 系统的核心，包含所有 Agent 实现以及工作流执行框架。

## 文件结构

```
src/agents/
├── base.py                  # Agent 基类
├── config.py                # Agent 配置常量
├── input_agents.py          # 输入处理 Agent
├── state_agents.py          # 状态管理 Agent
├── tool_agents.py           # 工具调用 Agent
├── response_agents.py       # 回复生成 Agent
├── memory_agents.py         # 记忆处理 Agent
├── scene_classifier.py      # 场景分类器
├── workflow_executor.py     # 工作流执行器
├── workflow_dependencies.py # 工作流依赖配置
└── __init__.py
```

---

## 1. Agent 基类 (base.py)

### 功能

定义所有 Agent 的统一接口。

### 核心类

**BaseAgent**
- `name: str` - Agent 名称
- `run(context: Context) -> Context` - 执行 Agent 逻辑，接收并返回 Context 对象

### 使用方式

所有 Agent 必须继承 BaseAgent 并实现 `run()` 方法。

---

## 2. 输入处理 Agent (input_agents.py)

### ContextBuildAgent

**功能**: 构建对话上下文，包括短期记忆检索和长期记忆召回。

**依赖**:
- `query_expander: QueryExpander` - 查询扩展器
- `memory_retriever: MemoryRetriever` - 记忆检索器
- `retrieval_strategy: RetrievalStrategy` - 检索策略（可选）

**执行流程**:
1. 调用 `QueryExpander.unified_judge()` 判断是否需要长期记忆
2. 调用 `MemoryRetriever.search_short_memories()` 检索短期记忆
3. 调用 `MemoryRetriever.search_long_memories()` 检索长期记忆（如需要）

---

### EmotionAndStateSeedAgent

**功能**: 分析用户情绪并生成当前状态种子数据。

**依赖**:
- `emotion_analyzer: EmotionAnalyzer` - 情绪分析器
- `format_history_text: Callable` - 历史记录格式化函数

**执行流程**:
1. 格式化短期历史记忆
2. 调用 `EmotionAnalyzer.analyze()` 分析情绪
3. 将情绪数据写入 Context

---

### MainlineMemoryAgent

**功能**: 管理主线摘要记忆，包括生成、更新和压缩。

**依赖**:
- `mainline_memory_updater: MainlineMemoryUpdater` - 主线记忆更新器
- `memory_compressor: MemoryCompressor` - 记忆压缩器

**执行流程**:
1. 调用 `MainlineMemoryUpdater.update_mainline_memory()` 更新主线摘要
2. 如需压缩，调用 `MemoryCompressor.compress()` 压缩历史记忆

---

## 3. 状态管理 Agent (state_agents.py)

### StateAdjustAgent

**功能**: 根据当前情绪、用户画像和对话场景调整人格参数。

**依赖**: 无外部依赖，直接操作数据库。

**执行流程**:
1. 从 MongoDB 读取用户当前人格配置
2. 根据情绪和输入判断是否需要调整人格
3. 写入调整后的新人格到 MongoDB

---

## 4. 工具调用 Agent (tool_agents.py)

### ToolPlanAgent

**功能**: 判断是否需要调用工具，并选择对应的工具。

**依赖**: 无外部依赖，使用内置 LLM 客户端。

**执行流程**:
1. 将可用工具注册到 `ToolRegistry`
2. 调用 LLM 判断是否需要工具
3. 如需要，返回工具名称和参数

---

### ToolExecuteAgent

**功能**: 执行 ToolPlanAgent 决策的工具调用。

**依赖**: `ToolRegistry`（全局单例）

**执行流程**:
1. 从 Context 读取工具决策
2. 调用 `ToolRegistry.execute_sync()` 执行工具
3. 将结果写入 Context 的 `tools["results"]`

**已实现的工具**:
- `weather_query` - 天气查询（高德天气 API）
- `web_search` - 互联网搜索
- `poi_search` - POI 地点搜索

---

## 5. 回复生成 Agent (response_agents.py)

### ResponseAgent

**功能**: 生成最终的 AI 回复。

**依赖**: 无外部依赖，使用内置 LLM 客户端。

**执行流程**:
1. 构建完整的对话上下文（历史记忆、工具结果等）
2. 调用 LLM 生成回复
3. 将回复写入 `Context.response_text`
4. 将短期记忆存入 Redis

---

## 6. 记忆处理 Agent (memory_agents.py)

### LongMemoryExtractAgent

**功能**: 从当前对话中提取长期记忆。

**依赖**: 无外部依赖，使用内置 LLM 客户端。

**执行流程**:
1. 调用 LLM 从对话中提取关键信息
2. 返回提取的记忆数据

---

## 7. 场景分类器 (scene_classifier.py)

**功能**: 根据用户输入自动判断场景类型，返回对应的检索策略。

**模型配置**:
- 模型: `deepseek-v4-flash`
- API Key: `SmartAgentDeepseekAPI` 环境变量
- Base URL: `https://api.deepseek.com`

**返回策略**:
- `STANDARD_STRATEGY` - 标准对话场景
- `TASK_STRATEGY` - 任务规划场景
- `EMOTION_STRATEGY` - 情感陪伴场景
- `KNOWLEDGE_STRATEGY` - 知识问答场景

**降级策略**:
- API 调用失败 → 返回 `STANDARD_STRATEGY`
- JSON 解析失败 → 返回 `STANDARD_STRATEGY`
- 未知策略名 → 返回 `STANDARD_STRATEGY`

---

## 8. 工作流执行器 (workflow_executor.py)

**功能**: 统一管理四大工作流的执行流程。

**工作流配置**:

| 工作流 | Agent 序列 |
|--------|-----------|
| standard | context_build → emotion_state_seed → state_adjust → tool_plan → tool_execute → response → mainline_memory |
| task | 同 standard |
| emotion | context_build → emotion_state_seed → state_adjust → response → long_memory_extract |
| knowledge | context_build → emotion_state_seed → tool_plan → tool_execute → response → long_memory_extract |

**核心方法**:
- `execute(context: Context) -> Context` - 执行完整工作流
- `_create_agent(agent_name, strategy)` - 根据策略动态创建 Agent

**策略传递**:
- `ContextBuildAgent` 会接收场景分类器返回的 `RetrievalStrategy`

---

## 9. 工作流依赖配置 (workflow_dependencies.py)

**功能**: 统一管理并初始化工作流所需的所有依赖组件。

**管理的依赖**:
- `main_llm_client` - 主 LLM 客户端
- `conversation_repo` - 会话仓库
- `memory_repo` - 记忆仓库
- `query_expander` - 查询扩展器
- `memory_retriever` - 记忆检索器
- `emotion_analyzer` - 情绪分析器
- `mainline_memory_updater` - 主线记忆更新器
- `memory_compressor` - 记忆压缩器

**设计模式**: 延迟初始化（Lazy Initialization），只在首次访问时创建实例。

---

## 模块间关系图

```
SmartAgentAPI (main.py)
  │
  ├── WorkflowExecutor
  │     │
  │     ├── WorkflowDependencies
  │     │     ├── QueryExpander
  │     │     ├── MemoryRetriever
  │     │     ├── EmotionAnalyzer
  │     │     ├── MainlineMemoryUpdater
  │     │     └── MemoryCompressor
  │     │
  │     ├── SceneClassifier (DeepSeek)
  │     │
  │     └── Agent 序列
  │           ├── ContextBuildAgent
  │           ├── EmotionAndStateSeedAgent
  │           ├── StateAdjustAgent
  │           ├── ToolPlanAgent
  │           ├── ToolExecuteAgent → ToolRegistry
  │           ├── ResponseAgent
  │           ├── MainlineMemoryAgent
  │           └── LongMemoryExtractAgent
  │
  └── Context (数据流载体)
```
