from __future__ import annotations

"""JSON 解析工具函数。"""

import json
import re
from typing import Any, Dict, Optional


def parse_json_response(response: str) -> Optional[Dict[str, Any]]:
    """解析 LLM 返回的 JSON 响应（支持 markdown 代码块格式）。

    Args:
        response: 包含 JSON 内容的字符串，可能包裹在 ``` 代码块中。

    Returns:
        解析后的字典，解析失败返回 None。
    """
    response = (response or "").strip()
    if response.startswith("```"):
        lines = response.split("\n")
        response = "\n".join(lines[1:-1]) if len(lines) > 2 else response.strip("`")
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        return None


def extract_json_from_text(text: str) -> Optional[Dict[str, Any]]:
    """从文本中提取第一个合法的 JSON 对象。

    先尝试直接解析，失败后使用正则提取花括号包裹的内容。

    Args:
        text: 可能包含 JSON 的文本字符串。

    Returns:
        解析后的字典，解析失败返回 None。
    """
    if not text:
        return None

    stripped = text.strip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", stripped, flags=re.DOTALL)
    if not match:
        return None

    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
