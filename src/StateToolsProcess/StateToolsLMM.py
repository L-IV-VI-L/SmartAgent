"""
状态工具处理模块 (State Tools Process Module)

运行顺序：输入处理模块（InputProcess）之后，LLM 调用之前

职责：
1. 状态处理 Agent：读取人格配置，计算情绪微调步长，更新 MongoDB/Redis
2. 工具调用 Agent：读取扩写结果，判断是否需要调用工具，执行并将结果写入 context
3. 两个 Agent 通过多进程同步运行，提升处理效率
"""

from typing import Optional, List, Dict, Any
import json
import time
import asyncio
import multiprocessing
from multiprocessing import Manager
from ..Tools.BaseLLM import BaseLLMClient
from ..Tools.tool import ToolRegistry, Tool
from ..Tools.amap_tools import AMapClient
from ..Tools.web_search import WebSearchClient
from ..database.repositories import PersonaRepository
from ..database.redis_client import RedisClient
from ..database.db_config import REDIS_EXPIRE
from .config import (
    DEFAULT_PERSONALITY,
    DEFAULT_TONE,
    PERSONA_UPDATE_THRESHOLD,
    TONE_UPDATE_THRESHOLD,
    UPDATE_STEP,
    REDIS_PERSONA_STEP_KEY,
    EMOTION_PERSONA_MAP,
    EMOTION_TONE_MAP,
)
from ..core.context import Context


# ==========================================
# LLM Prompt 模板
# ==========================================

ADJUSTMENT_SYSTEM_PROMPT = """你是一个情感与人格分析助手。根据用户当前情绪、对话历史和当前输入，分析助手应该如何调整自己的人格和语气来更好地回应用户。

当前人格选项：{personality_list}
当前语气选项：{tone_list}

当前人格权重：{personality_json}
当前语气权重：{tone_json}

请分析并返回两个对象的微调步长（正数表示增强，负数表示减弱，范围 -0.2 ~ 0.2）：

请严格按照以下 JSON 格式返回：
{{
  "persona_step": {{
    "人格标签1": 步长值,
    "人格标签2": 步长值
  }},
  "tone_step": {{
    "语气标签1": 步长值,
    "语气标签2": 步长值
  }},
  "reason": "简短分析原因（50字以内）"
}}

注意：
- 只返回当前已有人格/语气标签的步长
- 步长范围：-0.2 ~ 0.2
- 不需要调整的标签步长设为 0"""

TOOL_DECISION_PROMPT = """你是一个工具调用决策助手。根据用户输入和可用工具列表，判断是否需要调用工具来辅助回答。

可用工具：
{tools_info}

用户输入：{user_input}

请分析是否需要调用工具，如果需要，请指定工具名称和参数。

请严格按照以下 JSON 格式返回：
{{
  "need_tool": true/false,
  "tool_name": "工具名称（如果不需要则为空字符串）",
  "tool_params": {{}},
  "reason": "简短决策原因（50字以内）"
}}

注意：
- 如果用户输入可以独立回答，need_tool 设为 false
- 如果需要实时数据（天气、地图、搜索等），need_tool 设为 true
- tool_params 必须是有效的 JSON 对象"""


# ==========================================
# 公共辅助函数
# ==========================================

def _parse_json_response(response: str) -> Optional[Dict[str, Any]]:
    """解析 LLM 返回的 JSON 响应，处理代码块包裹"""
    response = response.strip()
    if response.startswith("```"):
        lines = response.split("\n")
        response = "\n".join(lines[1:-1]) if len(lines) > 2 else response.strip("`")
    try:
        return json.loads(response)
    except Exception:
        return None


def _build_context_from_data(context_data: Dict[str, Any]) -> Context:
    """从数据字典构建 Context 对象（多进程场景）"""
    context = Context(user_id=context_data.get("user_id", ""))
    context.user_input = context_data.get("user_input", "")
    context.raw_input = context_data.get("raw_input", "")
    context.emotion = context_data.get("emotion", {"label": "neutral", "score": 0.5})
    context.memory = context_data.get("memory", {"short_history": [], "compressed": "", "long_retrieved": []})
    context.persona.update(context_data.get("persona", {}))
    return context


