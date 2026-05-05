"""
SmartAgent FastAPI 服务入口

提供 RESTful API 接口，封装 SmartAgent 核心功能。
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from src.api.models import (
    ChatRequest,
    ChatResponse,
    ErrorResponse,
    HealthResponse,
    StatusResponse,
)
from src.main import SmartAgentAPI

logger = logging.getLogger(__name__)

VERSION = "0.1.0"

smart_agent: SmartAgentAPI | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global smart_agent
    smart_agent = SmartAgentAPI()
    logger.info("SmartAgent FastAPI 服务启动完成")
    yield
    logger.info("SmartAgent FastAPI 服务关闭")


app = FastAPI(
    title="SmartAgent API",
    description="面向多 Agent 协作的智能对话服务",
    version=VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse(status="ok", version=VERSION)


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    if smart_agent is None:
        raise HTTPException(status_code=503, detail="服务未初始化")

    result = await smart_agent.process_message(
        user_id=req.user_id,
        message=req.message,
        session_id=req.session_id,
    )

    if not result.get("success"):
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                user_id=req.user_id,
                session_id=result.get("session_id", req.user_id),
                error=result.get("error", ""),
                error_type=result.get("error_type", ""),
                processing_time=result.get("processing_time", 0),
            ).model_dump(),
        )

    return ChatResponse(**result)


@app.get("/status/{user_id}", response_model=StatusResponse)
async def get_user_status(user_id: str):
    from src.database.repositories import MemoryRepository, ConversationRepository

    try:
        repo = MemoryRepository()
        conv_repo = ConversationRepository()

        profile = repo.get_user_profile(user_id)
        emotion = conv_repo.get_emotion_state(user_id)

        return StatusResponse(
            status="ok",
            user_id=user_id,
            emotion=emotion.get("emotion") if emotion else None,
            persona=profile,
        )
    except Exception as e:
        logger.error("获取用户状态失败: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
