# Tools 工具模块文档

## 概述

`Tools` 模块提供智能体系统所需的各种外部工具和服务封装，包括：
- LLM 客户端（DashScope API）
- 高德地图工具（地理编码、天气、POI 搜索）
- Web Search MCP 工具（联网搜索）
- 通用工具函数（UUID、时间、字典操作等）

## 文件结构

```
src/Tools/
├── BaseLLM.py          # LLM 客户端
├── common_tools.py     # 通用工具函数
├── utils_config.py     # 工具配置文件
├── amap_tools.py       # 高德地图工具
├── web_search.py       # Web Search MCP 工具
├── tool.py             # 工具基类和工具箱
└── Tools.md            # 本文档
```

## 环境变量

| 环境变量 | 说明 | 使用模块 |
|----------|------|----------|
| `DASHSCOPE_API_KEY` | 阿里云百炼 API Key | BaseLLM, WebSearch |
| `AMAP_MAPS_API_KEY` | 高德地图 API Key | AMapClient |

## 核心模块

### 1. BaseLLM - LLM 客户端

**文件**：[BaseLLM.py](file:///d:/SmartAgent/src/Tools/BaseLLM.py)

**功能**：提供 DashScope 兼容的 OpenAI 格式 API 调用能力。

**使用示例**：
```python
from src.Tools.BaseLLM import BaseLLMClient

client = BaseLLMClient()
response = client.chat_with_prompt(
    prompt="你好",
    system_message="你是一个助手",
    model="qwen-plus",
    temperature=0.7
)
```

### 2. AMapTools - 高德地图工具

**文件**：[amap_tools.py](file:///d:/SmartAgent/src/Tools/amap_tools.py)

**功能**：
- `geocode()` - 地理编码（地址转经纬度）
- `reverse_geocode()` - 逆地理编码（经纬度转地址）
- `get_weather()` - 天气查询（实时/预报）
- `search_poi()` - POI 关键字搜索
- `search_poi_around()` - POI 周边搜索

**使用示例**：
```python
from src.Tools.amap_tools import AMapClient

client = AMapClient()
weather = client.get_weather(city="北京")
```

### 3. WebSearch - 联网搜索工具

**文件**：[web_search.py](file:///d:/SmartAgent/src/Tools/web_search.py)

**功能**：
- `search()` - Web 搜索
- `search_with_agent()` - 千问联网检索 Agent
- `quick_search()` - 快速搜索（返回摘要）

**使用示例**：
```python
from src.Tools.web_search import WebSearchClient

client = WebSearchClient()
results = client.search(query="阿里云最新新闻")
```

### 4. CommonTools - 通用工具函数

**文件**：[common_tools.py](file:///d:/SmartAgent/src/Tools/common_tools.py)

**功能**：
- `generate_uuid()` - 生成唯一 ID
- `generate_task_id()` - 生成任务 ID
- `get_current_timestamp()` - 获取当前时间戳
- `format_timestamp()` - 格式化时间戳
- `truncate_dict()` - 字典截断

### 5. UtilsConfig - 工具配置

**文件**：[utils_config.py](file:///d:/SmartAgent/src/Tools/utils_config.py)

**功能**：
- `PersonaTagConfig` - 人格标签配置
- `ToneTagConfig` - 语气标签配置

### 6. Tool 基类与工具箱

**文件**：[tool.py](file:///d:/SmartAgent/src/Tools/tool.py)

**功能**：
- `Tool` - 工具基类
- `ToolRegistry` - 工具箱（注册和管理所有工具）

详见 [ToolRegistry.md](file:///d:/SmartAgent/src/Tools/ToolRegistry.md)

## 添加新工具

### 步骤 1：创建工具文件

在 `src/Tools/` 目录下创建新的工具文件，例如 `my_tool.py`：

```python
import os

class MyToolClient:
    def __init__(self, api_key=None):
        self.api_key = api_key or os.getenv("MY_TOOL_API_KEY")
        if not self.api_key:
            raise ValueError("请设置环境变量 MY_TOOL_API_KEY")
    
    def do_something(self, param: str) -> dict:
        """实现工具逻辑"""
        pass
```

### 步骤 2：封装为 Tool

继承 `Tool` 基类，实现工具接口：

```python
from src.Tools.tool import Tool
from src.Tools.my_tool import MyToolClient

class MyTool(Tool):
    name = "my_tool"
    description = "这是一个示例工具"
    
    async def _run(self, param: str) -> str:
        client = MyToolClient()
        result = client.do_something(param)
        return str(result)
```

### 步骤 3：注册到工具箱

在工具初始化时注册：

```python
from src.Tools.tool import ToolRegistry
from src.Tools.my_tool import MyTool

tool = MyTool()
ToolRegistry.register(tool)
```

## 相关文件

- [InputProcess/InputProcess.md](file:///d:/SmartAgent/src/InputProcess/InputProcess.md) - 输入处理模块文档
- [core/context.md](file:///d:/SmartAgent/src/core/context.md) - Context 上下文模块文档
- [database/db_config.py](file:///d:/SmartAgent/src/database/db_config.py) - 数据库配置
