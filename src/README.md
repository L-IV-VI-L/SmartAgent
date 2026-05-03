# `src`

SmartAgent 的核心源码目录。

## 模块结构

- `agents/`：新的核心工作流层，按输入、状态、工具、回复四类 Agent 拆分职责
- `core/`：`Context` 对象与最终 Prompt 构建逻辑
- `InputProcess/`：输入处理基础组件，包括扩写、情绪分析、记忆召回、主线记忆维护与压缩
- `Tools/`：大模型客户端、互联网/地图工具封装与工具注册机制
- `database/`：Redis、MongoDB、Milvus 客户端与统一仓储层
- `prompts/`：按场景划分的 Prompt 模板

## 当前运行链路概览

1. 初始化 `Context`
2. `ContextBuildAgent` 判断是否需要召回、扩写，并拉取短期/长期记忆
3. `EmotionAndStateSeedAgent` 补充情绪信息
4. `MainlineMemoryAgent` 更新主线摘要与压缩记忆
5. `StateAdjustAgent` 根据情绪和历史调整人格、语气状态
6. `ToolPlanAgent` / `ToolExecuteAgent` 处理工具规划与调用
7. `ResponseAgent` 生成最终回复并写入记忆存储

## 迁移说明

旧版以 `main.py`、`service.py`、`InputLMM.py`、`StateToolsLMM.py`、`summarizeLMM.py` 为核心的流程式结构已完成清理。
当前源码应以 `agents/ + core/ + database/ + prompts/` 的协作模式理解和维护。