# ==========================================
# 工具定义（模块级类，避免重复注册）
# ==========================================

class WeatherTool(Tool):
    name = "weather_query"
    description = "查询目标城市的实时天气或预报天气"
    
    def __init__(self, amap_client: AMapClient):
        self._amap_client = amap_client
    
    async def _run(self, city: str, extensions: str = "base") -> str:
        result = self._amap_client.get_weather(city=city, extensions=extensions)
        return json.dumps(result, ensure_ascii=False)


class SearchTool(Tool):
    name = "web_search"
    description = "通过互联网搜索获取实时信息"
    
    async def _run(self, query: str, count: int = 5) -> str:
        client = WebSearchClient()
        result = client.search(query=query, count=count)
        return json.dumps(result, ensure_ascii=False)


class POISearchTool(Tool):
    name = "poi_search"
    description = "搜索指定地点的 POI 信息（餐厅、景点等）"
    
    def __init__(self, amap_client: AMapClient):
        self._amap_client = amap_client
    
    async def _run(self, keywords: str, city: Optional[str] = None) -> str:
        result = self._amap_client.search_poi(keywords=keywords, city=city)
        return json.dumps(result, ensure_ascii=False)


_TOOLS_REGISTERED = False


def _ensure_tools_registered():
    """
    确保工具已注册（只在主进程中调用一次）
    
    注意：此函数应该在主进程中调用，而不是在子进程中调用。
    在多进程环境下，子进程会继承主进程的工具注册状态。
    """
    global _TOOLS_REGISTERED
    if _TOOLS_REGISTERED:
        return
    
    try:
        amap_client = AMapClient()
        ToolRegistry.register(WeatherTool(amap_client))
        ToolRegistry.register(SearchTool())
        ToolRegistry.register(POISearchTool(amap_client))
        _TOOLS_REGISTERED = True
        print(f"[ToolsAgent] [主进程] 已注册 {len(ToolRegistry.get_tools())} 个工具")
    except Exception as e:
        print(f"[ToolsAgent] [主进程] 工具注册失败：{e}")


