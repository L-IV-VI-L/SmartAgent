"""
Redis 数据库客户端
提供 Redis 连接对象
"""

try:
    from redis import Redis  # type: ignore
    from redis.exceptions import RedisError  # type: ignore
except Exception:  # pragma: no cover - fallback for incompatible runtime/redis
    Redis = None

    class RedisError(Exception):
        pass

from .db_config import REDIS_CONFIG


class _InMemoryPipeline:
    def __init__(self, store):
        self.store = store
        self.ops = []

    def rpush(self, key, value): self.ops.append(("rpush", key, value)); return self
    def ltrim(self, key, start, end): self.ops.append(("ltrim", key, start, end)); return self
    def expire(self, key, ttl): self.ops.append(("expire", key, ttl)); return self
    def hset(self, key, mapping): self.ops.append(("hset", key, mapping)); return self
    def execute(self):
        for op in self.ops:
            if op[0] == "rpush":
                self.store.setdefault(op[1], []).append(op[2])
            elif op[0] == "ltrim":
                self.store[op[1]] = self.store.get(op[1], [])[op[2]:None if op[3] == -1 else op[3] + 1]
            elif op[0] == "expire":
                pass  # 内存实现忽略过期
            elif op[0] == "hset":
                self.store.setdefault(op[1], {}).update(op[2])


class _InMemoryRedis:
    def __init__(self):
        self.store = {}

    def ping(self): return True
    def close(self): return None
    def pipeline(self): return _InMemoryPipeline(self.store)
    def lrange(self, key, start, end): return [item.encode("utf-8") if isinstance(item, str) else item for item in self.store.get(key, [])[start:None if end == -1 else end + 1]]
    def hset(self, key, mapping=None, **kwargs):
        if mapping:
            self.store.setdefault(key, {}).update(mapping)
        if kwargs:
            self.store.setdefault(key, {}).update(kwargs)
    def hgetall(self, key):
        return self.store.get(key, {})
    def delete(self, key):
        self.store.pop(key, None)


class RedisClient:
    """Redis 客户端类，失败时回退到内存实现。"""

    def __init__(self, **kwargs):
        config = {**REDIS_CONFIG, **kwargs}
        self.host = config["host"]
        self.port = config["port"]
        self.db = config["db"]
        self.password = config["password"]
        try:
            if Redis is None:
                raise RuntimeError("redis unavailable")
            self.client = Redis(host=self.host, port=self.port, db=self.db, password=self.password)
            self.client.ping()
        except Exception:
            self.client = _InMemoryRedis()

    def close(self):
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
