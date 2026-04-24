"""
工具基类与工具箱

提供工具的标准接口和注册机制，便于 Agent 动态加载和使用工具。
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Callable
from pydantic import BaseModel, Field


class Tool(ABC):
    """
    工具基类
    
    所有工具必须继承此类，并实现 name、description 和 _run 方法。
    """
    
    name: str = ""
    description: str = ""
    
    @abstractmethod
    async def _run(self, **kwargs) -> str:
        """
        执行工具逻辑（子类必须实现）
        
        Args:
            **kwargs: 工具参数
        
        Returns:
            str: 工具执行结果
        """
        pass
    
    async def run(self, **kwargs) -> str:
        """
        执行工具（带参数校验的入口）
        
        Args:
            **kwargs: 工具参数
        
        Returns:
            str: 工具执行结果
        """
        return await self._run(**kwargs)
    
    def get_info(self) -> Dict[str, str]:
        """获取工具信息"""
        return {
            "name": self.name,
            "description": self.description,
        }


class ToolRegistry:
    """
    工具箱：管理所有工具的注册和调用
    """
    
    _tools: Dict[str, Tool] = {}
    
    @classmethod
    def register(cls, tool: Tool):
        """
        注册工具
        
        Args:
            tool: 工具实例
        """
        cls._tools[tool.name] = tool
    
    @classmethod
    def get_tool(cls, name: str) -> Optional[Tool]:
        """获取指定工具"""
        return cls._tools.get(name)
    
    @classmethod
    def get_tools(cls) -> List[Dict[str, str]]:
        """获取所有工具信息"""
        return [tool.get_info() for tool in cls._tools.values()]
    
    @classmethod
    async def execute(cls, tool_name: str, **kwargs) -> str:
        """
        执行指定工具
        
        Args:
            tool_name: 工具名称
            **kwargs: 工具参数
        
        Returns:
            str: 工具执行结果
        
        Raises:
            ValueError: 工具不存在
        """
        tool = cls.get_tool(tool_name)
        if not tool:
            raise ValueError(f"未找到工具：{tool_name}")
        return await tool.run(**kwargs)
