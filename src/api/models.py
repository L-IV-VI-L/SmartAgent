"""
FastAPI 请求/响应数据模型
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    user_id: str = Field(..., description="用户唯一标识")
    message: str = Field(..., min_length=1, max_length=2000, description="用户输入的消息")
    session_id: Optional[str] = Field(None, description="会话 ID，不提供则自动使用 user_id")


class ToolResult(BaseModel):
    tool_name: str
    result: Any


class ChatResponse(BaseModel):
    success: bool
    user_id: str
    session_id: str
    response: str
    emotion: str
    state: Optional[Dict[str, Any]] = None
    tool_results: List[Dict[str, Any]] = Field(default_factory=list)
    processing_time: float


class ErrorResponse(BaseModel):
    success: bool = False
    user_id: str
    session_id: str
    response: str = ""
    error: str
    error_type: str
    processing_time: float


class StatusResponse(BaseModel):
    status: str
    user_id: str
    emotion: Optional[str] = None
    persona: Optional[Dict[str, Any]] = None


class HealthResponse(BaseModel):
    status: str
    version: str = "0.1.0"
