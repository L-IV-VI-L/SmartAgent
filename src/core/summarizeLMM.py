"""
总结回复模块 (Summarize LMM Module)

职责：
1. 读取 Context 中 build_prompt() 生成的最终提示词
2. 调用 LLM 生成回复
3. 根据人格、语气、情绪调整回复风格
4. 将本轮对话向量化存入 Milvus 长期记忆
5. 将本轮对话存入 Redis 短期记忆
"""

import os
import time
from typing import Optional, List, Dict, Any
import requests

from .context import Context
from ..Tools.BaseLLM import BaseLLMClient
from ..database.db_config import MILVUS_COLLECTIONS
from ..database.repositories import ConversationRepository, MemoryRepository


class SummarizeModule:
    """总结回复模块"""

    RESPONSE_SYSTEM_PROMPT = """你是一个拟人对话助手。根据以下上下文信息，生成符合当前人格、语气和情绪的回复。

回复要求：
1. 结合用户情绪调整回复风格
2. 体现当前人格特征
3. 使用当前语气风格
4. 如果工具结果存在，引用工具提供的信息
5. 如果有相关记忆，适当提及以体现连贯性
6. 回复要自然流畅，避免机械感

注意：
- 不要直接重复上下文中的设定信息
- 工具结果需要用自己的话总结，不要直接复制
- 保持回复简洁明了（通常小于300 字）"""

    DASHSCOPE_EMBEDDING_URL = "https://dashscope.aliyuncs.com/api/v1/services/embeddings/text-embedding/text-embedding"
    EMBEDDING_MODEL = "text-embedding-v3"

    def __init__(self):
        """初始化总结模块"""
        self.llm_client = BaseLLMClient()
        self.conversation_repo = ConversationRepository()
        self.memory_repo = MemoryRepository()

    def generate_response(self, context: Context, system_prompt: Optional[str] = None, **kwargs) -> str:
        """
        生成回复

        Args:
            context: Context 对象（必须已由调用方完成 build_prompt()）
            system_prompt: 自定义系统提示词（可选，覆盖默认）
            **kwargs: 其他传递给 LLM 的参数

        Returns:
            生成的回复文本
        """
        effective_system = system_prompt or self.RESPONSE_SYSTEM_PROMPT

        response = self.llm_client.chat_with_prompt(
            prompt=context.text,
            system_message=effective_system,
            **kwargs
        )

        return response

    def generate_response_with_history(self, context: Context, history_messages: Optional[List[Dict[str, Any]]] = None, system_prompt: Optional[str] = None, **kwargs) -> str:
        """
        生成回复（带完整对话历史）

        Args:
            context: Context 对象
            history_messages: 额外的历史消息列表 [{"role": "...", "content": "..."}]
            system_prompt: 自定义系统提示词
            **kwargs: 其他参数

        Returns:
            生成的回复文本
        """
        messages = []

        if history_messages:
            messages.extend(history_messages)

        messages.append({"role": "user", "content": context.text})

        effective_system = system_prompt or self.RESPONSE_SYSTEM_PROMPT

        response = self.llm_client.chat(
            messages=messages,
            system_prompt=effective_system,
            **kwargs
        )

        return response

    def save_conversation_to_milvus(self, user_id: str, user_input: str, response: str):
        try:
            from ..database.milvus_client import MilvusClient

            content = f"用户：{user_input}\n助手：{response}"
            vector = self._get_embedding(content)
            if vector is None:
                vector = [0.0] * 1536

            now = time.time()
            memory_id = f"{user_id}_{int(now * 1000)}"
            payload = [{
                "id": memory_id,
                "doc_id": memory_id,
                "text": content,
                "embedding": vector,
            }]

            self.memory_repo.append(user_id=user_id, content=content, embedding=vector, doc_id=memory_id)
            print(f"[记忆存储] user_id={user_id}, 对话已存入 Milvus")
        except Exception as e:
            print(f"[记忆存储] 存入失败: {e}")

    def save_conversation_to_redis(
        self,
        user_id: str,
        user_input: str,
        response: str,
    ):
        """
        将本轮对话存入 Redis 短期记忆

        存储内容：用户输入 + 大模型回复
        最大保留轮数：15 轮，超出自动截断
        过期时间：3 天

        Args:
            user_id: 用户 ID
            user_input: 扩写后的用户输入
            response: 大模型生成的回复
        """
        try:
            self.conversation_repo.append_turn(user_id=user_id, user_input=user_input, response=response)
            print(f"[短期记忆] user_id={user_id}, 已存入 Redis")

        except Exception as e:
            print(f"[短期记忆] 存入失败: {e}")

    def _get_embedding(self, text: str) -> Optional[list]:
        """
        调用 DashScope 获取文本向量

        Args:
            text: 输入文本

        Returns:
            向量列表，失败返回 None
        """
        api_key = os.getenv("DASHSCOPE_API_KEY")
        if not api_key:
            print("[记忆存储] 缺少环境变量 DASHSCOPE_API_KEY")
            return None

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.EMBEDDING_MODEL,
            "input": {
                "texts": [text]
            },
            "parameters": {
                "text_type": "query"
            }
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
                embedding = embeddings[0].get("embedding") or []
                target_dim = 1536
                if len(embedding) < target_dim:
                    embedding = embedding + [0.0] * (target_dim - len(embedding))
                elif len(embedding) > target_dim:
                    embedding = embedding[:target_dim]
                return embedding

            print(f"[记忆存储] Embedding API 返回为空: {data}")
            return None

        except requests.exceptions.Timeout:
            print("[记忆存储] Embedding 请求超时")
            return None
        except requests.exceptions.RequestException as e:
            print(f"[记忆存储] Embedding 网络请求失败: {e}")
            return None
        except Exception as e:
            print(f"[记忆存储] Embedding 异常: {e}")
            return None


def generate_response(
    context: Context,
    system_prompt: Optional[str] = None,
    **kwargs
) -> str:
    """便捷函数：生成回复"""
    module = SummarizeModule()
    return module.generate_response(context, system_prompt, **kwargs)
