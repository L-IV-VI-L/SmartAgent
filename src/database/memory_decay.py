"""
长期记忆衰减管理模块 (Memory Decay Module)

职责：
1. 计算记忆随时间的指数衰减
2. 记忆被检索选中时自动强化权重
3. 定期清理低权重/过期记忆

衰减策略：
- 模式：指数衰减 W = W0 * 0.5^(t / T_half)
- 半衰期：30 天（可配置）
- 检索强化：每次被选中 +0.3 权重
- 清理阈值：权重 < 0.5 标记 inactive，< 0.1 直接删除
"""

import time
from typing import Optional, List, Dict, Any


class MemoryDecayConfig:
    """记忆衰减配置（集中管理所有参数）"""
    
    # ========== 衰减参数 ==========
    DECAY_MODE = "exponential"       # "exponential" / "linear" / "logarithmic"
    HALF_LIFE_DAYS = 30              # 半衰期（天）：权重降到一半需要的时间
    
    # ========== 权重阈值 ==========
    MIN_ACTIVE_WEIGHT = 0.5          # 低于此值标记为 inactive
    DELETE_WEIGHT = 0.1              # 低于此值直接删除
    MAX_WEIGHT = 5.0                 # 权重上限
    
    # ========== 强化参数 ==========
    REINFORCE_STEP = 0.3             # 每次被检索到增加的权重
    
    # ========== 清理参数 ==========
    INACTIVE_CLEANUP_DAYS = 7        # inactive 超过此天数直接删除
    
    # ========== 集合名称 ==========
    COLLECTION_NAME = "long_term_memory"


