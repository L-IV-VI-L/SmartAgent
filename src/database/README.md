# `database`

数据库与记忆存储模块。

## 主要职责

- 管理 MongoDB、Redis、Milvus 等数据源连接
- 提供 persona、conversation、memory 等仓储访问
- 支持短期记忆、长期记忆与记忆衰减逻辑

## 主要文件

- `db_config.py`：数据库与集合配置
- `mongodb_client.py`：MongoDB 客户端封装
- `redis_client.py`：Redis 客户端封装
- `milvus_client.py`：Milvus 客户端封装
- `repositories.py`：仓储层接口
- `memory_decay.py`：记忆衰减逻辑
- `db_factory.py`：数据库工厂

## 说明

`src/database/__init__.py` 不会默认导入所有客户端，避免在依赖不完整时影响启动。