class StateToolsProcessModule:
    """状态处理 Agent，负责人格、语气和情绪的联动更新。"""

    def __init__(self):
        self.llm_client = BaseLLMClient()
        self.persona_repo = PersonaRepository()

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
            persona_data["personality_weights"] = self._apply_steps(persona_data["personality_weights"], persona_step)
            persona_data["tone_weights"] = self._apply_steps(persona_data["tone_weights"], tone_step)
            self._update_persona_to_mongo(user_id, persona_data["personality_weights"], persona_data["tone_weights"])
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
            print(f"[StateTools] MongoDB 未找到 user_id={user_id} 的人格配置，已写入默认值")
            return default_data
        except Exception as e:
            print(f"[StateTools] MongoDB 加载人格配置失败：{e}，使用默认值")
            return self._default_persona_data()
    
    def _update_persona_to_mongo(self, user_id: str, personality_weights: Dict[str, float], tone_weights: Dict[str, float]):
        try:
            self.persona_repo.upsert(user_id, personality_weights, tone_weights)
            print(f"[StateTools] MongoDB 人格配置已更新: user_id={user_id}")
        except Exception as e:
            print(f"[StateTools] MongoDB 更新人格配置失败：{e}")
    
    # ==========================================
    # Context 对齐操作
    # ==========================================
    
    def _write_persona_to_context(self, context: Context, persona_data: Dict[str, Any]):
        """将人格配置写入 context.persona"""
        context.persona.update({
            "nickname": persona_data.get("nickname", ""),
            "custom_persona": persona_data.get("custom_persona", ""),
            "personality_weights": persona_data.get("personality_weights", {}),
            "tone_weights": persona_data.get("tone_weights", {}),
        })
    
    # ==========================================
    # LLM 情感分析与步长计算
    # ==========================================
    
    def _calculate_adjustment_steps(self, emotion: Dict[str, Any], user_input: str, short_history: List[Dict[str, Any]], current_personality: Dict[str, Any], current_tone: Dict[str, Any]) -> tuple[Dict[str, float], Dict[str, float]]:
        history_text = self._format_history(short_history)
        personality_list = ", ".join(current_personality.keys())
        tone_list = ", ".join(current_tone.keys())
        
        system_prompt = ADJUSTMENT_SYSTEM_PROMPT.format(
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
            result = _parse_json_response(response)
            
            if result:
                persona_step = self._filter_and_clip_steps(
                    result.get("persona_step", {}), current_personality
                )
                tone_step = self._filter_and_clip_steps(
                    result.get("tone_step", {}), current_tone
                )
                reason = result.get("reason", "")
                if reason:
                    print(f"[StateTools] 调整原因：{reason}")
                return persona_step, tone_step
        
        except Exception as e:
            print(f"[StateTools] LLM 计算微调步长失败：{e}，使用默认步长")
        
        return self._default_steps(emotion, current_personality, current_tone)
    
    def _default_steps(self, emotion: Dict[str, Any], current_personality: Dict[str, Any], current_tone: Dict[str, Any]) -> tuple[Dict[str, float], Dict[str, float]]:
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
    
    def _save_steps_to_redis(self, user_id: str, persona_step: Dict[str, float], tone_step: Dict[str, float]):
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
                    persona_key, REDIS_EXPIRE,
                    json.dumps(step_data, ensure_ascii=False),
                )
                
                print(f"[StateTools] 微调步长已存入 Redis: user_id={user_id}")
                print(f"  人格步长: {persona_step}")
                print(f"  语气步长: {tone_step}")
        
        except Exception as e:
            print(f"[StateTools] Redis 存入微调步长失败：{e}")
    
    # ==========================================
    # 工具方法
    # ==========================================
    
    def _check_threshold(self, persona_step: Dict[str, float], tone_step: Dict[str, float]) -> bool:
        for v in persona_step.values():
            if abs(v) >= PERSONA_UPDATE_THRESHOLD:
                return True
        
        for v in tone_step.values():
            if abs(v) >= TONE_UPDATE_THRESHOLD:
                return True
        
        return False
    
    def _apply_steps(self, current_weights: Dict[str, float], steps: Dict[str, float]) -> Dict[str, float]:
        return {
            key: round(max(0.0, current_weights.get(key, 0.0) + steps.get(key, 0.0)), 4)
            for key in current_weights
        }
    
    def _filter_and_clip_steps(self, raw_steps: Dict[str, Any], valid_keys: Dict[str, Any]) -> Dict[str, float]:
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


