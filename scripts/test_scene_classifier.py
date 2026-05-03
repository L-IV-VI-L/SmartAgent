#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""场景分类器测试脚本。

验证场景分类器能否正确分类各类输入。

用法：
    python scripts/test_scene_classifier.py
"""

from __future__ import annotations

import sys
import os

# 确保项目根目录在 sys.path 中
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)


def test_scene_classifier():
    """测试场景分类器的分类准确度。"""
    print("\n" + "=" * 60)
    print("场景分类器测试")
    print("=" * 60)
    
    from src.agents.scene_classifier import SceneClassifier
    
    classifier = SceneClassifier()
    
    test_cases = [
        {
            "input": "你好",
            "expected": "standard",
            "description": "日常问候",
        },
        {
            "input": "今天天气怎么样",
            "expected": "task",
            "description": "查询实时信息",
        },
        {
            "input": "周末去哪玩",
            "expected": "task",
            "description": "推荐建议",
        },
        {
            "input": "帮我查一下去北京的高铁票",
            "expected": "task",
            "description": "任务规划",
        },
        {
            "input": "今天心情不好",
            "expected": "emotion",
            "description": "情感表达",
        },
        {
            "input": "我最近压力好大，感觉喘不过气来",
            "expected": "emotion",
            "description": "倾诉烦恼",
        },
        {
            "input": "什么是量子计算",
            "expected": "knowledge",
            "description": "知识问答",
        },
        {
            "input": "解释一下人工智能的原理",
            "expected": "knowledge",
            "description": "原理询问",
        },
        {
            "input": "吃饭了吗",
            "expected": "standard",
            "description": "日常闲聊",
        },
        {
            "input": "推荐一家好吃的餐厅",
            "expected": "task",
            "description": "推荐请求",
        },
    ]
    
    results = {}
    
    for test_case in test_cases:
        input_text = test_case["input"]
        expected = test_case["expected"]
        description = test_case["description"]
        
        print(f"\n正在测试: {description} (输入: {input_text})")
        
        try:
            strategy = classifier.classify(input_text)
            strategy_name = strategy.name if hasattr(strategy, "name") else str(strategy)
            
            # 从策略对象获取名称
            if hasattr(strategy, "__class__"):
                # 检查是否为 RetrievalStrategy 实例
                from src.InputProcess.retrieval_strategies import (
                    STANDARD_STRATEGY, TASK_STRATEGY, EMOTION_STRATEGY, KNOWLEDGE_STRATEGY
                )
                if strategy is STANDARD_STRATEGY:
                    strategy_name = "standard"
                elif strategy is TASK_STRATEGY:
                    strategy_name = "task"
                elif strategy is EMOTION_STRATEGY:
                    strategy_name = "emotion"
                elif strategy is KNOWLEDGE_STRATEGY:
                    strategy_name = "knowledge"
                else:
                    strategy_name = "unknown"
            
            is_correct = (strategy_name == expected)
            status = "[OK]" if is_correct else "[FAIL]"
            
            print(f"  {status} 预期: {expected}, 实际: {strategy_name}")
            
            results[input_text] = is_correct
            
        except Exception as e:
            print(f"  [FAIL] 测试异常: {e}")
            results[input_text] = False
    
    return results


def main():
    print("=" * 60)
    print("SmartAgent 场景分类器测试")
    print("=" * 60)
    
    results = test_scene_classifier()
    
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for input_text, is_correct in results.items():
        status = "[OK]" if is_correct else "[FAIL]"
        print(f"{status} {input_text}")
    
    print(f"\n通过率: {passed}/{total}")
    
    if passed == total:
        print("\n[OK] 所有分类测试通过!")
        sys.exit(0)
    else:
        failed = [k for k, v in results.items() if not v]
        print(f"\n[FAIL] 以下输入分类失败: {failed}")
        sys.exit(1)


if __name__ == "__main__":
    main()
