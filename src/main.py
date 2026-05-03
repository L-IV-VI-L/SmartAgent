from __future__ import annotations

"""SmartAgent 统一入口点。

提供面向 API 封装的智能 Agent 调用接口，
为后续 FastAPI 服务层做好准备。
"""

import asyncio
import logging
import time
from typing import Any, Dict, Optional

from src.core.context import Context
from src.agents.workflow_executor import WorkflowExecutor
from src.agents.scene_classifier import SceneClassifier
from src.agents.workflow_dependencies import WorkflowDependencies

logger = logging.getLogger(__name__)


class SmartAgentAPI:
    """面向 API 封装的智能 Agent 入口。
    
    该类是无状态的，每次请求独立处理。
    所有状态保存在 Context 对象中，由数据库层持久化。
    
    使用示例:
        api = SmartAgentAPI()
        result = await api.process_message(
            user_id="123",
            message="你好",
            session_id="session_001"
        )
    """

    def __init__(
        self,
        workflow_executor: Optional[WorkflowExecutor] = None,
    ):
        """初始化 API 入口点。
        
        Args:
            workflow_executor: 工作流执行器实例。
                如果为 None，将使用默认配置创建。
        """
        self.workflow_executor = workflow_executor or WorkflowExecutor()
        logger.info("SmartAgentAPI 初始化完成")

    async def process_message(
        self,
        user_id: str,
        message: str,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """处理用户消息，返回结构化响应。
        
        这是未来 FastAPI 路由的直接调用目标。
        
        Args:
            user_id: 用户唯一标识。
            message: 用户输入的消息。
            session_id: 会话 ID，可选。如果为 None，将使用 user_id。
        
        Returns:
            结构化响应字典，包含:
            - success: 是否成功
            - user_id: 用户 ID
            - session_id: 会话 ID
            - response: AI 回复内容
            - emotion: 当前情绪分析结果
            - state: 用户状态
            - tool_results: 工具调用结果
            - processing_time: 处理耗时（秒）
            
            失败时返回:
            - success: False
            - error: 错误信息
            - error_type: 异常类型
            - processing_time: 处理耗时
        """
        start_time = time.time()
        
        try:
            logger.info("收到消息: user_id=%s, session_id=%s", user_id, session_id or user_id)
            
            # 1. 构建 Context
            context = Context(user_id=user_id, session_id=session_id)
            context.raw_input = message
            context.user_input = message
            
            # 2. 执行工作流
            result_context = self.workflow_executor.execute(context)
            
            # 3. 计算耗时
            processing_time = time.time() - start_time
            
            # 4. 构建结构化响应
            response = {
                "success": True,
                "user_id": user_id,
                "session_id": result_context.session_id or user_id,
                "response": result_context.response_text or "",
                "emotion": result_context.emotion.get("label", "neutral"),
                "state": result_context.persona,
                "tool_results": result_context.tools.get("results", []),
                "processing_time": round(processing_time, 3),
            }
            
            logger.info(
                "消息处理完成: user_id=%s, 耗时=%.3fs, 回复长度=%d",
                user_id,
                processing_time,
                len(response["response"]),
            )
            
            return response
            
        except Exception as e:
            processing_time = time.time() - start_time
            
            logger.error("消息处理失败: user_id=%s, 错误=%s", user_id, e)
            
            return {
                "success": False,
                "user_id": user_id,
                "session_id": session_id or user_id,
                "response": "",
                "error": str(e),
                "error_type": type(e).__name__,
                "processing_time": round(processing_time, 3),
            }

    def process_message_sync(
        self,
        user_id: str,
        message: str,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """同步版本的消息处理接口。
        
        适用于非异步环境（如脚本测试）。
        
        Args:
            user_id: 用户唯一标识。
            message: 用户输入的消息。
            session_id: 会话 ID，可选。
        
        Returns:
            结构化响应字典。
        """
        return asyncio.get_event_loop().run_until_complete(
            self.process_message(user_id, message, session_id)
        )
