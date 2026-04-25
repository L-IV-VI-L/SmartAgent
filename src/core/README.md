# `core`

核心数据结构与回复生成模块。

## 主要职责

- 定义对话上下文 `Context`
- 将 persona、emotion、memory、tools 等信息组装成提示词
- 调用大模型生成最终回复

## 主要文件

- `context.py`：上下文容器与提示词构建
- `summarizeLMM.py`：回复生成模块
- `__init__.py`：核心对象导出

## 使用场景

`src/service.py` 会先创建 `Context`，再通过 `build_prompt()` 生成最终提示词交给回复模块。
