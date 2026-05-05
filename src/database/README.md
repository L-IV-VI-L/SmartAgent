# Database 模块文档

## 概述

Database 模块提供 SmartAgent 系统的所有数据访问层功能，包括 Milvus（向量存储）、MongoDB（文档存储）、Redis（缓存）以及统一的 Repository 层。

## 文件结构

```
src/database/
├── db_config.py           # 数据库配置常量
├── db_factory.py          # 数据库工厂
├── milvus_client.py       # Milvus 向量数据库客户端
├── mongodb_client.py      # MongoDB 文档数据库客户端
├── redis_client.py        # Redis 缓存客户端
├── memory_decay.py        # 记忆衰减模块
├── repositories.py        # Repository 层（数据访问接口）
└── __init__.py
```

---

## 1. 数据库配置 (db_config.py)

### 功能

定义所有数据库连接的配置常量和环境变量读取。

### 配置项

| 配置 | 说明 | 环境变量 | 默认值 |
|------|------|---------|--------|
| Milvus URI | Milvus 连接地址 | `MILVUS_URI` | `http://localhost:19530` |
| Milvus Token | Milvus 认证 Token | `MILVUS_TOKEN` | `None` |
| MongoDB URI | MongoDB 连接地址 | `MONGO_URI` | `mongodb://localhost:27017` |
| Redis URI | Redis 连接地址 | `REDIS_URI` | `redis://localhost:6379` |
| Milvus 集合名 | 长期记忆集合 | - | `long_term_memory` |

---

## 2. Milvus 向量数据库 (milvus_client.py)

### MilvusVectorStore

**功能**: 提供向量存储和检索功能，用于长期记忆管理。

### 集合 Schema

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | INT64 | 主键，自动递增 |
| `doc_id` | VARCHAR(64) | 文档唯一标识 |
| `user_id` | VARCHAR(64) | 用户标识 |
| `text` | VARCHAR(65535) | 文本内容 |
| `content` | VARCHAR(65535) | 原始内容 |
| `vector` | FLOAT_VECTOR(1024) | 向量表示 |
| `weight` | FLOAT | 权重值 |
| `create_time` | DOUBLE | 创建时间戳 |
| `update_time` | DOUBLE | 更新时间戳 |
| `metadata` | JSON | 元数据 |

### 核心方法

| 方法 | 说明 |
|------|------|
| `upsert(doc_id, vector, text, metadata, ...)` | 插入或更新向量记录 |
| `search(query_vector, top_k, filter_expr)` | 向量相似度搜索 |
| `get_by_id(doc_id)` | 根据 doc_id 获取记录 |
| `update_memory(memory_id, data)` | 更新指定记忆的字段（通过 upsert 实现） |

### 索引配置

- 索引类型: `IVF_FLAT`
- 度量类型: `COSINE`
- 参数: `nlist=128`

### 注意事项

- 向量维度必须是 1024，与 DashScope `text-embedding-v3` 模型的输出维度匹配
- 集合名称: `long_term_memory`
- 初始化脚本: `scripts/init_milvus.py`

---

## 3. MongoDB 文档数据库 (mongodb_client.py)

### MongoClient

**功能**: 提供文档存储功能，用于用户配置、人格数据等。

### 核心方法

| 方法 | 说明 |
|------|------|
| `insert_one(collection, document)` | 插入文档 |
| `find_one(collection, filter)` | 查找单个文档 |
| `update_one(collection, filter, update)` | 更新文档 |
| `find_many(collection, filter)` | 查找多个文档 |

---

## 4. Redis 缓存 (redis_client.py)

### RedisClient

**功能**: 提供缓存功能，用于短期记忆、会话状态等。

### 核心方法

| 方法 | 说明 |
|------|------|
| `set(key, value, ttl)` | 设置键值对（可设过期时间） |
| `get(key)` | 获取值 |
| `delete(key)` | 删除键 |
| `rpush(key, value)` | 列表右侧推入 |
| `lrange(key, start, end)` | 获取列表范围 |
| `hset(key, field, value)` | 哈希表设置 |
| `hgetall(key)` | 获取整个哈希表 |

### 使用场景

- 短期记忆存储
- 会话状态缓存
- 用户临时数据

---

## 5. 记忆衰减 (memory_decay.py)

### 功能

实现记忆衰减策略，根据时间等因素调整记忆权重。

### 核心类

**MemoryDecayModule**
- 根据记忆创建时间计算衰减权重
- 支持自定义衰减公式

---

## 6. Repository 层 (repositories.py)

### ConversationRepository

**功能**: 会话数据访问接口。

### 核心方法

| 方法 | 说明 |
|------|------|
| `get_conversation_history(user_id, limit)` | 获取用户历史对话 |
| `save_conversation(user_id, message, response)` | 保存对话记录 |

---

### MemoryRepository

**功能**: 记忆数据访问接口，封装 Milvus 操作。

### 核心方法

| 方法 | 说明 |
|------|------|
| `save_long_memory(doc_id, vector, text, metadata, ...)` | 保存长期记忆到 Milvus |
| `search_long_memories(user_id, query_vector, top_k, memory_types)` | 检索长期记忆 |

---

## 模块间关系图

```
Repository Layer
├── ConversationRepository
│     ├── MongoDB Client
│     └── Redis Client
│
└── MemoryRepository
      ├── MilvusVectorStore
      └── MemoryDecayModule

Database Factory
└── 统一创建和初始化所有数据库客户端
```

## 数据流

```
ContextBuildAgent
  └── MemoryRetriever
        ├── MemoryRepository.search_short_memories() → Redis
        └── MemoryRepository.search_long_memories() → Milvus

MainlineMemoryAgent
  └── MainlineMemoryUpdater
        └── MemoryRepository → MongoDB / Milvus
```
