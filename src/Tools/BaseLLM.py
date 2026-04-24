import os
from typing import Optional

try:
    from langchain_openai import ChatOpenAI  # type: ignore
except Exception:  # pragma: no cover - fallback for incompatible runtime/deps
    ChatOpenAI = None

try:
    from langchain_core.messages import HumanMessage, SystemMessage, AIMessage  # type: ignore
except Exception:  # pragma: no cover - fallback for incompatible runtime/deps
    class _Msg:
        def __init__(self, content):
            self.content = content

    class HumanMessage(_Msg):
        pass

    class SystemMessage(_Msg):
        pass

    class AIMessage(_Msg):
        pass


class BaseLLMClient:
    """
    基础 LLM Client 类，基于 LangChain 实现
    用于创建和管理大语言模型客户端，支持通过环境变量获取 API key
    """
    
    def __init__(
        self,
        system_prompt: Optional[str] = None,
        **kwargs
    ):
        """
        初始化 BaseLLMClient
        
        Args:
            system_prompt: 系统提示词，用于设置 LLM 的角色和行为
            **kwargs: 其他可选参数 (model, temperature, max_tokens 等)
        """
        self.system_prompt = system_prompt
        
        self.model = kwargs.get("model", "qwen-max")
        self.temperature = kwargs.get("temperature", 0.7)
        self.max_tokens = kwargs.get("max_tokens", 120000)
        self.top_p = kwargs.get("top_p", 0.9)
        
        api_key = kwargs.get("api_key") or os.getenv("DASHSCOPE_API_KEY")
        
        self.llm = None
        if ChatOpenAI is not None:
            self.llm = ChatOpenAI(
                model=self.model,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                api_key=api_key,
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            )
    
    def chat(
        self,
        messages: list,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> str:
        """
        发送聊天请求并获取响应
        
        Args:
            messages: 消息列表，支持字典格式 [{"role": "user/assistant/system", "content": "..."}]
                     或 LangChain 消息对象
            system_prompt: 系统提示词，如果提供则覆盖初始化时的 system_prompt
            **kwargs: 其他传递给 LLM 的参数
        
        Returns:
            模型响应的文本内容
        """
        effective_system_prompt = system_prompt if system_prompt is not None else self.system_prompt
        
        langchain_messages = []
        
        if effective_system_prompt:
            langchain_messages.append(SystemMessage(content=effective_system_prompt))
        
        role_map = {
            "user": HumanMessage,
            "assistant": AIMessage,
            "system": SystemMessage
        }
        
        for msg in messages:
            if isinstance(msg, dict):
                msg_class = role_map.get(msg["role"])
                if msg_class:
                    langchain_messages.append(msg_class(content=msg["content"]))
            else:
                langchain_messages.append(msg)
        
        if self.llm is None:
            return ""
        response = self.llm.invoke(langchain_messages, **kwargs)
        return response.content
    
    def chat_with_prompt(
        self,
        prompt: str,
        system_message: Optional[str] = None,
        **kwargs
    ) -> str:
        """
        使用提示词进行聊天
        
        Args:
            prompt: 用户提示词
            system_message: 系统消息，用于设置角色或行为
            **kwargs: 其他传递给 chat 方法的参数
        
        Returns:
            模型响应的文本内容
        """
        messages = [HumanMessage(content=prompt)]
        return self.chat(messages, system_prompt=system_message, **kwargs)
    
    def count_tokens(self, text: str) -> int:
        """
        快速估算 Token 数量
        
        Args:
            text: 输入文本
        
        Returns:
            估算的 Token 数量（中文约 1.5 字/token，英文约 4 字符/token）
        """
        if not text:
            return 0
        
        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        other_chars = len(text) - chinese_chars
        
        return int(chinese_chars / 1.5 + other_chars / 4)
