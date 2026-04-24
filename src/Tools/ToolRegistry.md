# ToolRegistry 工具箱文档

## 概述

`ToolRegistry` 是智能体系统的工具箱，提供工具的标准接口和注册机制，便于 Agent 动态加载和使用工具。

## 文件位置

```
src/Tools/tool.py
```

## 核心类

### Tool 基类

所有工具必须继承 `Tool` 类并实现以下接口：

```python
from abc import ABC, abstractmethod

class Tool(ABC):
    name: str = ""              # 工具名称（唯一标识）
    description: str = ""       # 工具描述
    
    @abstractmethod
    async def _run(self, **kwargs) -> str:
        """执行工具逻辑（子类必须实现）"""
        pass
```

**必须实现的属性**：
- `name`: 工具唯一标识
- `description`: 工具功能描述

**必须实现的方法**：
- `_run(**kwargs)`: 工具核心逻辑

### ToolRegistry 工具箱

```python
class ToolRegistry:
    _tools: Dict[str, Tool] = {}  # 工具存储（类变量）
```

**类方法**：

| 方法 | 参数 | 返回 | 说明 |
|------|------|------|------|
| `register(tool)` | `tool: Tool` | None | 注册工具 |
| `get_tool(name)` | `name: str` | `Optional[Tool]` | 获取指定工具 |
| `get_tools()` | None | `List[Dict[str, str]]` | 获取所有工具信息 |
| `execute(tool_name, **kwargs)` | `tool_name: str` | `str` | 执行指定工具 |

## 使用示例

### 1. 创建工具

```python
from src.Tools.tool import Tool
from src.Tools.web_search import WebSearchClient

class WebSearchTool(Tool):
    name = "web_search"
    description = "联网搜索工具，用于搜索互联网上的实时信息"
    
    async def _run(self, query: str, count: int = 10) -> str:
        client = WebSearchClient()
        result = client.search(query=query, count=count)
        results = result.get("results", [])
        return f"搜索结果：\n" + "\n".join([f"- {r.get('title', '')}: {r.get('snippet', '')}" for r in results])
```

### 2. 注册工具

```python
from src.Tools.tool import ToolRegistry
from src.Tools.tool_impl import WebSearchTool

# 创建工具实例
tool = WebSearchTool()

# 注册到工具箱
ToolRegistry.register(tool)
```

### 3. 执行工具

```python
# 通过工具箱执行
result = await ToolRegistry.execute("web_search", query="阿里云最新新闻", count=5)
print(result)
```

### 4. 获取工具列表

```python
tools_info = ToolRegistry.get_tools()
for tool in tools_info:
    print(f"工具名称：{tool['name']}, 描述：{tool['description']}")
```

## 已注册工具

| 工具名称 | 描述 | 参数 | 返回 |
|----------|------|------|------|
| `web_search` | 联网搜索 | `query`, `count` | 搜索结果列表 |
| `amap_weather` | 天气查询 | `city` | 天气信息 |
| `amap_geocode` | 地理编码 | `address`, `city` | 经纬度坐标 |
| `amap_search_poi` | POI 搜索 | `keywords`, `city` | POI 列表 |

## 添加新工具流程

1. 在 `src/Tools/` 目录创建工具客户端类
2. 继承 `Tool` 基类，实现 `_run` 方法
3. 注册到 `ToolRegistry`

## 相关文件

- [Tools.md](file:///d:/SmartAgent/src/Tools/Tools.md) - Tools 模块总文档
- [amap_tools.py](file:///d:/SmartAgent/src/Tools/amap_tools.py) - 高德地图工具
- [web_search.py](file:///d:/SmartAgent/src/Tools/web_search.py) - Web Search 工具
- [tool.py](file:///d:/SmartAgent/src/Tools/tool.py) - 工具基类和工具箱
