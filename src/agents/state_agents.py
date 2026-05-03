from __future__ import annotations

"""状态处理相关 Agent。"""


import json
import time
from typing import Any, Dict, List, Optional

from ..core.context import Context
from ..database.db_config import REDIS_EXPIRE
from ..database.redis_client import RedisClient
from ..database.repositories import PersonaRepository
from ..prompts import PERSONA_ADJUSTMENT_PROMPT
from ..Tools.BaseLLM import BaseLLMClient
from ..utils.json_utils import parse_json_response
from ..utils.logger import get_logger
from .base import BaseAgent
from .config import (
    DEFAULT_PERSONALITY,
    DEFAULT_TONE,
    EMOTION_PERSONA_MAP,
    EMOTION_TONE_MAP,
    PERSONA_UPDATE_THRESHOLD,
    REDIS_PERSONA_STEP_KEY,
    TONE_UPDATE_THRESHOLD,
    UPDATE_STEP,
)

logger = get_logger(__name__)


class StateAdjustAgent(BaseAgent):
    """状态调整 Agent。

    负责人格、语气、情绪联动带来的状态更新：
    1. 从 MongoDB 读取用户人格配置，不存在时写入默认配置。
    2. 根据情绪、用户输入、近期历史和当前人格配置计算微调步长。
    3. 将微调步长写入 Redis，达到阈值时回写 MongoDB。
    4. 将最新人格配置同步到 ``context.persona``。
    """

    name = "state_adjust"
    uses_llm = True

    def __init__(
        self,
        llm_client: Optional[BaseLLMClient] = None,
        persona_repo: Optional[PersonaRepository] = None,
    ):
        self.llm_client = llm_client or BaseLLMClient()
        self.persona_repo = persona_repo or PersonaRepository()

    def run(self, context: Context) -> Context:
        return self.process(context)

    def process(self, context: Context, shared_dict: Optional[Any] = None) -> Context:
        user_id = context.user_id
        persona_data = self._load_persona_from_mongo(user_id)
        persona_step, tone_step = self._calculate_adjustment_steps(
            emotion=context.emotion,
            user_input=context.user_input,
            short_history=context.memory.get("short_history", []),
            current_personality=persona_data["personality_weights"],
            current_tone=persona_data["tone_weights"],
        )
        self._save_steps_to_redis(user_id, persona_step, tone_step)
        if self._check_threshold(persona_step, tone_step):
            persona_data["personality_weights"] = self._apply_steps(
                persona_data["personality_weights"],
                persona_step,
            )
            persona_data["tone_weights"] = self._apply_steps(
                persona_data["tone_weights"],
                tone_step,
            )
            self._update_persona_to_mongo(
                user_id,
                persona_data["personality_weights"],
                persona_data["tone_weights"],
            )
        self._write_persona_to_context(context, persona_data)
        if shared_dict is not None:
            shared_dict["persona_done"] = True
            shared_dict["persona_data"] = {
                "nickname": persona_data["nickname"],
                "custom_persona": persona_data["custom_persona"],
                "personality_weights": persona_data["personality_weights"],
                "tone_weights": persona_data["tone_weights"],
            }
        return context

    # ==========================================
    # MongoDB 操作
    # ==========================================

    def _load_persona_from_mongo(self, user_id: str) -> Dict[str, Any]:
        try:
            doc = self.persona_repo.get(user_id)
            if doc.get("_exists"):
                return self._build_persona_data(doc)
            default_data = self._default_persona_data()
            self.persona_repo.upsert(
                user_id=user_id,
                personality_weights=default_data["personality_weights"],
                tone_weights=default_data["tone_weights"],
                nickname=default_data.get("nickname", ""),
                custom_persona=default_data.get("custom_persona", ""),
            )
            logger.info("MongoDB 未找到 user_id=%s 的人格配置，已写入默认值", user_id)
            return default_data
        except Exception as e:
            logger.error("MongoDB 加载人格配置失败: %s，使用默认值", e)
            return self._default_persona_data()

    def _update_persona_to_mongo(
        self,
        user_id: str,
        personality_weights: Dict[str, float],
        tone_weights: Dict[str, float],
    ):
        try:
            self.persona_repo.upsert(user_id, personality_weights, tone_weights)
            logger.info("MongoDB 人格配置已更新, user_id=%s", user_id)
        except Exception as e:
            logger.error("MongoDB 更新人格配置失败: %s", e)

    # ==========================================
    # Context 对齐操作
    # ==========================================

    def _write_persona_to_context(self, context: Context, persona_data: Dict[str, Any]):
        """将人格配置写入 context.persona。"""
        context.persona.update({
            "nickname": persona_data.get("nickname", ""),
            "custom_persona": persona_data.get("custom_persona", ""),
            "personality_weights": persona_data.get("personality_weights", {}),
            "tone_weights": persona_data.get("tone_weights", {}),
        })

    # ==========================================
    # LLM 情感分析与步长计算
    # ==========================================

    def _calculate_adjustment_steps(
        self,
        emotion: Dict[str, Any],
        user_input: str,
        short_history: List[Dict[str, Any]],
        current_personality: Dict[str, Any],
        current_tone: Dict[str, Any],
    ) -> tuple[Dict[str, float], Dict[str, float]]:
        history_text = self._format_history(short_history)
        personality_list = ", ".join(current_personality.keys())
        tone_list = ", ".join(current_tone.keys())

        system_prompt = PERSONA_ADJUSTMENT_PROMPT.format(
            personality_list=personality_list,
            tone_list=tone_list,
            personality_json=json.dumps(current_personality, ensure_ascii=False),
            tone_json=json.dumps(current_tone, ensure_ascii=False),
        )

        user_prompt_parts = [
            f"用户情绪：{emotion.get('label', 'neutral')}（强度：{emotion.get('score', 0.5)}）",
        ]
        if history_text:
            user_prompt_parts.append(f"近期对话：\n{history_text}")
        user_prompt_parts.append(f"用户当前输入：{user_input}")
        user_prompt_parts.append("请分析人格和语气的微调步长：")

        user_prompt = "\n\n".join(user_prompt_parts)

        try:
            response = self.llm_client.chat_with_prompt(
                prompt=user_prompt,
                system_message=system_prompt,
            )
            result = self._parse_json_response(response)

            if result:
                persona_step = self._filter_and_clip_steps(
                    result.get("persona_step", {}),
                    current_personality,
                )
                tone_step = self._filter_and_clip_steps(
                    result.get("tone_step", {}),
                    current_tone,
                )
                reason = result.get("reason", "")
                if reason:
                    logger.info("人格调整原因: %s", reason)
                return persona_step, tone_step

        except Exception as e:
            logger.warning("LLM 计算微调步长失败，使用默认步长: %s", e)

        return self._default_steps(emotion, current_personality, current_tone)

    def _default_steps(
        self,
        emotion: Dict[str, Any],
        current_personality: Dict[str, Any],
        current_tone: Dict[str, Any],
    ) -> tuple[Dict[str, float], Dict[str, float]]:
        emotion_label = emotion.get("label", "neutral")
        emotion_score = emotion.get("score", 0.5)

        persona_step = {k: 0.0 for k in current_personality}
        tone_step = {k: 0.0 for k in current_tone}

        base_step = UPDATE_STEP * emotion_score

        for tag, multiplier in EMOTION_PERSONA_MAP.get(emotion_label, {}).items():
            if tag in persona_step:
                persona_step[tag] = round(base_step * multiplier, 4)

        for tag, multiplier in EMOTION_TONE_MAP.get(emotion_label, {}).items():
            if tag in tone_step:
                tone_step[tag] = round(base_step * multiplier, 4)

        return persona_step, tone_step

    # ==========================================
    # Redis 操作
    # ==========================================

    def _save_steps_to_redis(
        self,
        user_id: str,
        persona_step: Dict[str, float],
        tone_step: Dict[str, float],
    ):
        try:
            with RedisClient() as redis:
                persona_key = REDIS_PERSONA_STEP_KEY.format(user_id=user_id)

                now = time.time()
                step_data = {
                    "user_id": user_id,
                    "persona_step": persona_step,
                    "tone_step": tone_step,
                    "timestamp": now,
                }
                redis.client.setex(
                    persona_key,
                    REDIS_EXPIRE.get("persona_step", 86400),
                    json.dumps(step_data, ensure_ascii=False),
                )

                logger.debug("微调步长已存入 Redis, user_id=%s, 人格步长=%s, 语气步长=%s", user_id, persona_step, tone_step)

        except Exception as e:
            logger.error("Redis 存入微调步长失败: %s", e)

    # ==========================================
    # 工具方法
    # ==========================================

    def _check_threshold(
        self,
        persona_step: Dict[str, float],
        tone_step: Dict[str, float],
    ) -> bool:
        for v in persona_step.values():
            if abs(v) >= PERSONA_UPDATE_THRESHOLD:
                return True

        for v in tone_step.values():
            if abs(v) >= TONE_UPDATE_THRESHOLD:
                return True

        return False

    def _apply_steps(
        self,
        current_weights: Dict[str, float],
        steps: Dict[str, float],
    ) -> Dict[str, float]:
        return {
            key: round(max(0.0, current_weights.get(key, 0.0) + steps.get(key, 0.0)), 4)
            for key in current_weights
        }

    def _filter_and_clip_steps(
        self,
        raw_steps: Dict[str, Any],
        valid_keys: Dict[str, Any],
    ) -> Dict[str, float]:
        result = {k: 0.0 for k in valid_keys}
        for k, v in raw_steps.items():
            if k in valid_keys:
                result[k] = max(-0.2, min(0.2, float(v)))
        return result

    def _format_history(self, short_history: List[Dict[str, Any]]) -> str:
        if not short_history:
            return ""
        parts = [
            f"{msg.get('role', 'unknown')}: {msg.get('content', '')}"
            for msg in short_history
        ]
        return "\n".join(parts)

    def _build_persona_data(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "nickname": doc.get("nickname", ""),
            "custom_persona": doc.get("custom_persona", ""),
            "personality_weights": doc.get("personality_weights", {}),
            "tone_weights": doc.get("tone_weights", {}),
        }

    def _default_persona_data(self) -> Dict[str, Any]:
        return {
            "nickname": "",
            "custom_persona": "",
            "personality_weights": DEFAULT_PERSONALITY.copy(),
            "tone_weights": DEFAULT_TONE.copy(),
        }

    def _parse_json_response(self, response: str) -> Optional[Dict[str, Any]]:
        return parse_json_response(response)
