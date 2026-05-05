"""情绪和状态分析 Agent。

按照 config.py 中的规则设计：
1. 使用 DEFAULT_PERSONALITY 和 DEFAULT_TONE 作为人格基线
2. 使用 EMOTION_PERSONA_MAP 和 EMOTION_TONE_MAP 进行情绪到人格/语气的映射
3. 使用 UPDATE_STEP 计算调整步长
4. 输出符合 MONGO_AGENT_PERSONALITY_SCHEMA 的格式
"""

from __future__ import annotations

import json
import time
from typing import Any, Dict, Optional

from ..core.context import Context
from ..database.db_config import REDIS_EXPIRE, MONGO_COLLECTIONS
from ..database.redis_client import RedisClient
from ..database.repositories import PersonaRepository
from ..Tools.BaseLLM import BaseLLMClient
from ..utils.logger import get_logger
from .base import BaseAgent
from .config import (
    DEFAULT_PERSONALITY,
    DEFAULT_TONE,
    EMOTION_PERSONA_MAP,
    EMOTION_TONE_MAP,
    UPDATE_STEP,
    PERSONA_UPDATE_THRESHOLD,
    TONE_UPDATE_THRESHOLD,
    REDIS_PERSONA_STEP_KEY,
    REDIS_TONE_STEP_KEY,
)
from src.prompts import EMOTION_STATE_SYSTEM_PROMPT

logger = get_logger(__name__)


