"""
Database 模块 - 数据库连接管理

提供 Redis、MongoDB、Milvus 三种数据库的连接对象

"""

from typing import Optional, Dict, Any
from .redis_client import RedisClient
from .mongodb_client import MongoDBClient
from .milvus_client import MilvusClient


class DatabaseFactory:
    """
    数据库工厂类
    用于创建和管理各种数据库连接
    """
    
    _instances: Dict[str, Any] = {}
    
    @classmethod
    def create(cls, db_type: str, **kwargs) -> Any:
        """
        创建数据库连接
        
        Args:
            db_type: 数据库类型 ('redis', 'mongodb', 'milvus')
            **kwargs: 数据库连接参数（可选，会覆盖配置文件）
        
        Returns:
            数据库客户端实例
        
        Raises:
            ValueError: 不支持的数据库类型
        """
        db_type = db_type.lower()
        
        if db_type == 'redis':
            return RedisClient(**kwargs)
        elif db_type == 'mongodb':
            return MongoDBClient(**kwargs)
        elif db_type == 'milvus':
            return MilvusClient(**kwargs)
        else:
            raise ValueError(f"不支持的数据库类型：{db_type}")
    
    @classmethod
    def get_instance(cls, name: str, db_type: str, **kwargs) -> Any:
        """
        获取或创建数据库连接实例（单例模式）
        
        Args:
            name: 连接实例名称
            db_type: 数据库类型
            **kwargs: 数据库连接参数（可选）
        
        Returns:
            数据库客户端实例
        """
        if name not in cls._instances:
            cls._instances[name] = cls.create(db_type, **kwargs)
        return cls._instances[name]
    
    @classmethod
    def remove_instance(cls, name: str):
        """
        移除数据库连接实例
        
        Args:
            name: 连接实例名称
        """
        if name in cls._instances:
            instance = cls._instances[name]
            if hasattr(instance, 'close'):
                instance.close()
            del cls._instances[name]
    
    @classmethod
    def close_all(cls):
        """关闭所有数据库连接"""
        for name, instance in cls._instances.items():
            if hasattr(instance, 'close'):
                instance.close()
        cls._instances.clear()


# 便捷函数
def get_redis_client(**kwargs) -> RedisClient:
    """
    获取 Redis 客户端
    
    Args:
        **kwargs: Redis 连接参数（可选）
    
    Returns:
        RedisClient: Redis 客户端实例
    """
    return DatabaseFactory.create('redis', **kwargs)


def get_mongodb_client(**kwargs) -> MongoDBClient:
    """
    获取 MongoDB 客户端
    
    Args:
        **kwargs: MongoDB 连接参数（可选）
    
    Returns:
        MongoDBClient: MongoDB 客户端实例
    """
    return DatabaseFactory.create('mongodb', **kwargs)


def get_milvus_client(**kwargs) -> MilvusClient:
    """
    获取 Milvus 客户端
    
    Args:
        **kwargs: Milvus 连接参数（可选）
    
    Returns:
        MilvusClient: Milvus 客户端实例
    """
    return DatabaseFactory.create('milvus', **kwargs)