class ToolsAgent:
    """工具调用 Agent，负责工具决策与执行。"""

    def __init__(self):
        self.llm_client = BaseLLMClient()

    def process(self, context: Context, shared_dict: Optional[Any] = None) -> Context:
        user_input = context.user_input or context.raw_input
        tools_info = self._get_tools_info()
        decision = self._decide_tool_call(user_input, tools_info)
        if decision.get("need_tool", False):
            tool_name = decision.get("tool_name", "")
            tool_params = decision.get("tool_params", {})
            if tool_name and tool_params:
                tool_result = self._execute_tool(tool_name, tool_params)
                if tool_result:
                    validated_result = self._validate_tool_result_json(tool_result)
                    context.tools["results"].append({"tool_name": tool_name, "result": validated_result})
                    print(f"[ToolsAgent] 工具 {tool_name} 调用成功，结果已写入 context")
        if shared_dict is not None:
            shared_dict["tools_done"] = True
            shared_dict["tool_results"] = list(context.tools["results"])
        return context
    
    def _get_tools_info(self) -> str:
        tools = ToolRegistry.get_tools()
        if not tools:
            return "无可用工具"
        
        parts = [f"- {tool['name']}: {tool['description']}" for tool in tools]
        return "\n".join(parts)
    
    def _decide_tool_call(self, user_input: str, tools_info: str) -> Dict[str, Any]:
        system_prompt = TOOL_DECISION_PROMPT.format(
            tools_info=tools_info,
            user_input=user_input,
        )
        
        try:
            response = self.llm_client.chat_with_prompt(
                prompt=f"用户输入：{user_input}",
                system_message=system_prompt,
            )
            result = _parse_json_response(response)
            
            if result:
                print(f"[ToolsAgent] 工具决策：need_tool={result.get('need_tool', False)}, reason={result.get('reason', '')}")
                return result
        
        except Exception as e:
            print(f"[ToolsAgent] LLM 工具决策失败：{e}")
        
        return {"need_tool": False, "tool_name": "", "tool_params": {}, "reason": "决策失败，默认不调用"}
    
    def _execute_tool(self, tool_name: str, tool_params: Dict[str, Any]) -> Optional[str]:
        try:
            return asyncio.run(
                ToolRegistry.execute(tool_name, **tool_params)
            )
        
        except Exception as e:
            print(f"[ToolsAgent] 工具 {tool_name} 执行失败：{e}")
            return None
    
    def _validate_tool_result_json(self, result_str: str) -> Dict[str, Any]:
        if not result_str:
            return {"success": False, "error": "工具返回结果为空"}
        
        result_str = result_str.strip()
        if result_str.startswith("```"):
            lines = result_str.split("\n")
            result_str = "\n".join(lines[1:-1]) if len(lines) > 2 else result_str.strip("`")
        
        try:
            parsed = json.loads(result_str)
            if isinstance(parsed, dict):
                return parsed
            return {"success": True, "data": parsed}
        
        except json.JSONDecodeError:
            print(f"[ToolsAgent] 工具结果 JSON 格式无效，已包装为标准格式")
            return {
                "success": True,
                "raw_result": result_str[:2000],
                "format_warning": "原始结果非 JSON 格式，已包装"
            }


def _run_state_process(context_data: Dict[str, Any], shared_dict: Any):
    try:
        context = _build_context_from_data(context_data)
        module = StateToolsProcessModule()
        module.process(context, shared_dict)
    
    except Exception as e:
        print(f"[StateTools] 多进程状态处理失败：{e}")
        shared_dict["persona_done"] = True
        shared_dict["persona_error"] = str(e)


def _run_tools_process(context_data: Dict[str, Any], shared_dict: Any):
    try:
        context = _build_context_from_data(context_data)
        agent = ToolsAgent()
        agent.process(context, shared_dict)
    
    except Exception as e:
        print(f"[ToolsAgent] 多进程工具处理失败：{e}")
        shared_dict["tools_done"] = True
        shared_dict["tools_error"] = str(e)


def process_state_tools(context: Context) -> Context:
    # 步骤1：在主进程中预先注册工具
    _ensure_tools_registered()
    
    context_data = {
        "user_id": context.user_id,
        "user_input": context.user_input,
        "raw_input": context.raw_input,
        "emotion": context.emotion,
        "memory": dict(context.memory),
        "persona": dict(context.persona),
    }
    
    with Manager() as manager:
        shared_dict = manager.dict()
        shared_dict["persona_done"] = False
        shared_dict["tools_done"] = False
        
        p_state = multiprocessing.Process(
            target=_run_state_process,
            args=(context_data, shared_dict),
            name="StateProcess"
        )
        p_tools = multiprocessing.Process(
            target=_run_tools_process,
            args=(context_data, shared_dict),
            name="ToolsProcess"
        )
        
        p_state.start()
        p_tools.start()
        
        p_state.join(timeout=30)
        p_tools.join(timeout=30)
        
        if p_state.is_alive():
            print("[StateTools] 状态处理超时，强制终止")
            p_state.terminate()
            p_state.join()
        
        if p_tools.is_alive():
            print("[ToolsAgent] 工具处理超时，强制终止")
            p_tools.terminate()
            p_tools.join()
        
        # 必须在 with Manager() 块内读取 shared_dict
        if "persona_data" in shared_dict:
            context.persona.update(shared_dict["persona_data"])

        if "tool_results" in shared_dict:
            context.tools["results"].extend(shared_dict["tool_results"])

    return context
