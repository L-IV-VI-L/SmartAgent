"""
Core 模块

核心数据结构与处理：
- Context: 对话上下文容器
- SummarizeModule: 基于上下文生成回复

注意：这里避免导入 `summarizeLMM`，因为它会间接加载大量第三方依赖。
在依赖未完全安装或损坏时，单独导入 `Context` 也应该能够正常工作。
"""

from .context import Context

__all__ = [
    'Context',
]
