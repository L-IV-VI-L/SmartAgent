from __future__ import annotations

from abc import ABC, abstractmethod

from ..core.context import Context


class BaseAgent(ABC):
    """工作流中 Agent 基类。
    
    职责：
    1. 定义 Agent 的基本属性，如名称和是否使用 LLM
    2. 声明一个抽象方法 ``run``，用于在工作流中执行 Agent 的具体任务
    """

    name: str = "base_agent"
    uses_llm: bool = False

    @abstractmethod
    def run(self, context: Context) -> Context:
        raise NotImplementedError
