"""
阿里云百炼 Web Search MCP 工具

通过 DashScope MCP endpoint 调用官方 WebSearch 工具，支持联网搜索与结果摘要。

环境变量要求：
    DASHSCOPE_API_KEY: 阿里云百炼 API Key

MCP 服务地址：
    https://dashscope.aliyuncs.com/api/v1/mcps/WebSearch/mcp
"""

from __future__ import annotations

import json
import os
from typing import Optional, Dict, Any, List

import requests


class WebSearchClient:
    """阿里云百炼 Web Search MCP 客户端。"""

    BASE_URL = "https://dashscope.aliyuncs.com"
    MCP_ENDPOINT = "/api/v1/mcps/WebSearch/mcp"
    MCP_PROTOCOL_VERSION = "2024-11-05"
    TOOL_NAME = "bailian_web_search"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("DASHSCOPE_API_KEY")
        if not self.api_key:
            raise ValueError("请设置环境变量 DASHSCOPE_API_KEY")

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _endpoint(self) -> str:
        return f"{self.BASE_URL}{self.MCP_ENDPOINT}"

    def _jsonrpc_payload(self, method: str, params: Optional[Dict[str, Any]] = None, request_id: int = 1) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
        }
        if params is not None:
            payload["params"] = params
        return payload

    def _post_mcp(self, payload: Dict[str, Any], timeout: int = 30) -> Dict[str, Any]:
        response = requests.post(
            self._endpoint(),
            json=payload,
            headers=self._get_headers(),
            timeout=timeout,
        )
        response.raise_for_status()
        data = response.json()
        if data.get("error"):
            raise Exception(f"MCP 调用失败：{data['error']}")
        return data

    def initialize(self) -> Dict[str, Any]:
        payload = self._jsonrpc_payload(
            "initialize",
            {
                "protocolVersion": self.MCP_PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {
                    "name": "SmartAgent-WebSearchClient",
                    "version": "0.1.0",
                },
            },
        )
        return self._post_mcp(payload)

    def list_tools(self) -> Dict[str, Any]:
        payload = self._jsonrpc_payload("tools/list", {"cursor": None})
        return self._post_mcp(payload)

    def call_tool(self, query: str, count: int = 5) -> Dict[str, Any]:
        payload = self._jsonrpc_payload(
            "tools/call",
            {
                "name": self.TOOL_NAME,
                "arguments": {
                    "query": query,
                    "count": count,
                },
            },
        )
        return self._post_mcp(payload, timeout=60)

    def _extract_tool_text(self, response_data: Dict[str, Any]) -> str:
        result = response_data.get("result", {})
        content = result.get("content", [])
        texts: List[str] = []
        for item in content:
            if item.get("type") == "text" and item.get("text"):
                texts.append(item["text"])
        return "\n".join(texts).strip()

    def search(
        self,
        query: str,
        count: int = 10,
        country: Optional[str] = None,
        lang: str = "zh-CN",
    ) -> Dict[str, Any]:
        """通过 MCP WebSearch 工具执行搜索。"""
        response_data = self.call_tool(query=query, count=min(count, 50))
        text = self._extract_tool_text(response_data)

        parsed: Dict[str, Any] = {}
        if text:
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                parsed = {"raw_text": text}

        pages = parsed.get("pages", []) if isinstance(parsed, dict) else []
        results: List[Dict[str, Any]] = []
        for page in pages[:count]:
            results.append(
                {
                    "title": page.get("title", ""),
                    "url": page.get("url", ""),
                    "snippet": page.get("snippet", ""),
                    "source": page.get("hostname", page.get("source", "")),
                }
            )

        return {
            "query": query,
            "results": results,
            "raw": response_data,
        }

    def quick_search(self, query: str, max_results: int = 5) -> str:
        result = self.search(query, count=max_results)
        results = result.get("results", [])

        if not results:
            return f"未找到关于'{query}'的搜索结果"

        summary_parts = []
        for i, item in enumerate(results[:max_results], 1):
            title = item.get("title", "")
            snippet = item.get("snippet", "")
            url = item.get("url", "")
            source = item.get("source", "")
            summary_parts.append(f"[{i}] {title}\n{snippet}\n来源：{source}\n链接：{url}")

        return f"搜索关键词：{query}\n\n" + "\n\n".join(summary_parts)

    def search_with_agent(
        self,
        query: str,
        agent_id: str = "default",
        agent_version: str = "latest",
    ) -> Dict[str, Any]:
        raise NotImplementedError("当前版本仅支持 WebSearch MCP tools/call 调用")


def get_web_search_client(api_key: Optional[str] = None) -> WebSearchClient:
    return WebSearchClient(api_key)
