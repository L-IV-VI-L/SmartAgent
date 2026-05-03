# SmartAgent 项目计划

## 项目概述

基于中颗粒度 Agent 架构，通过场景分类 + 配置化 Agent 编排实现场景化工作流的智能对话系统。最终交付形态为 REST API 服务。

**更新日期**: 2026-05-02

**当前进度**: 第一阶段已完成，第二阶段进行中。

---

## 架构概览

```
用户输入
  │
  ▼
SmartAgentAPI (统一入口点) ← 未来 FastAPI 路由
  │
  ▼
WorkflowExecutor
  │
  ├── 场景分类器 (DeepSeek-v4-flash)
  │     └── 返回 RetrievalStrategy
  │
  ▼
工作流执行
  │
  ├── standard: ContextBuildAgent → EmotionAndStateSeedAgent → StateAdjustAgent → ToolPlanAgent → ToolExecuteAgent → ResponseAgent → MainlineMemoryAgent
  ├── task: 同 standard
  ├── emotion: ContextBuildAgent → EmotionAndStateSeedAgent → StateAdjustAgent → ResponseAgent → LongMemoryExtractAgent
  └── knowledge: ContextBuildAgent → EmotionAndStateSeedAgent → ToolPlanAgent → ToolExecuteAgent → ResponseAgent → LongMemoryExtractAgent
```

---

## 已完成模块

