"""
InputProcess 模块

输入处理模块，负责：
- 判断用户输入是否需要扩写
- 召回短期记忆（Redis）或长期记忆（Milvus）
- 对问题进行扩写
- 将扩写结果和召回记忆写入 Context
"""

from .InputLMM import InputProcessModule, process_input

__all__ = ["InputProcessModule", "process_input"]
