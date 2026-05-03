from __future__ import annotations

"""工具处理相关 Agent。"""

from typing import Any, Dict, Optional
import asyncio
import json

from ..Tools.BaseLLM import BaseLLMClient
from ..Tools.amap_tools import AMapClient
from ..Tools.tool import Tool, ToolRegistry
from ..Tools.web_search import WebSearchClient
from ..core.context import Context
from ..prompts import TOOL_DECISION_PROMPT
from ..utils.json_utils import parse_json_response, extract_json_from_text
from ..utils.logger import get_logger
from .base import BaseAgent

logger = get_logger(__name__)


class WeatherTool(Tool):
    """高德天气查询工具。"""

    name = "weather_query"
    description = "查询目标城市的实时天气或预报天气。city参数支持城市名称（如：北京、上海）或adcode（如：110000）"

    def __init__(self, amap_client: AMapClient):
        self._amap_client = amap_client

    async def _run(self, city: str, extensions: str = "base", **kwargs) -> str:
        result = self._amap_client.get_weather(city=city, extensions=extensions)
        return json.dumps(result, ensure_ascii=False)


class SearchTool(Tool):
    """互联网搜索工具。"""

    name = "web_search"
    description = "通过互联网搜索获取实时信息"

    async def _run(self, query: str, count: int = 5, **kwargs) -> str:
        client = WebSearchClient()
        result = client.search(query=query, count=count)
        return json.dumps(result, ensure_ascii=False)


class POISearchTool(Tool):
    """高德 POI 搜索工具。"""

    name = "poi_search"
    description = "搜索指定地点的 POI 信息（餐厅、景点等）"

    def __init__(self, amap_client: AMapClient):
        self._amap_client = amap_client

    async def _run(self, keywords: str, city: Optional[str] = None, **kwargs) -> str:
        result = self._amap_client.search_poi(keywords=keywords, city=city)
        return json.dumps(result, ensure_ascii=False)


_TOOLS_REGISTERED = False


def ensure_tools_registered() -> None:
    """确保默认工具已注册。"""
    global _TOOLS_REGISTERED
    if _TOOLS_REGISTERED:
        return

    try:
        amap_client = AMapClient()
        ToolRegistry.register(WeatherTool(amap_client))
        ToolRegistry.register(SearchTool())
        ToolRegistry.register(POISearchTool(amap_client))
        _TOOLS_REGISTERED = True
        logger.info("已注册 %d 个工具", len(ToolRegistry.get_tools()))
    except Exception as e:
        logger.error("工具注册失败: %s", e)


class ToolPlanAgent(BaseAgent):
    """工具规划 Agent：判断是否需要工具，并生成工具调用计划。
    
    职责：
    1. 从 ``Context`` 中提取用户输入
    2. 调用 ``ToolRegistry`` 获取所有已注册工具的信息
    3. 调用 ``BaseLLMClient`` 生成工具调用计划
    4. 将计划写入 ``Context`` 中
    """

    name = "tool_plan"
    uses_llm = True

    def __init__(self, llm_client: Optional[BaseLLMClient] = None):
        self.llm_client = llm_client or BaseLLMClient()

    def run(self, context: Context) -> Context:
        ensure_tools_registered()
        user_input = context.user_input or context.raw_input
        tools_info = self._get_tools_info()
        decision = self._decide_tool_call(user_input, tools_info)
        context.tools["decision"] = decision
        return context

    def _get_tools_info(self) -> str:
        tools = ToolRegistry.get_tools()
        if not tools:
            return "无可用工具"
        parts = [f"- {tool['name']}: {tool['description']}" for tool in tools]
        return "\n".join(parts)

    def _decide_tool_call(self, user_input: str, tools_info: str) -> Dict[str, Any]:
        system_prompt = TOOL_DECISION_PROMPT.format(
            tools_info=tools_info,
            user_input=user_input,
        )

        try:
            response = self.llm_client.chat_with_prompt(
                prompt=f"用户输入：{user_input}",
                system_message=system_prompt,
            )
            result = self._parse_json_response(response)
            if result:
                logger.info("工具决策：need_tool=%s, reason=%s", result.get('need_tool', False), result.get('reason', ''))
                return result
        except Exception as e:
            logger.error("LLM 工具决策失败: %s", e)

        return {"need_tool": False, "tool_name": "", "tool_params": {}, "reason": "决策失败，默认不调用"}

    def _parse_json_response(self, response: str) -> Optional[Dict[str, Any]]:
        return parse_json_response(response)


class ToolExecuteAgent(BaseAgent):
    """工具执行 Agent：执行工具并将结果写入 context.tools。
    
    职责：
    1. 从 ``Context`` 中提取工具调用计划
    2. 调用 ``ToolRegistry`` 执行工具
    3. 将工具执行结果写入 ``Context`` 中
    """ 

    name = "tool_execute"
    uses_llm = False

    def run(self, context: Context) -> Context:
        decision = context.tools.get("decision", {})
        if not decision.get("need_tool", False):
            return context

        tool_name = decision.get("tool_name", "")
        tool_params = decision.get("tool_params", {})
        if not tool_name or not tool_params:
            return context

        ensure_tools_registered()
        tool_result = self._execute_tool(tool_name, tool_params)
        if tool_result:
            validated_result = self._validate_tool_result_json(tool_result)
            context.tools["results"].append({"tool_name": tool_name, "result": validated_result})
            logger.info("工具 %s 调用成功，结果已写入 context", tool_name)
        return context

    def _execute_tool(self, tool_name: str, tool_params: Dict[str, Any]) -> Optional[str]:
        try:
            return ToolRegistry.execute_sync(tool_name, **tool_params)
        except Exception as e:
            logger.error("工具 %s 执行失败: %s", tool_name, e)
            return None

    def _validate_tool_result_json(self, result_str: str) -> Dict[str, Any]:
        if not result_str:
            return {"success": False, "error": "工具返回结果为空"}

        result_str = result_str.strip()
        if result_str.startswith("```"):
            lines = result_str.split("\n")
            result_str = "\n".join(lines[1:-1]) if len(lines) > 2 else result_str.strip("`")

        try:
            parsed = json.loads(result_str)
            if isinstance(parsed, dict):
                return parsed
            return {"success": True, "data": parsed}
        except json.JSONDecodeError:
            logger.warning("工具结果 JSON 格式无效，已包装为标准格式")
            return {
                "success": True,
                "raw_result": result_str[:2000],
                "format_warning": "原始结果非 JSON 格式，已包装",
            }


class ToolsAgent(BaseAgent):
    """工具调用语义的组合 Agent。
    
    职责：
    1. 从 ``Context`` 中提取用户输入
    2. 调用 ``ToolPlanAgent`` 生成工具调用计划
    3. 调用 ``ToolExecuteAgent`` 执行工具
    4. 将工具执行结果写入 ``Context`` 中
    """

    name = "tools"
    uses_llm = True

    def __init__(
        self,
        plan_agent: Optional[ToolPlanAgent] = None,
        execute_agent: Optional[ToolExecuteAgent] = None,
    ):
        self.plan_agent = plan_agent or ToolPlanAgent()
        self.execute_agent = execute_agent or ToolExecuteAgent()

    def run(self, context: Context) -> Context:
        context = self.plan_agent.run(context)
        return self.execute_agent.run(context)

    def process(self, context: Context, shared_dict: Optional[Any] = None) -> Context:
        context = self.run(context)
        if shared_dict is not None:
            shared_dict["tools_done"] = True
            shared_dict["tool_results"] = list(context.tools["results"])
        return context