| 模块 | 状态 | 文件 | 说明 |
|------|------|------|------|
| 场景分类器 | ✅ | [scene_classifier.py](file:///d:/SmartAgent/src/agents/scene_classifier.py) | 基于 DeepSeek-v4-flash，4种场景分类 |
| 工作流执行器 | ✅ | [workflow_executor.py](file:///d:/SmartAgent/src/agents/workflow_executor.py) | 4个工作流，Agent工厂模式 |
| 依赖配置管理 | ✅ | [workflow_dependencies.py](file:///d:/SmartAgent/src/agents/workflow_dependencies.py) | 统一初始化所有依赖组件 |
| 检索策略 | ✅ | [retrieval_strategies.py](file:///d:/SmartAgent/src/InputProcess/retrieval_strategies.py) | STANDARD/TASK/EMOTION/KNOWLEDGE |
| Agent 体系 | ✅ | 8个Agent | 全部实现并验证 |
| 数据库层 | ✅ | Milvus/MongoDB/Redis | Factory 模式 |
| 工具系统 | ✅ | amap/web_search | 工具注册/执行 |
| Milvus集合 | ✅ | [init_milvus.py](file:///d:/SmartAgent/scripts/init_milvus.py) | 已重建，schema正确（vector dim=1024） |
| 统一入口点 | ✅ | [main.py](file:///d:/SmartAgent/src/main.py) | API Ready，支持异步调用 |
| 异步工具执行 | ✅ | [tool.py](file:///d:/SmartAgent/src/Tools/tool.py) | 修复 asyncio.run() 冲突 |
| 天气查询工具 | ✅ | [amap_tools.py](file:///d:/SmartAgent/src/Tools/amap_tools.py) | 支持城市名自动转换adcode |

---

## 当前状态

- ✅ **核心组件已实现并测试通过**
- ✅ **Milvus 集合已修复**（旧集合已删除重建）
- ✅ **统一入口点已创建**（SmartAgentAPI）
- ✅ **DeepSeek API 已配置并正常工作**
- ✅ **工具执行异步冲突已修复**
- ✅ **天气查询工具已优化**（支持城市名）
- 🔴 **Milvus 不可用降级策略未实现**
- 🟡 **无 FastAPI 服务层**

---

## 已完成阶段

### ✅ 阶段1：统一入口点

**状态**: 已完成

#### 任务 1.1：SmartAgentAPI 类
- **文件**: [src/main.py](file:///d:/SmartAgent/src/main.py)
- **核心接口**:
  ```python
  class SmartAgentAPI:
      async def process_message(user_id, message, session_id) -> Dict
  ```
- **设计原则**:
  - 无状态（每次请求独立）
  - 明确的输入/输出格式
  - 完整的异常处理（转换为 HTTP 状态码）
  - 异步支持（为 FastAPI 预留）

#### 任务 1.2：异步支持
- **文件**: [src/Tools/tool.py](file:///d:/SmartAgent/src/Tools/tool.py)
- **内容**: 添加 `execute_sync()` 方法，解决 `asyncio.run()` 在事件循环中调用的冲突

#### 验收标准
- [x] 可通过 `SmartAgentAPI().process_message()` 调用工作流 ✅
- [x] 4个工作流都能正确执行 ✅
- [x] 异常返回结构化错误信息 ✅
- [x] 支持 `async/await` ✅

---

## 下一步计划

### 🟡 阶段2：完整集成测试（明日任务）

**目标**：验证 4 个工作流都能通过统一入口点执行。

#### 任务 2.1：Milvus 写入/检索测试
- **目的**: 验证长期记忆能否正确写入 Milvus，向量检索是否返回正确结果
- **测试方法**:
  1. 通过 `SmartAgentAPI` 发送消息
  2. 检查 `ContextBuildAgent` 是否正确检索 Milvus
  3. 检查 `MainlineMemoryAgent` 是否正确写入 Milvus

**引用路径**:
- 写入: [milvus_client.py:60-88](file:///d:/SmartAgent/src/database/milvus_client.py#L60-L88) `MilvusVectorStore.upsert()`
- 检索: [milvus_client.py:144-180](file:///d:/SmartAgent/src/database/milvus_client.py#L144-L180) `MilvusVectorStore.search()`

**字段匹配注意事项**:
- Milvus 集合 schema 必须包含以下字段：
  - `id` (INT64, 主键, 自动递增)
  - `doc_id` (VARCHAR, max_length=64)
  - `user_id` (VARCHAR, max_length=64)
  - `text` (VARCHAR, max_length=65535)
  - `content` (VARCHAR, max_length=65535)
  - `vector` (FLOAT_VECTOR, dim=1024) ← **必须与 DashScope text-embedding-v3 的维度匹配**
  - `weight` (FLOAT)
  - `create_time` (DOUBLE)
  - `update_time` (DOUBLE)
  - `metadata` (JSON)
- 向量维度：1024（DashScope text-embedding-v3 模型的输出维度）
- 集合名称：`long_term_memory`

#### 任务 2.2：工作流执行测试
- **目的**: 验证 4 个工作流都能通过 `SmartAgentAPI` 正确执行

| 工作流 | 测试输入示例 | 预期场景 |
|--------|-------------|---------|
| standard | "你好" | 标准对话场景 |
| task | "周末去哪玩" | 任务规划场景 |
| emotion | "今天心情不好" | 情感陪伴场景 |
| knowledge | "什么是量子计算" | 知识问答场景 |

**验证点**:
1. 场景分类器正确返回对应的 `RetrievalStrategy`
2. 工作流执行器选择正确的工作流
3. Agent 序列按顺序执行
4. 最终返回完整的响应

**引用路径**:
- 场景分类: [scene_classifier.py:52-64](file:///d:/SmartAgent/src/agents/scene_classifier.py#L52-L64) `SceneClassifier.classify()`
- 工作流执行: [workflow_executor.py:115-145](file:///d:/SmartAgent/src/agents/workflow_executor.py#L115-L145) `WorkflowExecutor.execute()`
- 策略传递: [workflow_executor.py:147-168](file:///d:/SmartAgent/src/agents/workflow_executor.py#L147-L168) `WorkflowExecutor._create_agent()`

#### 任务 2.3：降级策略测试
- **目的**: 验证 Milvus 不可用时只使用短期记忆

**测试方法**:
1. 停止 Milvus 服务
2. 发送消息
3. 验证系统不会崩溃，而是跳过长期记忆检索
4. 验证日志中记录降级行为

**引用路径**:
- ContextBuildAgent: [input_agents.py:35-49](file:///d:/SmartAgent/src/agents/input_agents.py#L35-L49)
- MemoryRetriever: [memory_retriever.py:91-119](file:///d:/SmartAgent/src/InputProcess/memory_retriever.py#L91-L119)

**注意事项**:
- `ContextBuildAgent` 的 `run()` 方法中已有 `try/except` 捕获异常
- 但需要在 `MemoryRetriever.search_long_memories()` 中添加 `try/except` 来捕获 Milvus 异常

#### 验收标准
- [ ] Milvus 写入/检索正常
- [ ] 4个工作流通过入口点执行成功
- [ ] 降级策略生效

---

### 🟢 阶段3：API 服务层（后续）

**目标**：提供 FastAPI REST API 服务。

#### 任务 3.1：创建 FastAPI 应用
- **文件**: `src/api/server.py`
- **接口**:
  - `POST /api/chat` - 对话接口
  - `GET /api/health` - 健康检查

#### 任务 3.2：请求/响应模型
- **文件**: `src/api/models.py`
- **内容**:
  - `ChatRequest` - 请求模型
  - `ChatResponse` - 响应模型

#### 验收标准
- [ ] FastAPI 服务可启动
- [ ] `/api/chat` 接口可正常调用
- [ ] 错误返回正确 HTTP 状态码

---

## 技术栈

| 组件 | 技术 |
|------|------|
| LLM | DashScope (通义千问) / DeepSeek |
| 向量数据库 | Milvus |
| 文档数据库 | MongoDB |
| 缓存/会话 | Redis |
| 向量检索 | DashScope text-embedding-v3 |
| Web 框架 | FastAPI (计划) |
| 异步 | asyncio |

---

## 环境变量

| 变量 | 说明 | 必需 | 当前状态 |
|------|------|------|---------|
| `DASHSCOPE_API_KEY` | 主 LLM API Key（通义千问） | ✅ | 已配置 |
| `SmartAgentDeepseekAPI` | 场景分类器 API Key（DeepSeek） | ✅ | 已配置 |
| `AMAP_MAPS_API_KEY` | 高德地图 API Key（Web服务类型） | ✅ | 已配置 |
| `MILVUS_URI` | Milvus 连接地址 | ✅ | 已配置 |
| `MONGO_URI` | MongoDB 连接地址 | ✅ | 已配置 |
| `REDIS_URI` | Redis 连接地址 | ✅ | 已配置 |

**注意事项**:
- `AMAP_MAPS_API_KEY` 必须是 **Web 服务** 类型的 Key，不能使用 Web 端 (JS API) 类型的 Key
- `SmartAgentDeepseekAPI` 是系统环境变量，通过 `[System.Environment]::GetEnvironmentVariable("SmartAgentDeepseekAPI", "Machine")` 读取
- 修改系统环境变量后需要重启终端或手动重新加载

---

## 决策记录

### 2026-05-02: 使用 DeepSeek-v4-flash 作为场景分类器

**决策**: 选择 `deepseek-v4-flash` 模型用于场景分类
**原因**: 成本低、速度快、支持 OpenAI 兼容格式
**配置**: 
- 环境变量: `SmartAgentDeepseekAPI`
- Base URL: `https://api.deepseek.com`

### 2026-05-02: 测试数据无需迁移

**决策**: Milvus 旧集合直接删除重建
**原因**: 所有数据均为测试数据，无迁移必要
**影响**: 旧集合数据丢失

### 2026-05-02: 工具执行异步冲突修复

**问题**: `ToolExecuteAgent` 内部使用 `asyncio.run()` 执行工具，但 `SmartAgentAPI.process_message()` 已经在一个事件循环中运行
**修复方案**: 在 `ToolRegistry` 中添加 `execute_sync()` 方法，检测是否在事件循环中，如果是则创建新线程执行异步调用

---

## 测试记录

### 2026-05-02: 单元测试

| 测试项 | 状态 |
|--------|------|
| SceneClassifier 分类功能 | ✅ |
| WorkflowExecutor 工作流识别 | ✅ |
| Agent 依赖注入 | ✅ |
| 降级策略 | ✅ |

### 2026-05-02: Milvus 集合

| 检查项 | 状态 |
|--------|------|
| 集合创建 | ✅ |
| vector 字段 (dim=1024) | ✅ |
| 索引 (IVF_FLAT, COSINE) | ✅ |

### 2026-05-02: DeepSeek API

| 测试项 | 状态 |
|--------|------|
| 环境变量读取 | ✅ |
| API 连接 | ✅ |
| 场景分类（standard） | ✅ |
| 场景分类（emotion） | ✅ |
| 场景分类（knowledge） | ✅ |
| 完整工作流执行 | ✅ |

### 2026-05-02: 工具测试

| 测试项 | 状态 | 说明 |
|--------|------|------|
| 天气查询（adcode） | ✅ | 城市 adcode 查询成功 |
| 天气查询（城市名） | ✅ | 自动转换城市名为 adcode |
| 网络搜索 | ✅ | 搜索成功，返回最新信息 |

---

## 已知问题

| 问题 | 状态 | 说明 |
|------|------|------|
| Milvus 不可用降级策略 | 🔴 未实现 | 需要在 `MemoryRetriever.search_long_memories()` 中添加 `try/except` |
| 场景分类器"周末去哪玩"分类为 standard | ⚠️ 优化中 | 当前分类为 standard，预期为 task |
