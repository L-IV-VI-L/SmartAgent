# Database 模块 - 数据库连接管理

## 概述

Database 模块提供了三种数据库的连接管理：**Redis**、**MongoDB** 和 **Milvus**。该模块采用工厂模式和单例模式，提供统一的接口来创建和管理数据库连接。

## 目录结构

```
Database/
├── __init__.py          # 模块初始化，导出公共接口
├── db_config.py         # 数据库连接配置文件
├── db_factory.py        # 数据库工厂类和便捷函数
├── redis_client.py      # Redis 客户端封装
├── mongodb_client.py    # MongoDB 客户端封装
└── milvus_client.py     # Milvus 客户端封装
```

## 配置文件

所有数据库的连接配置都集中在 [`db_config.py`](file:///d:/SmartAgent/Database/db_config.py) 中：

### Redis 配置
```python
REDIS_CONFIG = {
    "host": "localhost",
    "port": 6379,
    "db": 0,
    "password": None,
}
```

### MongoDB 配置
```python
MONGODB_CONFIG = {
    "host": "localhost",
    "port": 27017,
    "database": "default",
    "username": None,
    "password": None,
}
```

### Milvus 配置
```python
MILVUS_CONFIG = {
    "uri": "http://localhost:19530",
    "token": None,
}
```

## 使用方式

### 方式 1：直接创建客户端（推荐）

```python
from Database import RedisClient, MongoDBClient, MilvusClient

# 使用配置文件中的默认配置
redis = RedisClient()
redis.client.set("key", "value")

# 覆盖配置文件中的参数
redis = RedisClient(host="192.168.1.100", port=6380)
redis.client.set("key", "value")

# MongoDB
mongo = MongoDBClient()
mongo.db.collection_name.insert_one({"key": "value"})

# Milvus
milvus = MilvusClient()
milvus.client.create_collection("my_collection", dimension=128)
```

### 方式 2：使用工厂类

```python
from Database import DatabaseFactory

# 创建数据库连接
db = DatabaseFactory.create("redis")
db.client.set("key", "value")

# 创建时覆盖配置
db = DatabaseFactory.create("mongodb", host="192.168.1.100")
db.db.collection_name.insert_one({"key": "value"})
```

### 方式 3：使用便捷函数

```python
from Database import get_redis_client, get_mongodb_client, get_milvus_client

# Redis
redis = get_redis_client()
redis.client.set("key", "value")

# MongoDB
mongo = get_mongodb_client()
mongo.db.collection_name.insert_one({"key": "value"})

# Milvus
milvus = get_milvus_client()
milvus.client.create_collection("my_collection", dimension=128)
```

### 方式 4：使用单例模式

```python
from Database import DatabaseFactory

# 获取或创建单例实例
redis1 = DatabaseFactory.get_instance("my_redis", "redis")
redis2 = DatabaseFactory.get_instance("my_redis", "redis")
# redis1 和 redis2 是同一个实例

# 移除实例
DatabaseFactory.remove_instance("my_redis")

# 关闭所有连接
DatabaseFactory.close_all()
```

## API 参考

### 客户端类

#### RedisClient

```python
class RedisClient:
    def __init__(self, **kwargs):
        """
        初始化 Redis 客户端
        
        参数:
            **kwargs: 可选参数，会覆盖配置文件中的默认值
                     支持的参数：host, port, db, password
        """
    
    def close(self):
        """关闭连接"""
    
    def __enter__(self):
        """上下文管理器进入"""
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器退出"""
```

**属性：**
- `client`: Redis 连接对象

**示例：**
```python
with RedisClient() as redis:
    redis.client.set("key", "value")
    value = redis.client.get("key")
```

#### MongoDBClient

```python
class MongoDBClient:
    def __init__(self, **kwargs):
        """
        初始化 MongoDB 客户端
        
        参数:
            **kwargs: 可选参数，会覆盖配置文件中的默认值
                     支持的参数：host, port, database, username, password
        """
    
    def close(self):
        """关闭连接"""
    
    def __enter__(self):
        """上下文管理器进入"""
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器退出"""
```

**属性：**
- `client`: MongoDB 客户端对象
- `db`: 当前数据库对象

**示例：**
```python
with MongoDBClient() as mongo:
    mongo.db.users.insert_one({"name": "John", "age": 30})
    user = mongo.db.users.find_one({"name": "John"})
```

#### MilvusClient

```python
class MilvusClient:
    def __init__(self, **kwargs):
        """
        初始化 Milvus 客户端
        
        参数:
            **kwargs: 可选参数，会覆盖配置文件中的默认值
                     支持的参数：uri, token
        """
    
    def close(self):
        """关闭连接"""
    
    def __enter__(self):
        """上下文管理器进入"""
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器退出"""
```

**属性：**
- `client`: Milvus 客户端对象

**示例：**
```python
with MilvusClient() as milvus:
    milvus.client.create_collection("my_collection", dimension=128)
```

### 工厂类

#### DatabaseFactory

```python
class DatabaseFactory:
    @classmethod
    def create(cls, db_type: str, **kwargs) -> Any:
        """
        创建数据库连接
        
        参数:
            db_type: 数据库类型 ('redis', 'mongodb', 'milvus')
            **kwargs: 数据库连接参数（可选，会覆盖配置文件）
        
        返回:
            数据库客户端实例
        
        异常:
            ValueError: 不支持的数据库类型
        """
    
    @classmethod
    def get_instance(cls, name: str, db_type: str, **kwargs) -> Any:
        """
        获取或创建数据库连接实例（单例模式）
        
        参数:
            name: 连接实例名称
            db_type: 数据库类型
            **kwargs: 数据库连接参数（可选）
        
        返回:
            数据库客户端实例
        """
    
    @classmethod
    def remove_instance(cls, name: str):
        """
        移除数据库连接实例
        
        参数:
            name: 连接实例名称
        """
    
    @classmethod
    def close_all(cls):
        """关闭所有数据库连接"""
```

### 便捷函数

```python
def get_redis_client(**kwargs) -> RedisClient:
    """获取 Redis 客户端"""

def get_mongodb_client(**kwargs) -> MongoDBClient:
    """获取 MongoDB 客户端"""

def get_milvus_client(**kwargs) -> MilvusClient:
    """获取 Milvus 客户端"""
```

## 依赖库

- **Redis**: `redis`
- **MongoDB**: `pymongo`
- **Milvus**: `pymilvus`

## 最佳实践

1. **使用上下文管理器**：推荐使用 `with` 语句来管理数据库连接，确保连接正确关闭
2. **单例模式**：对于需要复用的连接，使用 `DatabaseFactory.get_instance()` 方法
3. **配置管理**：将敏感信息（如密码）放在配置文件中，不要硬编码在代码里
4. **连接池**：对于高并发场景，考虑使用连接池（当前版本未实现）

## 注意事项

- 所有客户端类都**仅提供数据库连接对象**，具体的数据库操作通过 `client` 或 `db` 属性自行实现
- 连接会在初始化时自动测试，如果连接失败会抛出 `ConnectionError` 异常
- 使用完毕后记得调用 `close()` 方法关闭连接，或使用上下文管理器自动关闭
