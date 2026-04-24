from __future__ import annotations

"""
输入处理模块 (Input Process Module)

负责：
1. 判断用户输入是否需要扩写、是否需要召回记忆（统一由一个 Agent 判断）
2. 召回短期记忆（Redis）和长期记忆（Milvus）
3. 精炼记忆关键信息并扩写问题（统一由一个 Agent 处理）
4. 将扩写结果和精炼记忆写入 Context
"""

from typing import Optional, List, Dict, Any, Tuple
import json

try:
    import tiktoken  # type: ignore
except Exception:  # pragma: no cover - fallback for incompatible runtime/deps
    tiktoken = None

from ..Tools.BaseLLM import BaseLLMClient
from ..database.repositories import ConversationRepository, MemoryRepository
from ..database.memory_decay import MemoryDecayModule
from ..core.context import Context


class InputProcessModule:
    """输入处理模块，负责记忆召回、问题扩写与情绪前置分析。"""

    TOKEN_LIMIT = 120000
    MAX_SHORT_HISTORY = 5
    MAX_LONG_MEMORIES = 3
    
    PRONOUNS = ["这个", "那个", "这些", "那些", "他", "她", "它", "他们", "她们", "它们", 
                "此", "该", "其", "上述", "以下", "前面", "刚才", "上次"]
    
    RECALL_KEYWORDS = ["上次", "之前", "还记得", "说过", "提到", "之前聊", "之前说",
                       "继续", "接着", "后来", "后来呢", "然后呢",
                       "喜欢", "讨厌", "习惯", "偏好", "经常", "总是", "以前", "曾经"]
    
    EMOTION_LABELS = "positive（积极/开心）、negative（消极/不满）、neutral（中性）、anxious（焦虑/急切）、angry（生气/愤怒）、confused（困惑/迷茫）"
    
    JUDGE_PROMPT = """你是一个意图分析助手。请分析用户输入，并回答两个问题：

1. 是否需要召回历史记忆？（需要结合历史对话才能准确回答）
   需要的情况：提到过去对话、询问偏好/习惯、追问之前话题、包含指代词需要上下文
   不需要的情况：独立问题、闲聊问候、全新话题切换

2. 是否需要扩写用户输入？（输入是否完整明确）
   需要的情况：输入简短、包含指代词、上下文依赖强、意图不明确
   不需要的情况：输入完整明确、可以独立理解

请严格按照以下 JSON 格式返回，不要添加其他内容：
{{"need_recall": true/false, "need_expansion": true/false}}"""

    EXPAND_PROMPT = """你是一个对话分析助手。请完成三个任务：

任务1：精炼短期对话历史
- 保留事实性信息（用户偏好、需求、约束等）
- 保留任务相关进度
- 去除问候、感谢、闲聊等无实质内容的对话
- 保持原始角色信息（user/assistant）

任务2：根据对话历史和记忆，扩写用户当前问题
- 补全省略的主语、宾语等成分
- 明确指代词的具体所指
- 保持原意不变
- 使问题可以独立理解（不依赖上下文）

任务3：分析用户当前情绪
结合短期对话历史和当前输入，分析用户的情绪状态。
情绪类型参考：{emotion_labels}
情绪强度：0.1~1.0，数值越高情绪越强烈

请严格按照以下 JSON 格式返回，不要添加其他内容：
{{
  "refined_history": [
    {{"role": "user", "content": "精炼后的用户发言"}},
    {{"role": "assistant", "content": "精炼后的助手回复"}}
  ],
  "expanded_query": "扩写后的完整问题",
  "emotion": {{
    "label": "情绪类型",
    "score": 0.5
  }}
}}

注意：
- 如果对话历史已经足够精炼，可以保持原样
- 如果问题已经很完整明确，expanded_query 可以与原问题相同
- refined_history 可以为空数组（如果没有需要保留的历史）"""

    EMOTION_PROMPT = """你是一个情绪分析助手。分析用户输入的情绪状态。
情绪类型参考：{emotion_labels}
情绪强度：0.1~1.0，数值越高情绪越强烈

请严格按照以下 JSON 格式返回：
{{"label": "情绪类型", "score": 强度值}}"""

    COMPRESS_PROMPT = """你是一个记忆压缩助手。将多轮对话压缩成简洁的摘要，保留关键信息。
要求：
1. 简洁明了（100 字以内）
2. 保留关键事实和信息
3. 去除冗余和重复
4. 保持语义完整
直接返回压缩后的文本，不要使用JSON格式。"""
    
    def __init__(self):
        self.llm_client = BaseLLMClient()
        self._tiktoken_encoder = None
        self.conversation_repo = ConversationRepository()
        self.memory_repo = MemoryRepository()
    
    def _get_tiktoken_encoder(self):
        if tiktoken is None:
            return None
        if self._tiktoken_encoder is None:
            try:
                self._tiktoken_encoder = tiktoken.encoding_for_model("gpt-3.5-turbo")
            except Exception:
                self._tiktoken_encoder = tiktoken.get_encoding("cl100k_base")
        return self._tiktoken_encoder
    
    def _count_tokens(self, text: str) -> int:
        if not text:
            return 0
        try:
            encoder = self._get_tiktoken_encoder()
            if encoder is not None:
                return len(encoder.encode(text))
        except Exception:
            pass
        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        other_chars = len(text) - chinese_chars
        return int(chinese_chars / 1.5 + other_chars / 4)
    
    def _parse_json_response(self, response: str) -> Optional[Dict[str, Any]]:
        response = response.strip()
        if response.startswith("```"):
            lines = response.split("\n")
            response = "\n".join(lines[1:-1]) if len(lines) > 2 else response.strip("`")
        try:
            return json.loads(response)
        except Exception:
            return None
    
    def _normalize_emotion(self, emotion_data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        default = {"label": "neutral", "score": 0.5}
        if not emotion_data:
            return default
        try:
            return {
                "label": emotion_data.get("label", "neutral"),
                "score": min(1.0, max(0.1, float(emotion_data.get("score", 0.5))))
            }
        except (ValueError, TypeError):
            return default
    
    def _format_history_text(
        self,
        short_history: Optional[List[Dict[str, Any]]] = None,
        long_memories: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        parts = []
        
        if short_history:
            for msg in short_history:
                role = msg.get("role", "unknown")
                content = msg.get("content", "")
                parts.append(f"{role}: {content}")
        
        if long_memories:
            for mem in long_memories:
                parts.append(mem.get("content", ""))
        
        return "\n".join(parts)
    
    def _call_llm_text(self, user_prompt: str, system_prompt: str) -> Optional[str]:
        try:
            return self.llm_client.chat_with_prompt(
                prompt=user_prompt,
                system_message=system_prompt
            ).strip()
        except Exception:
            return None
    
    def _call_llm_json(self, user_prompt: str, system_prompt: str) -> Optional[Dict[str, Any]]:
        text = self._call_llm_text(user_prompt, system_prompt)
        return self._parse_json_response(text) if text else None
    
    def process(self, user_id: str, query: str, context: Context) -> Context:
        context.raw_input = query
        context.user_id = user_id

        need_recall, need_expansion = self._unified_judge(query)
        
        short_history: List[Dict[str, Any]] = []
        long_memories: List[Dict[str, Any]] = []
        
        if need_recall:
            short_history = self._get_redis_history(user_id)
            long_memories = self._search_milvus_memories(user_id, query)
        
        if need_expansion:
            all_memories = short_history + long_memories
            if all_memories:
                expanded_query, refined_short_history, emotion = self._refine_and_expand(
                    query, short_history, long_memories
                )
                context.user_input = expanded_query
                if refined_short_history:
                    context.memory["short_history"] = refined_short_history
                if long_memories:
                    context.memory["long_retrieved"] = long_memories
            else:
                context.user_input = query
                emotion = self._analyze_emotion(query)
        else:
            context.user_input = query
            emotion_context = self._format_history_text(short_history=short_history) if short_history else None
            emotion = self._analyze_emotion(query, emotion_context)
            if short_history:
                context.memory["short_history"] = short_history
            if long_memories:
                context.memory["long_retrieved"] = long_memories
        
        context.emotion = emotion
        
        if self._should_compress(context):
            all_memories = context.memory.get("short_history", []) + context.memory.get("long_retrieved", [])
            if all_memories:
                compressed = self._compress_memories(all_memories)
                context.memory["compressed"] = compressed
                context.memory["short_history"] = [{"role": "system", "content": f"历史对话摘要：{compressed}"}]
                context.memory["long_retrieved"] = []

        return context
    
    def _unified_judge(self, query: str) -> tuple[bool, bool]:
        query = query.strip()
        need_recall_keywords = False
        need_expansion_keywords = False
        
        if len(query) >= 5:
            for keyword in self.RECALL_KEYWORDS:
                if keyword in query:
                    need_recall_keywords = True
                    break
            
            if len(query) <= 20:
                for pronoun in self.PRONOUNS:
                    if pronoun in query:
                        need_expansion_keywords = True
                        break
        
        if len(query) < 5:
            return True, True
        
        if len(query) > 50 and not need_recall_keywords and not need_expansion_keywords:
            return False, False
        
        result = self._call_llm_json(
            user_prompt=f"用户输入：{query}",
            system_prompt=self.JUDGE_PROMPT
        )
        
        if result:
            return bool(result.get("need_recall", False)), bool(result.get("need_expansion", False))
        
        return need_recall_keywords, (need_expansion_keywords or len(query) < 10)
    
    def _should_compress(self, context: Context) -> bool:
        total_text = context.build_prompt()
        return self._count_tokens(total_text) > self.TOKEN_LIMIT
    
    def _analyze_emotion(
        self,
        query: str,
        context_text: Optional[str] = None
    ) -> Dict[str, Any]:
        emotion_prompt = self.EMOTION_PROMPT.format(emotion_labels=self.EMOTION_LABELS)
        user_prompt = f"用户输入：{query}"
        if context_text:
            user_prompt = f"短期对话历史：\n{context_text}\n\n{user_prompt}"
        
        result = self._call_llm_json(user_prompt, emotion_prompt)
        return self._normalize_emotion(result)
    
    def _refine_and_expand(
        self,
        query: str,
        short_history: List[Dict[str, Any]],
        long_memories: List[Dict[str, Any]]
    ) -> tuple[str, Optional[List[Dict[str, Any]]], Dict[str, Any]]:
        history_text = self._format_history_text(short_history=short_history, long_memories=long_memories)
        
        system_prompt = self.EXPAND_PROMPT.format(emotion_labels=self.EMOTION_LABELS)
        user_prompt = f"短期对话历史：\n{history_text}\n\n用户当前问题：{query}\n\n请精炼历史、扩写问题并分析情绪："
        
        result = self._call_llm_json(user_prompt, system_prompt)
        
        if result:
            expanded_query = result.get("expanded_query", query)
            
            refined_history = result.get("refined_history", [])
            if isinstance(refined_history, list) and refined_history:
                refined_history = [
                    {"role": item["role"], "content": item["content"]}
                    for item in refined_history
                    if isinstance(item, dict) and "role" in item and "content" in item
                ]
            
            emotion = self._normalize_emotion(result.get("emotion"))
            
            return expanded_query, refined_history if refined_history else None, emotion
        
        return query, None, {"label": "neutral", "score": 0.5}
    
    def _get_redis_history(self, user_id: str) -> List[Dict[str, Any]]:
        try:
            return self.conversation_repo.get_recent(user_id, self.MAX_SHORT_HISTORY)
        except Exception as e:
            print(f"Redis 获取失败：{e}")
            return []
    
    def _calculate_composite_score(
        self,
        semantic_score: float,
        weight: float,
        semantic_weight: float = 0.8,
        memory_weight_ratio: float = 0.2,
    ) -> float:
        normalized_weight = weight / 5.0
        return semantic_score * semantic_weight + normalized_weight * memory_weight_ratio
    
    def _rerank_memories(self, memories: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not memories:
            return memories
        
        scored_memories = []
        for memory in memories:
            composite_score = self._calculate_composite_score(
                semantic_score=memory.get("score", 0.0),
                weight=memory.get("weight", 0.0)
            )
            memory_with_score = memory.copy()
            memory_with_score["composite_score"] = composite_score
            scored_memories.append(memory_with_score)
        
        return sorted(scored_memories, key=lambda x: x.get("composite_score", 0.0), reverse=True)
    
    def _search_milvus_memories(self, user_id: str, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        try:
            results = self.memory_repo.search(query=query, top_k=top_k * 2, filters={"user_id": user_id} if user_id else None)
            memories = []
            for result in results:
                metadata = result.get("metadata", {})
                memories.append({
                    "role": "memory",
                    "content": result.get("content", ""),
                    "score": result.get("score", 0.0),
                    "weight": metadata.get("weight", 0.0),
                    "create_time": metadata.get("create_time", 0.0),
                    "metadata": metadata,
                })
            if not memories:
                print(f"[Milvus 检索] user_id={user_id}, query={query}, 未找到记忆")
                return []
            final_memories = self._rerank_memories(memories)[:top_k]
            self._reinforce_selected_memories(final_memories)
            print(f"[Milvus 检索] user_id={user_id}, query={query}, 找到 {len(memories)} 条记忆，重排后返回 {len(final_memories)} 条")
            return final_memories
        except Exception as e:
            print(f"Milvus 检索失败：{e}")
            return []
    
    def _reinforce_selected_memories(self, final_memories: List[Dict[str, Any]]):
        try:
            decay_module = MemoryDecayModule()
            for mem in final_memories:
                memory_id = mem.get("metadata", {}).get("id")
                current_weight = mem.get("weight", 0.0)
                if memory_id is not None:
                    new_weight = decay_module.reinforce_on_retrieval(memory_id, current_weight)
                    mem["weight"] = new_weight
        
        except Exception as e:
            print(f"[记忆强化] 处理失败: {e}")
    
    def _compress_memories(self, memories: List[Dict[str, Any]]) -> str:
        if not memories:
            return ""
        memory_text = self._format_history_text(short_history=memories)
        compressed = self._call_llm_text(user_prompt=f"请压缩以下对话：\n{memory_text}", system_prompt=self.COMPRESS_PROMPT)
        return compressed if compressed else memory_text[:200]


    def _recall_memories(self, user_id: str, query: str, need_recall: bool) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        if not need_recall:
            return [], []
        return self._get_redis_history(user_id), self._search_milvus_memories(user_id, query)

    def _build_user_state(
        self,
        query: str,
        short_history: List[Dict[str, Any]],
        long_memories: List[Dict[str, Any]],
        need_expansion: bool,
    ) -> tuple[str, Dict[str, Any]]:
        if need_expansion and (short_history or long_memories):
            expanded_query, refined_short_history, emotion = self._refine_and_expand(query, short_history, long_memories)
            if refined_short_history:
                short_history = refined_short_history
            return expanded_query, emotion
        emotion_context = self._format_history_text(short_history=short_history) if short_history else None
        return query, self._analyze_emotion(query, emotion_context)

    def _maybe_compress(self, context: Context) -> None:
        if not self._should_compress(context):
            return
        all_memories = context.memory.get("short_history", []) + context.memory.get("long_retrieved", [])
        if not all_memories:
            return
        compressed = self._compress_memories(all_memories)
        context.memory["compressed"] = compressed
        context.memory["short_history"] = [{"role": "system", "content": f"历史对话摘要：{compressed}"}]
        context.memory["long_retrieved"] = []


def process_input(user_id: str, query: str, context: Context) -> Context:
    module = InputProcessModule()
    return module.process(user_id, query, context)
