# `src`

SmartAgent 的核心源码目录。

## 模块结构

- `main.py`：命令行入口
- `service.py`：对话流程编排服务
- `core/`：上下文与回复生成核心逻辑
- `InputProcess/`：输入扩写、记忆召回与输入预处理
- `StateToolsProcess/`：状态工具处理
- `Tools/`：大模型客户端与通用工具
- `database/`：数据库与记忆存储相关组件

## 运行流程概览

1. `main.py` 解析命令行参数
2. `service.py` 创建上下文并串联各处理模块
3. `InputProcess` 处理输入、召回记忆
4. `StateToolsProcess` 补充状态信息
5. `core/summarizeLMM.py` 生成最终回复
6. `database/` 负责持久化短期与长期记忆
