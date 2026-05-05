from __future__ import annotations

"""回复生成 Agent。


"""

from typing import Any, Callable, Dict, List, Optional
import os
import requests

from ..core.context import Context
from ..database.repositories import ConversationRepository, MemoryRepository
from ..InputProcess.long_memory_extractor import LongMemoryExtractor
from ..InputProcess.memory_schema import LongMemoryRecord
from ..Tools.BaseLLM import BaseLLMClient
from ..utils.logger import get_logger
from .base import BaseAgent
from src.prompts import RESPONSE_SYSTEM_PROMPT

logger = get_logger(__name__)


class ResponseAgent(BaseAgent):
    """回复生成 Agent：根据上下文信息生成符合人格、语气和情绪的回复。
    
    职责：
    1. 从 ``Context`` 中提取用户输入、短期记忆、长期记忆和工具调用结果
    2. 调用 ``BaseLLMClient`` 生成回复
    3. 将回复写入 ``Context`` 中
    """

    name = "response"
    uses_llm = True

    DASHSCOPE_EMBEDDING_URL = "https://dashscope.aliyuncs.com/api/v1/services/embeddings/text-embedding/text-embedding"
    EMBEDDING_MODEL = "text-embedding-v3"

    def __init__(
        self,
        llm_client: Optional[BaseLLMClient] = None,
        conversation_repo: Optional[ConversationRepository] = None,
        memory_repo: Optional[MemoryRepository] = None,
        long_memory_extractor: Optional[LongMemoryExtractor] = None,
        embedding_fn: Optional[Callable[[str], Optional[List[float]]]] = None,
        embedding_dimension: int = 1024,
    ):
        self.llm_client = llm_client or BaseLLMClient()
        self.conversation_repo = conversation_repo or ConversationRepository()
        self.memory_repo = memory_repo or MemoryRepository()
        self.long_memory_extractor = long_memory_extractor or LongMemoryExtractor(llm_client)
        self.embedding_fn = embedding_fn
        self.embedding_dimension = embedding_dimension

    def run(self, context: Context) -> Context:
        if not getattr(context, "text", ""):
            context.build_prompt()
        context.response = self.generate_response(context)
        context.response_text = context.response

        user_input = context.user_input or context.raw_input
        self._save_conversation_to_redis(context.user_id, user_input, context.response)
        self._save_structured_long_memory(context)

        return context

    def _save_conversation_to_redis(self, user_id: str, user_input: str, response: str) -> None:
        """将本轮对话存入 Redis 短期记忆。"""
        try:
            self.conversation_repo.append_turn(
                user_id=user_id,
                user_input=user_input,
                response=response,
            )
            logger.info("短期记忆已存入 Redis, user_id=%s", user_id)
        except Exception as e:
            logger.error("短期记忆存入失败: %s", e)

    def _save_structured_long_memory(self, context: Context) -> None:
        """使用 LongMemoryExtractAgent 提取结构化记忆并写入 MongoDB + Milvus。"""
        try:
            memories = self.long_memory_extractor.extract(context)
            if not memories:
                return

            saved_count = 0
            for memory in memories:
                try:
                    self._attach_embedding(memory)
                    self.memory_repo.append_structured(memory)
                    saved_count += 1
                except Exception as e:
                    logger.error("结构化长期记忆写入失败 doc_id=%s: %s", memory.doc_id, e)

            if saved_count > 0:
                logger.info("已写入 %d 条结构化长期记忆到 MongoDB + Milvus", saved_count)
        except Exception as e:
            logger.error("结构化长期记忆提取失败: %s", e)

    def _attach_embedding(self, memory: LongMemoryRecord) -> None:
        """为记忆附加向量表示。"""
        if memory.embedding is not None:
            return

        vector = self._get_embedding(memory.embedding_text)
        memory.embedding = vector or [0.0] * self.embedding_dimension

    def _get_embedding(self, text: str) -> Optional[List[float]]:
        """获取文本向量（优先使用自定义函数，否则调用 DashScope API）。"""
        if self.embedding_fn is not None:
            result = self.embedding_fn(text)
            if result is not None:
                return result

        api_key = os.getenv("DASHSCOPE_API_KEY")
        if not api_key:
            logger.warning("记忆存储缺少环境变量 DASHSCOPE_API_KEY")
            return None

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.EMBEDDING_MODEL,
            "input": {"texts": [text]},
            "parameters": {"text_type": "query", "dimensions": self.embedding_dimension},
        }

        try:
            resp = requests.post(
                self.DASHSCOPE_EMBEDDING_URL,
                headers=headers,
                json=payload,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()

            embeddings = data.get("output", {}).get("embeddings", [])
            if embeddings:
                embedding = embeddings[0].get("embedding", [])
                if len(embedding) < self.embedding_dimension:
                    embedding = embedding + [0.0] * (self.embedding_dimension - len(embedding))
                elif len(embedding) > self.embedding_dimension:
                    embedding = embedding[:self.embedding_dimension]
                return embedding

            logger.warning("记忆存储 Embedding API 返回为空: %s", data)
            return None

        except requests.exceptions.Timeout:
            logger.error("记忆存储 Embedding 请求超时")
            return None
        except requests.exceptions.RequestException as e:
            logger.error("记忆存储 Embedding 网络请求失败: %s", e)
            return None
        except Exception as e:
            logger.error("记忆存储 Embedding 异常: %s", e)
            return None

    def generate(self, context: Context) -> str:
        result_context = self.run(context)
        return result_context.response

    def generate_response(
        self,
        context: Context,
        system_prompt: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        """生成回复。"""
        effective_system = system_prompt or RESPONSE_SYSTEM_PROMPT

        response = self.llm_client.chat_with_prompt(
            prompt=context.text,
            system_message=effective_system,
            **kwargs,
        )

        return response

    def generate_response_with_history(
        self,
        context: Context,
        history_messages: Optional[List[Dict[str, Any]]] = None,
        system_prompt: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        """生成回复（带完整对话历史）。"""
        messages: List[Dict[str, Any]] = []

        if history_messages:
            messages.extend(history_messages)

        messages.append({"role": "user", "content": context.text})

        effective_system = system_prompt or RESPONSE_SYSTEM_PROMPT

        response = self.llm_client.chat(
            messages=messages,
            system_prompt=effective_system,
            **kwargs,
        )

        return response


def generate_response(
    context: Context,
    system_prompt: Optional[str] = None,
    **kwargs: Any,
) -> str:
    """便捷函数：生成回复。"""
    agent = ResponseAgent()
    return agent.generate_response(context, system_prompt, **kwargs)
