# Utils 模块文档

## 概述

Utils 模块提供 SmartAgent 系统的通用工具函数，包括 JSON 解析、日志配置等。

## 文件结构

```
src/utils/
├── json_utils.py     # JSON 解析工具
├── logger.py         # 日志配置
└── __init__.py
```

---

## 1. JSON 解析工具 (json_utils.py)

### 核心函数

| 函数 | 说明 |
|------|------|
| `extract_json_from_text(text)` | 从文本中提取 JSON |
| `parse_json_response(response)` | 解析 LLM 返回的 JSON 响应 |

### 使用场景

- 场景分类器解析 LLM 返回的分类结果
- 情绪分析器解析 LLM 返回的情绪数据
- 工具调用决策解析

---

## 2. 日志配置 (logger.py)

### 核心函数

| 函数 | 说明 |
|------|------|
| `get_logger(name)` | 获取配置好的 Logger 实例 |

### 日志配置

- 日志级别: INFO（生产环境）/ DEBUG（开发环境）
- 日志格式: `时间 [级别] 模块名 - 消息`
- 日志输出: 控制台 + 文件

### 使用方式

```python
from src.utils.logger import get_logger

logger = get_logger(__name__)
logger.info("这是一条日志消息")
```
