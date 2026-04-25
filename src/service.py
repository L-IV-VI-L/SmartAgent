"""
SmartAgent 服务层

统一封装核心对话流程。
"""

from __future__ import annotations

import logging
import os
import sys
import time
from dataclasses import dataclass
from typing import Optional

# 运行时环境清理，避免外部 PYTHONPATH 污染
os.environ.pop("PYTHONPATH", None)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VENV_SITE = os.path.join(PROJECT_ROOT, ".venv", "Lib", "site-packages")

new_path = []
for p in sys.path:
    norm = os.path.normpath(p)
    if norm == r"D:\Lib\site-packages":
        continue
    new_path.append(p)

if VENV_SITE not in new_path:
    new_path.insert(0, VENV_SITE)
if PROJECT_ROOT not in new_path:
    new_path.insert(1, PROJECT_ROOT)
sys.path = new_path

from .core.context import Context
from .database.memory_decay import decay_memories
from .database.repositories import PersonaRepository, ConversationRepository, MemoryRepository

logger = logging.getLogger(__name__)


@dataclass
class ChatResult:
    user_id: str
    query: str
    response: str
    context: Context


class SmartAgentService:
    """核心 agent 服务，负责串起完整对话闭环。"""

    def _build_summarize_module(self):
        from .core.summarizeLMM import SummarizeModule
        return SummarizeModule()

    def _get_summarize_module(self):
        if self._summarize_module is None:
            self._summarize_module = self._build_summarize_module()
        return self._summarize_module

    def __init__(self):
        self._summarize_module = None
        self.persona_repo = PersonaRepository()
        self.conversation_repo = ConversationRepository()
        self.memory_repo = MemoryRepository()

    def _load_persona(self, user_id: str):
        return self.persona_repo.get(user_id)

    def _check_and_decay(self, user_id: str):
        from .database.redis_client import RedisClient

        with RedisClient() as redis:
            key = f"decay_last_run:{user_id}"
            last_run = redis.client.get(key)
            now = time.time()
            if last_run is None or (now - float(last_run)) > 86400:
                decay_memories(user_id)
                redis.client.set(key, str(now), ex=86400 * 7)

    def create_context(self, user_id: str) -> Context:
        context = Context(user_id=user_id)
        persona_data = self._load_persona(user_id)
        if persona_data:
            context.persona.update(persona_data)
        self._check_and_decay(user_id)
        return context

    def process_query(self, user_id: str, query: str) -> ChatResult:
        from .InputProcess import process_input
        from .StateToolsProcess import process_state_tools

        started_at = time.time()
        logger.info("[SmartAgentService] process_query start user_id=%s", user_id)

        step_started_at = time.time()
        context = self.create_context(user_id)
        logger.info("[SmartAgentService] create_context done cost=%.3fs", time.time() - step_started_at)

        step_started_at = time.time()
        context.raw_input = query
        context.user_input = query
        context = process_input(user_id, query, context)
        logger.info("[SmartAgentService] process_input done cost=%.3fs", time.time() - step_started_at)

        step_started_at = time.time()
        context = process_state_tools(context)
        logger.info("[SmartAgentService] process_state_tools done cost=%.3fs", time.time() - step_started_at)

        step_started_at = time.time()
        context.build_prompt()
        logger.info("[SmartAgentService] build_prompt done cost=%.3fs", time.time() - step_started_at)

        step_started_at = time.time()
        response = self._get_summarize_module().generate_response(context)
        logger.info("[SmartAgentService] generate_response done cost=%.3fs", time.time() - step_started_at)

        step_started_at = time.time()
        self.conversation_repo.append_turn(
            user_id=context.user_id,
            user_input=context.user_input,
            response=response,
            session_id=context.user_id,
        )
        self.memory_repo.append(
            user_id=context.user_id,
            content=f"用户：{context.user_input}\n助手：{response}",
            embedding=[0.0] * 1536,
            doc_id=f"{context.user_id}_{int(time.time() * 1000)}",
        )
        logger.info("[SmartAgentService] persistence done cost=%.3fs", time.time() - step_started_at)
        logger.info("[SmartAgentService] process_query finished total_cost=%.3fs", time.time() - started_at)
        return ChatResult(user_id=user_id, query=query, response=response, context=context)
