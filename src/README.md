# `src`

SmartAgent 的核心源码目录。

## 模块结构

- `api/`：FastAPI 服务入口，提供 RESTful 对话接口
- `agents/`：核心工作流层，按输入、状态、工具、回复、记忆等 Agent 拆分职责
- `core/`：`Context` 上下文对象，工作流数据传递载体
- `InputProcess/`：输入处理组件，包括查询扩展、情绪分析、记忆检索与压缩等
- `Tools/`：LLM 客户端、工具注册机制与外部 API 封装
- `database/`：Redis、MongoDB、Milvus 客户端、记忆衰减与统一仓储层
- `prompts/`：按职责划分的 Prompt 模板集中管理
- `utils/`：通用工具函数，包括 JSON 解析和日志配置

## 当前运行链路

1. 初始化 `Context`
2. `SceneClassifier` 判断场景类型，选择对应检索策略
3. `ContextBuildAgent` 构建上下文，拉取短期/长期记忆
4. `EmotionAndStateSeedAgent` 补充情绪信息
5. `MainlineMemoryAgent` 更新主线摘要与压缩记忆
6. `StateAdjustAgent` 根据情绪和历史调整人格、语气状态
7. `ToolPlanAgent` / `ToolExecuteAgent` 处理工具规划与调用
8. `ResponseAgent` 生成最终回复并写入记忆存储

## 启动方式

```bash
# API 服务
python -m src.run_server

# 或直接使用 uvicorn
uvicorn src.api.app:app --reload --host 0.0.0.0 --port 8000
```