class MemoryDecayModule:
    """记忆衰减管理模块"""
    
    # ==========================================
    # 衰减计算核心方法
    # ==========================================
    
    @staticmethod
    def calculate_decay(
        current_weight: float,
        update_time: float,
        current_time: Optional[float] = None
    ) -> float:
        """
        计算衰减后的权重
        
        Args:
            current_weight: 当前权重
            update_time: 最后强化/更新时间戳
            current_time: 当前时间戳（默认使用 time.time()）
        
        Returns:
            衰减后的新权重
        """
        if current_time is None:
            current_time = time.time()
        
        days_since_update = (current_time - update_time) / 86400
        
        if days_since_update <= 0:
            return current_weight
        
        mode = MemoryDecayConfig.DECAY_MODE
        
        if mode == "exponential":
            decay_factor = 0.5 ** (days_since_update / MemoryDecayConfig.HALF_LIFE_DAYS)
            return current_weight * decay_factor
        
        elif mode == "linear":
            daily_decay = 0.02
            return max(0.0, current_weight - current_weight * daily_decay * days_since_update)
        
        elif mode == "logarithmic":
            return current_weight / (1 + 0.1 * days_since_update)
        
        else:
            return current_weight
    
    @staticmethod
    def reinforce_memory(current_weight: float, step: Optional[float] = None) -> float:
        """
        强化记忆权重（被检索到时调用）
        
        Args:
            current_weight: 当前权重
            step: 强化步长（默认使用配置值）
        
        Returns:
            强化后的新权重
        """
        if step is None:
            step = MemoryDecayConfig.REINFORCE_STEP
        
        return min(MemoryDecayConfig.MAX_WEIGHT, current_weight + step)
    
    # ==========================================
    # Milvus 操作
    # ==========================================
    
    def decay_all_memories(
        self,
        user_id: Optional[str] = None
    ) -> Dict[str, int]:
        """
        执行衰减计算，更新所有记忆的权重
        
        Args:
            user_id: 用户ID（可选，为 None 时处理所有用户）
        
        Returns:
            统计信息 {"decayed": 衰减数量, "deactivated": 标记失效数量, "deleted": 删除数量}
        """
        stats = {"decayed": 0, "deactivated": 0, "deleted": 0}
        collection = MemoryDecayConfig.COLLECTION_NAME
        
        try:
            from ..database.milvus_client import MilvusClient
            
            with MilvusClient() as milvus:
                filter_expr = "active == true"
                if user_id:
                    filter_expr = f'{filter_expr} and user_id == "{user_id}"'
                
                results = milvus.client.query(
                    collection_name=collection,
                    filter=filter_expr,
                    output_fields=["id", "user_id", "weight", "update_time"]
                )
                
                current_time = time.time()
                
                for mem in results:
                    mem_id = mem.get("id")
                    old_weight = mem.get("weight", 0.0)
                    update_time = mem.get("update_time", 0.0)
                    
                    new_weight = self.calculate_decay(old_weight, update_time, current_time)
                    
                    if new_weight < MemoryDecayConfig.DELETE_WEIGHT:
                        milvus.client.delete(
                            collection_name=collection,
                            filter=f"id == {mem_id}"
                        )
                        stats["deleted"] += 1
                        continue
                    
                    is_active = new_weight >= MemoryDecayConfig.MIN_ACTIVE_WEIGHT
                    
                    if not is_active:
                        stats["deactivated"] += 1
                    
                    milvus.client.update(
                        collection_name=collection,
                        data={
                            "id": mem_id,
                            "weight": new_weight,
                            "active": is_active,
                            "update_time": update_time
                        }
                    )
                    stats["decayed"] += 1
                
                if stats["decayed"] > 0 or stats["deleted"] > 0:
                    print(f"[记忆衰减] 完成: 衰减={stats['decayed']}, 失效={stats['deactivated']}, 删除={stats['deleted']}")
        
        except Exception as e:
            print(f"[记忆衰减] 执行失败: {e}")
        
        return stats
    
    def reinforce_on_retrieval(
        self,
        memory_id: int,
        current_weight: float
    ) -> float:
        """
        检索到记忆时强化权重
        
        Args:
            memory_id: 记忆ID
            current_weight: 当前权重
        
        Returns:
            强化后的新权重
        """
        new_weight = self.reinforce_memory(current_weight)
        update_time = time.time()
        collection = MemoryDecayConfig.COLLECTION_NAME
        
        try:
            from ..database.milvus_client import MilvusClient
            
            with MilvusClient() as milvus:
                milvus.client.update(
                    collection_name=collection,
                    data={
                        "id": memory_id,
                        "weight": new_weight,
                        "active": True,
                        "update_time": update_time
                    }
                )
                
                print(f"[记忆强化] id={memory_id}, weight: {current_weight:.3f} -> {new_weight:.3f}")
        
        except Exception as e:
            print(f"[记忆强化] 更新失败: {e}")
        
        return new_weight
    
    def scheduled_cleanup(self) -> Dict[str, int]:
        """
        定期清理：删除 inactive 超过配置天数的记忆
        
        Returns:
            统计信息 {"cleaned": 清理数量}
        """
        stats = {"cleaned": 0}
        collection = MemoryDecayConfig.COLLECTION_NAME
        cleanup_threshold = time.time() - MemoryDecayConfig.INACTIVE_CLEANUP_DAYS * 86400
        
        try:
            from ..database.milvus_client import MilvusClient
            
            with MilvusClient() as milvus:
                filter_expr = f"active == false and update_time < {cleanup_threshold}"
                
                results = milvus.client.query(
                    collection_name=collection,
                    filter=filter_expr,
                    output_fields=["id"]
                )
                
                for mem in results:
                    milvus.client.delete(
                        collection_name=collection,
                        filter=f"id == {mem.get('id')}"
                    )
                    stats["cleaned"] += 1
                
                if stats["cleaned"] > 0:
                    print(f"[记忆清理] 已清理 {stats['cleaned']} 条过期记忆")
        
        except Exception as e:
            print(f"[记忆清理] 执行失败: {e}")
        
        return stats


def decay_memories(user_id: Optional[str] = None) -> Dict[str, int]:
    """便捷函数：执行记忆衰减"""
    module = MemoryDecayModule()
    return module.decay_all_memories(user_id)


def cleanup_memories() -> Dict[str, int]:
    """便捷函数：执行记忆清理"""
    module = MemoryDecayModule()
    return module.scheduled_cleanup()
