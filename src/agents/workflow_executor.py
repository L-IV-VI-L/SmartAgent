from __future__ import annotations

"""工作流执行器 - 统一管理四大工作流的执行流程。"""

import logging
from typing import Callable, Dict, List, Optional

from src.core.context import Context
from src.agents.scene_classifier import SceneClassifier
from src.agents.input_agents import ContextBuildAgent, MainlineMemoryAgent
from src.agents.tool_agents import ToolPlanAgent, ToolExecuteAgent
from src.agents.response_agents import ResponseAgent
from src.agents.memory_agents import LongMemoryExtractAgent
from src.agents.base import BaseAgent
from src.agents.workflow_dependencies import WorkflowDependencies
from src.agents.emotion_state_agent import EmotionStateAgent
from src.InputProcess.retrieval_strategies import (
    RetrievalStrategy,
    STANDARD_STRATEGY,
    TASK_STRATEGY,
    EMOTION_STRATEGY,
    KNOWLEDGE_STRATEGY,
)

logger = logging.getLogger(__name__)

WORKFLOW_CONFIGS = {
    "standard": {
        "strategy": STANDARD_STRATEGY,
        "agents": ["context_build", "emotion_state", "tool_plan", "tool_execute", "response"],
    },
    "task": {
        "strategy": TASK_STRATEGY,
        "agents": ["context_build", "emotion_state", "tool_plan", "tool_execute", "response"],
    },
    "emotion": {
        "strategy": EMOTION_STRATEGY,
        "agents": [
            "context_build",
            "emotion_state",
            "tool_plan",
            "tool_execute",
            "response",
            "mainline_memory",
        ],
    },
    "knowledge": {
        "strategy": KNOWLEDGE_STRATEGY,
        "agents": [
            "context_build",
            "emotion_state",
            "tool_plan",
            "tool_execute",
            "response",
            "long_memory_extract",
        ],
    },
}


class WorkflowExecutor:
    """工作流执行器。

    根据场景分类器返回的策略自动构建并执行对应的 Agent 序列。
    """

    def __init__(
        self,
        classifier: Optional[SceneClassifier] = None,
        dependencies: Optional[WorkflowDependencies] = None,
        agent_factory: Optional[Dict[str, Callable[[], BaseAgent]]] = None,
    ):
        self.classifier = classifier or SceneClassifier()
        self.dependencies = dependencies or WorkflowDependencies()
        self.agent_factory = agent_factory or self._build_default_agent_factory()

    def _build_default_agent_factory(self) -> Dict[str, Callable[[], BaseAgent]]:
        """创建默认的 Agent 工厂函数。

        注意：context_build Agent 不在工厂中创建，因为它需要动态接收
        场景分类器返回的检索策略。请使用 _create_agent() 方法创建所有 Agent。
        """
        deps = self.dependencies
        factory: Dict[str, Callable[[], BaseAgent]] = {}

        def _format_history_text(short_history=None):
            """辅助函数：格式化历史记录为文本。"""
            from src.agents.workflow_dependencies import format_history_text as _fmt
            return _fmt(short_history=short_history)

        factory["emotion_state"] = lambda: EmotionStateAgent()
        factory["tool_plan"] = lambda: ToolPlanAgent()
        factory["tool_execute"] = lambda: ToolExecuteAgent()
        factory["response"] = lambda: ResponseAgent()
        factory["mainline_memory"] = lambda: MainlineMemoryAgent(
            mainline_memory_updater=deps.mainline_memory_updater,
            memory_compressor=deps.memory_compressor,
        )
        factory["long_memory_extract"] = lambda: LongMemoryExtractAgent()

        return factory

    def execute(self, context: Context) -> Context:
        """执行完整的工作流。

        Args:
            context: 包含用户输入的上下文对象。

        Returns:
            执行完成后的上下文对象。
        """
        try:
            user_input = context.raw_input or context.user_input
            if not user_input:
                logger.warning("用户输入为空，跳过工作流执行")
                return context

            strategy = self.classifier.classify(user_input)
            workflow_name = self._identify_workflow(strategy)

            logger.info("开始执行工作流: %s", workflow_name)
            config = WORKFLOW_CONFIGS.get(workflow_name, WORKFLOW_CONFIGS["standard"])

            for agent_name in config["agents"]:
                try:
                    agent = self._create_agent(agent_name, strategy)
                    if agent is not None:
                        context = agent.run(context)
                    else:
                        logger.warning("Agent 创建失败: %s，跳过", agent_name)
                except Exception as e:
                    logger.warning("Agent %s 执行失败，跳过: %s", agent_name, e)
                    continue

            logger.info("工作流 %s 执行完成", workflow_name)
            return context

        except Exception as e:
            logger.error("工作流执行失败: %s", e)
            return context

    def _create_agent(self, agent_name: str, strategy: RetrievalStrategy) -> Optional[BaseAgent]:
        """根据 Agent 名称和策略创建 Agent 实例。

        Args:
            agent_name: Agent 的名称。
            strategy: 检索策略。

        Returns:
            创建的 Agent 实例，失败时返回 None。
        """
        deps = self.dependencies

        if agent_name == "context_build":
            return ContextBuildAgent(
                query_expander=deps.query_expander,
                memory_retriever=deps.memory_retriever,
                retrieval_strategy=strategy,
            )

        factory_func = self.agent_factory.get(agent_name)
        if factory_func is not None:
            return factory_func()

        logger.warning("未知 Agent: %s", agent_name)
        return None

    def _identify_workflow(self, strategy: RetrievalStrategy) -> str:
        """根据检索策略识别对应的工作流名称。"""
        if strategy is STANDARD_STRATEGY:
            return "standard"
        elif strategy is TASK_STRATEGY:
            return "task"
        elif strategy is EMOTION_STRATEGY:
            return "emotion"
        elif strategy is KNOWLEDGE_STRATEGY:
            return "knowledge"
        else:
            logger.warning("未识别的检索策略，使用标准对话工作流")
            return "standard"
