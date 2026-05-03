# Tools 模块文档

## 概述

Tools 模块提供 SmartAgent 系统的工具调用框架和第三方 API 封装，包括 LLM 客户端、天气查询、网络搜索等。

## 文件结构

```
src/Tools/
├── BaseLLM.py           # LLM 客户端基类
├── tool.py              # 工具注册表和工具基类
├── amap_tools.py        # 高德地图工具（天气/POI）
├── web_search.py        # 网络搜索工具
├── common_tools.py      # 通用工具
├── utils_config.py      # 工具相关配置
└── README.md            # 工具说明（本文档）
```

---

## 环境变量

| 变量 | 说明 | 使用模块 |
|------|------|---------|
| `DASHSCOPE_API_KEY` | 主 LLM API Key（通义千问） | BaseLLM, WebSearch |
| `AMAP_MAPS_API_KEY` | 高德地图 API Key（Web服务类型） | AMapClient |

**注意**: `AMAP_MAPS_API_KEY` 必须是 **Web 服务** 类型，不能使用 Web 端 (JS API) 类型。

---

## 1. LLM 客户端 (BaseLLM.py)

### BaseLLMClient

**功能**: 统一的 LLM 调用客户端，支持 OpenAI 兼容格式的 API。

### 配置

| 参数 | 说明 | 环境变量 | 默认值 |
|------|------|---------|--------|
| `api_key` | API Key | `DASHSCOPE_API_KEY` | - |
| `model` | 模型名称 | - | `qwen-turbo` |
| `base_url` | API 地址 | - | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| `temperature` | 温度参数 | - | 0.7 |
| `max_tokens` | 最大 Token 数 | - | 8000 |

### 核心方法

| 方法 | 说明 |
|------|------|
| `chat_with_prompt(prompt, system_message)` | 调用 LLM 生成回复 |
| `count_tokens(text)` | 计算 Token 数量 |

### 注意事项

- `base_url` 参数支持自定义 API 地址，可用于 DeepSeek 等其他 LLM 提供商
- 场景分类器使用独立的 LLM 客户端实例（`deepseek-v4-flash`）

---

## 2. 工具注册表 (tool.py)

### Tool（基类）

所有工具必须继承 `Tool` 类并实现 `_run()` 方法。

```python
class MyTool(Tool):
    name = "my_tool"
    description = "工具描述"
    
    async def _run(self, **kwargs):
        # 实现工具逻辑
        return result
```

### ToolRegistry

**功能**: 全局工具注册和调用接口。

### 核心方法

| 方法 | 说明 |
|------|------|
| `register(tool)` | 注册工具 |
| `get_tool(name)` | 获取工具实例 |
| `get_tool_list()` | 获取所有工具列表 |
| `execute(tool_name, **kwargs)` | 异步执行工具 |
| `execute_sync(tool_name, **kwargs)` | 同步执行工具（支持在异步事件循环中调用） |

### 注意事项

- `execute_sync()` 方法用于解决 `asyncio.run()` 在事件循环中调用的冲突
- 内部实现：检测是否在事件循环中，如果是则创建新线程执行

---

## 3. 高德地图工具 (amap_tools.py)

### AMapClient

**功能**: 封装高德地图 Web 服务 API。

### 配置

| 参数 | 环境变量 | 说明 |
|------|---------|------|
| `api_key` | `AMAP_MAPS_API_KEY` | 高德地图 API Key |

**注意**: API Key 必须是 **Web 服务** 类型，不能使用 Web 端 (JS API) 类型。

### 核心方法

| 方法 | 说明 |
|------|------|
| `get_weather(city, extensions)` | 天气查询，支持城市名或 adcode |
| `get_city_adcode(city_name)` | 城市名转 adcode |
| `geocode(address, city)` | 地理编码 |
| `reverse_geocode(location)` | 逆地理编码 |
| `search_poi(keywords, city)` | POI 搜索 |
| `search_around(keywords, location)` | 周边搜索 |
| `calculate_distance(origin, destination)` | 路径规划 |
| `calculate_direction(origin, destination)` | 方向计算 |
| `get_city_info(city)` | 城市信息查询 |

### 天气查询说明

- `city` 参数支持城市名（如"北京"）或 adcode（如"110000"）
- 如果传入城市名，将自动通过 `get_city_adcode()` 转换为 adcode
- `extensions="base"` 返回实况天气，`"all"` 返回预报天气

---

## 4. 网络搜索工具 (web_search.py)

### WebSearchClient

**功能**: 封装网络搜索 API。

### 核心方法

| 方法 | 说明 |
|------|------|
| `search(query, count)` | 执行网络搜索 |

---

## 5. 通用工具 (common_tools.py)

### 功能

提供通用工具函数：

| 函数 | 说明 |
|------|------|
| `generate_uuid()` | 生成唯一 ID |
| `generate_task_id()` | 生成任务 ID |
| `get_current_timestamp()` | 获取当前时间戳 |
| `format_timestamp()` | 格式化时间戳 |
| `truncate_dict()` | 字典截断 |

---

## 6. 工具配置 (utils_config.py)

### 功能

提供工具和 Agent 使用的配置常量：

- `PersonaTagConfig` - 人格标签配置
- `ToneTagConfig` - 语气标签配置

---

## 7. 工具列表

| 工具名称 | 说明 | 核心参数 |
|---------|------|---------|
| `weather_query` | 天气查询 | `city`（城市名或adcode）, `extensions`（base/all） |
| `web_search` | 互联网搜索 | `query`（搜索词）, `count`（结果数量） |
| `poi_search` | POI 搜索 | `keywords`（关键词）, `city`（城市） |

---

## 工具调用流程

```
ToolPlanAgent
  └── ToolRegistry.register() → 注册工具
  └── LLM 决策 → 选择工具

ToolExecuteAgent
  └── ToolRegistry.execute_sync() → 执行工具
  └── 结果写入 Context.tools["results"]
```

---

## 添加新工具

### 步骤 1：创建工具客户端类

在 `src/Tools/` 目录下创建工具客户端文件，例如 `my_tool.py`：

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

继承 `Tool` 基类，实现 `_run()` 方法：

```python
from src.Tools.tool import Tool
from src.Tools.my_tool import MyToolClient

class MyTool(Tool):
    name = "my_tool"
    description = "这是一个示例工具"
    
    async def _run(self, param: str, **kwargs) -> str:
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

---

## 使用示例

### 创建工具

```python
from src.Tools.tool import Tool
from src.Tools.web_search import WebSearchClient

class WebSearchTool(Tool):
    name = "web_search"
    description = "联网搜索工具，用于搜索互联网上的实时信息"
    
    async def _run(self, query: str, count: int = 10, **kwargs) -> str:
        client = WebSearchClient()
        result = client.search(query=query, count=count)
        results = result.get("results", [])
        return f"搜索结果：\n" + "\n".join([f"- {r.get('title', '')}: {r.get('snippet', '')}" for r in results])
```

### 注册工具

```python
from src.Tools.tool import ToolRegistry
from src.Tools.my_tool import MyTool

# 创建工具实例
tool = MyTool()

# 注册到工具箱
ToolRegistry.register(tool)
```

### 执行工具

```python
# 异步执行
result = await ToolRegistry.execute("web_search", query="阿里云最新新闻", count=5)

# 同步执行（支持在异步事件循环中调用）
result = ToolRegistry.execute_sync("web_search", query="阿里云最新新闻", count=5)
```

### 获取工具列表

```python
tools_info = ToolRegistry.get_tool_list()
for tool in tools_info:
    print(f"工具名称：{tool['name']}, 描述：{tool['description']}")
```
