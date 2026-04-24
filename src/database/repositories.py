"""统一数据访问层。

将 Redis、MongoDB、Milvus 的基础读写操作收口到这里，业务层只依赖仓库对象，不直接操作底层客户端。
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .db_config import (
    MONGO_COLLECTIONS,
    MILVUS_COLLECTIONS,
    REDIS_EXPIRE,
    REDIS_MAX_HISTORY_COUNT,
)
from .mongodb_client import MongoDBClient
from .redis_client import RedisClient
from .milvus_client import MilvusClient


@dataclass
class PersonaRecord:
    user_id: str
    nickname: str = ""
    custom_persona: str = ""
    personality_weights: Optional[Dict[str, float]] = None
    tone_weights: Optional[Dict[str, float]] = None
    create_time: float = 0.0
    update_time: float = 0.0


class PersonaRepository:
    """MongoDB 人格状态仓库。"""

    def get(self, user_id: str) -> Dict[str, Any]:
        with MongoDBClient() as mongo:
            collection = mongo.db[MONGO_COLLECTIONS["persona"]]
            doc = collection.find_one({"user_id": user_id})
            if not doc:
                return {
                    "user_id": user_id,
                    "nickname": "",
                    "custom_persona": "",
                    "personality_weights": {},
                    "tone_weights": {},
                    "create_time": time.time(),
                    "update_time": time.time(),
                    "_exists": False,
                }
            return {
                "user_id": doc.get("user_id", user_id),
                "nickname": doc.get("nickname", ""),
                "custom_persona": doc.get("custom_persona", ""),
                "personality_weights": doc.get("personality_weights", {}),
                "tone_weights": doc.get("tone_weights", {}),
                "create_time": doc.get("create_time", time.time()),
                "update_time": doc.get("update_time", time.time()),
                "_exists": True,
            }

    def upsert(self, user_id: str, personality_weights: Dict[str, float], tone_weights: Dict[str, float], nickname: str = "", custom_persona: str = "") -> None:
        now = time.time()
        with MongoDBClient() as mongo:
            collection = mongo.db[MONGO_COLLECTIONS["persona"]]
            collection.update_one(
                {"user_id": user_id},
                {
                    "$set": {
                        "user_id": user_id,
                        "nickname": nickname,
                        "custom_persona": custom_persona,
                        "personality_weights": personality_weights,
                        "tone_weights": tone_weights,
                        "update_time": now,
                    },
                    "$setOnInsert": {"create_time": now},
                },
                upsert=True,
            )


class ConversationRepository:
    """Redis 短期记忆仓库。"""

    def append_turn(self, user_id: str, user_input: str, response: str, session_id: Optional[str] = None) -> None:
        now = time.time()
        session_id = session_id or user_id
        with RedisClient() as redis:
            key = f"short_history:{user_id}"
            pipe = redis.client.pipeline()
            pipe.rpush(
                key,
                json.dumps({"session_id": session_id, "role": "user", "content": user_input, "timestamp": now, "turn_id": int(now * 1000)}),
            )
            pipe.rpush(
                key,
                json.dumps({"session_id": session_id, "role": "assistant", "content": response, "timestamp": now, "turn_id": int(now * 1000) + 1}),
            )
            pipe.ltrim(key, -REDIS_MAX_HISTORY_COUNT, -1)
            pipe.expire(key, REDIS_EXPIRE)
            pipe.execute()

    def get_recent(self, user_id: str, limit: int = REDIS_MAX_HISTORY_COUNT) -> List[Dict[str, Any]]:
        with RedisClient() as redis:
            raw = redis.client.lrange(f"short_history:{user_id}", 0, -1)
        result: List[Dict[str, Any]] = []
        for item in raw:
            try:
                result.append(json.loads(item.decode("utf-8")))
            except Exception:
                continue
        return result[-limit:]


class MemoryRepository:
    """Milvus 长期记忆仓库。"""

    def append(self, user_id: str, content: str, embedding: List[float], doc_id: Optional[str] = None) -> None:
        now = time.time()
        doc_id = doc_id or f"{user_id}_{int(now * 1000)}"
        payload = [{"id": doc_id, "doc_id": doc_id, "text": content, "embedding": embedding}]
        with MilvusClient() as milvus:
            milvus.client.insert(collection_name=MILVUS_COLLECTIONS["long_memory"], data=payload)

    def search(self, query: str, top_k: int = 3, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        with MilvusClient() as milvus:
            return milvus.search(query=query, top_k=top_k, filters=filters)
