#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""集成测试脚本。

验证 4 个工作流都能通过统一入口点执行，以及降级策略是否正确工作。

用法：
    python scripts/test_integration.py
"""

from __future__ import annotations

import sys
import os
import asyncio

# 确保项目根目录在 sys.path 中
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)


def test_workflow_execution():
    """测试 4 个工作流通过 SmartAgentAPI 执行。"""
    print("\n" + "=" * 60)
    print("测试 1: 工作流执行测试")
    print("=" * 60)
    
    from src.main import SmartAgentAPI
    
    api = SmartAgentAPI()
    
    test_cases = [
        {
            "workflow": "standard",
            "message": "你好",
            "expected_scene": "标准对话",
        },
        {
            "workflow": "task",
            "message": "周末去哪玩",
            "expected_scene": "任务规划",
        },
        {
            "workflow": "emotion",
            "message": "今天心情不好",
            "expected_scene": "情感陪伴",
        },
        {
            "workflow": "knowledge",
            "message": "什么是量子计算",
            "expected_scene": "知识问答",
        },
    ]
    
    results = {}
    
    for test_case in test_cases:
        workflow_name = test_case["workflow"]
        message = test_case["message"]
        expected_scene = test_case["expected_scene"]
        
        print(f"\n正在测试 {workflow_name} 工作流 (预期场景: {expected_scene})...")
        print(f"  输入消息: {message}")
        
        try:
            result = api.process_message_sync(
                user_id="test_user_integration",
                message=message,
                session_id=f"session_{workflow_name}",
            )
            
            if result.get("success"):
                response_text = result.get("response", "")
                processing_time = result.get("processing_time", 0)
                emotion = result.get("emotion", "neutral")
                
                print(f"  [OK] {workflow_name} 工作流执行成功")
                print(f"  - 回复长度: {len(response_text)} 字符")
                print(f"  - 处理耗时: {processing_time:.3f}s")
                print(f"  - 情绪分析: {emotion}")
                if response_text:
                    print(f"  - 回复预览: {response_text[:50]}...")
                
                results[workflow_name] = True
            else:
                error = result.get("error", "未知错误")
                error_type = result.get("error_type", "未知")
                print(f"  [FAIL] {workflow_name} 工作流执行失败")
                print(f"  - 错误类型: {error_type}")
                print(f"  - 错误信息: {error}")
                results[workflow_name] = False
                
        except Exception as e:
            print(f"  [FAIL] {workflow_name} 工作流测试异常: {e}")
            results[workflow_name] = False
    
    return results


def test_fallback_strategy():
    """测试降级策略（Milvus 不可用时系统不崩溃）。"""
    print("\n" + "=" * 60)
    print("测试 2: 降级策略测试")
    print("=" * 60)
    
    print("\n说明: 由于 Milvus 服务已正常运行，此测试主要验证")
    print("      代码中的异常处理逻辑是否正确捕获并降级。")
    print("      实际降级测试需要停止 Milvus 服务后重新运行。")
    
    from src.InputProcess.memory_retriever import MemoryRetriever
    from src.database.repositories import ConversationRepository, MemoryRepository
    from src.InputProcess.retrieval_strategies import RetrievalStrategy
    
    retriever = MemoryRetriever(
        conversation_repo=ConversationRepository(),
        memory_repo=MemoryRepository(),
        max_short_history=10,
    )
    
    print("\n正在测试降级策略...")
    try:
        results = retriever.search_long_memories(
            user_id="test_user_fallback",
            query="测试降级策略",
            top_k=3,
            strategy=RetrievalStrategy(top_k=3),
        )
        print(f"[OK] 降级策略测试通过: 返回 {len(results)} 条结果")
        return True
    except Exception as e:
        print(f"[FAIL] 降级策略测试失败: {e}")
        return False


def main():
    print("=" * 60)
    print("SmartAgent 集成测试")
    print("=" * 60)
    
    workflow_results = test_workflow_execution()
    fallback_ok = test_fallback_strategy()
    
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    
    for workflow, success in workflow_results.items():
        status = "[OK]" if success else "[FAIL]"
        print(f"{workflow} 工作流: {status}")
    
    print(f"降级策略: {'[OK]' if fallback_ok else '[FAIL]'}")
    
    all_passed = all(workflow_results.values()) and fallback_ok
    
    if all_passed:
        print("\n[OK] 所有集成测试通过!")
        sys.exit(0)
    else:
        failed_workflows = [w for w, s in workflow_results.items() if not s]
        if failed_workflows:
            print(f"\n[FAIL] 以下工作流测试失败: {', '.join(failed_workflows)}")
        if not fallback_ok:
            print("[FAIL] 降级策略测试失败!")
        sys.exit(1)


if __name__ == "__main__":
    main()