class EmotionStateAgent(BaseAgent):
    """情绪分析和状态调整 Agent。

    按照 config.py 中的规则：
    1. 使用 LLM 分析情绪标签和分数
    2. 根据 EMOTION_PERSONA_MAP 和 EMOTION_TONE_MAP 计算人格/语气调整步长
    3. 使用 UPDATE_STEP 作为步长基数
    4. 将步长写入 Redis，达到阈值时回写 MongoDB
    """

    name = "emotion_state"
    uses_llm = True

    def __init__(
        self,
        llm_client: Optional[BaseLLMClient] = None,
    ):
        self.llm_client = llm_client or BaseLLMClient()
        self.persona_repo = PersonaRepository()

    def run(self, context: Context) -> Context:
        user_input = context.user_input or context.raw_input or ""
        user_id = getattr(context, "user_id", "anonymous")

        # 1. LLM 情绪分析
        emotion_data = self._analyze_emotion(user_input)
        emotion_label = emotion_data.get("emotion_label", "neutral")
        emotion_score = emotion_data.get("emotion_score", 0.5)
        emotion_analysis = emotion_data.get("emotion_analysis", "")

        logger.info(
            "情绪分析: user_id=%s, label=%s, score=%.2f, analysis=%s",
            user_id, emotion_label, emotion_score, emotion_analysis,
        )

        # 2. 从 MongoDB 获取当前人格配置
        persona = self.persona_repo.get(user_id)
        current_personality = persona.get("personality_weights", dict(DEFAULT_PERSONALITY))
        current_tone = persona.get("tone_weights", dict(DEFAULT_TONE))

        # 3. 根据情绪映射计算调整步长
        persona_step, tone_step = self._calculate_steps(emotion_label, emotion_score, current_personality, current_tone)

        # 4. 将步长写入 Redis
        self._save_steps_to_redis(user_id, persona_step, tone_step)

        # 5. 检查是否达到阈值，如果达到则回写 MongoDB
        self._maybe_flush_to_mongo(user_id, current_personality, current_tone)

        # 6. 获取最新人格配置并写入 context
        updated_persona = self.persona_repo.get(user_id)
        context.persona = updated_persona
        context.emotion_analysis = emotion_analysis
        context.emotion_score = emotion_score
        context.emotion_label = emotion_label

        return context

    def _analyze_emotion(self, user_input: str) -> Dict[str, Any]:
        """使用 LLM 分析用户情绪。"""
        response = self.llm_client.chat_with_prompt(
            prompt=f"用户输入: {user_input}",
            system_message=EMOTION_STATE_SYSTEM_PROMPT,
        )

        if not response:
            return {"emotion_label": "neutral", "emotion_score": 0.5, "emotion_analysis": "LLM 分析失败"}

        return self._parse_json(response)

    def _calculate_steps(
        self,
        emotion_label: str,
        emotion_score: float,
        current_personality: Dict[str, float],
        current_tone: Dict[str, float],
    ) -> tuple[Dict[str, float], Dict[str, float]]:
        """根据情绪映射计算人格和语气调整步长。

        按照 config.py 中的规则：
        - base_step = UPDATE_STEP * emotion_score
        - 根据 EMOTION_PERSONA_MAP 和 EMOTION_TONE_MAP 计算各标签的调整量
        """
        persona_step = {k: 0.0 for k in current_personality}
        tone_step = {k: 0.0 for k in current_tone}

        base_step = UPDATE_STEP * emotion_score

        # 根据情绪映射计算人格步长
        for tag, multiplier in EMOTION_PERSONA_MAP.get(emotion_label, {}).items():
            if tag in persona_step:
                persona_step[tag] = round(base_step * multiplier, 4)

        # 根据情绪映射计算语气步长
        for tag, multiplier in EMOTION_TONE_MAP.get(emotion_label, {}).items():
            if tag in tone_step:
                tone_step[tag] = round(base_step * multiplier, 4)

        return persona_step, tone_step

    def _save_steps_to_redis(
        self,
        user_id: str,
        persona_step: Dict[str, float],
        tone_step: Dict[str, float],
    ):
        """将调整步长写入 Redis。"""
        try:
            with RedisClient() as redis:
                persona_key = REDIS_PERSONA_STEP_KEY.format(user_id=user_id)
                tone_key = REDIS_TONE_STEP_KEY.format(user_id=user_id)

                now = time.time()

                # 写入 persona 步长
                persona_data = {
                    "user_id": user_id,
                    "persona_step": json.dumps(persona_step, ensure_ascii=False),
                    "timestamp": now,
                }
                redis.client.delete(persona_key)
                redis.client.hset(persona_key, mapping=persona_data)
                redis.client.expire(persona_key, REDIS_EXPIRE.get("persona_step", 86400))

                # 写入 tone 步长
                tone_data = {
                    "user_id": user_id,
                    "tone_step": json.dumps(tone_step, ensure_ascii=False),
                    "timestamp": now,
                }
                redis.client.delete(tone_key)
                redis.client.hset(tone_key, mapping=tone_data)
                redis.client.expire(tone_key, REDIS_EXPIRE.get("tone_step", 86400))

                logger.info("Redis 步长数据已写入, user_id=%s", user_id)
        except Exception as e:
            logger.warning("Redis 步长写入失败: %s", e)

    def _maybe_flush_to_mongo(
        self,
        user_id: str,
        current_personality: Dict[str, float],
        current_tone: Dict[str, float],
    ):
        """检查步长是否达到阈值，如果达到则回写 MongoDB。"""
        try:
            with RedisClient() as redis:
                persona_key = REDIS_PERSONA_STEP_KEY.format(user_id=user_id)
                tone_key = REDIS_TONE_STEP_KEY.format(user_id=user_id)

                persona_step_data = redis.client.hgetall(persona_key)
                tone_step_data = redis.client.hgetall(tone_key)

                if not persona_step_data:
                    return

                # 将 bytes 类型的键值转换为 str
                def decode_bytes(data):
                    return {k.decode("utf-8") if isinstance(k, bytes) else k: v.decode("utf-8") if isinstance(v, bytes) else v for k, v in data.items()}

                persona_step_data = decode_bytes(persona_step_data)
                tone_step_data = decode_bytes(tone_step_data)

                logger.info(
                    "Redis 步长数据读取: user_id=%s, persona_step_data=%s, tone_step_data=%s",
                    user_id, persona_step_data, tone_step_data,
                )

                persona_step = json.loads(persona_step_data.get("persona_step", "{}"))
                tone_step = json.loads(tone_step_data.get("tone_step", "{}"))

                logger.info(
                    "Redis 步长解析: user_id=%s, persona_step=%s, tone_step=%s",
                    user_id, persona_step, tone_step,
                )

                # 检查是否达到阈值
                needs_flush = False
                for tag, step in persona_step.items():
                    if abs(float(step)) >= PERSONA_UPDATE_THRESHOLD:
                        needs_flush = True
                        break

                if not needs_flush:
                    for tag, step in tone_step.items():
                        if abs(float(step)) >= TONE_UPDATE_THRESHOLD:
                            needs_flush = True
                            break

                if not needs_flush:
                    return

                # 应用步长并写入 MongoDB
                new_personality = {k: current_personality.get(k, 0.0) + persona_step.get(k, 0.0) for k in current_personality}
                new_tone = {k: current_tone.get(k, 0.0) + tone_step.get(k, 0.0) for k in current_tone}

                self.persona_repo.upsert(user_id, new_personality, new_tone)
                logger.info("MongoDB 人格配置已更新（阈值触发）, user_id=%s", user_id)

                # 清除 Redis 步长
                redis.client.delete(persona_key)
                redis.client.delete(tone_key)

        except Exception as e:
            logger.warning("MongoDB 人格刷新失败: %s", e)

    @staticmethod
    def _parse_json(text: str) -> Dict[str, Any]:
        """解析 LLM 返回的 JSON。"""
        if not text:
            return {}
        text = text.strip()
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1:
            return {}
        json_str = text[start : end + 1]
        try:
            return json.loads(json_str)
        except Exception:
            return {}
