"""
MongoDB 数据库客户端
提供 MongoDB 连接对象
"""

from typing import Any

try:
    from pymongo import MongoClient  # type: ignore
except Exception:  # pragma: no cover - fallback for incompatible runtime/pymongo
    MongoClient = None

from .db_config import MONGODB_CONFIG


class _InMemoryCollection:
    def __init__(self):
        self._docs = []

    def find_one(self, query):
        for doc in self._docs:
            if all(doc.get(k) == v for k, v in query.items()):
                return doc
        return None

    def update_one(self, query, update, upsert=False):
        doc = self.find_one(query)
        if doc is None and upsert:
            doc = dict(query)
            self._docs.append(doc)
        if doc is not None:
            doc.update(update.get("$set", {}))
            if "$setOnInsert" in update and len(doc) == len(query):
                doc.update(update["$setOnInsert"])


class _InMemoryDB(dict):
    def __getitem__(self, name: str) -> Any:
        if name not in self:
            self[name] = _InMemoryCollection()
        return super().__getitem__(name)


class _InMemoryAdmin:
    def command(self, *_args, **_kwargs):
        return {"ok": 1}


class _InMemoryMongoClient:
    def __init__(self, *_args, **_kwargs):
        self._dbs = {}
        self.admin = _InMemoryAdmin()

    def __getitem__(self, name: str):
        if name not in self._dbs:
            self._dbs[name] = _InMemoryDB()
        return self._dbs[name]

    def close(self):
        return None


class MongoDBClient:
    """MongoDB 客户端类，优先使用真实 Mongo，失败时回退到内存实现。"""

    def __init__(self, **kwargs):
        config = {**MONGODB_CONFIG, **kwargs}
        self.host = config["host"]
        self.port = config["port"]
        self.database_name = config["database"]
        if config["username"] and config["password"]:
            uri = f"mongodb://{config['username']}:{config['password']}@{self.host}:{self.port}/{self.database_name}"
        else:
            uri = f"mongodb://{self.host}:{self.port}"
        try:
            if MongoClient is None:
                raise RuntimeError("pymongo unavailable")
            self.client = MongoClient(uri)
            self.db = self.client[self.database_name]
            self.client.admin.command("ping")
        except Exception:
            self.client = _InMemoryMongoClient()
            self.db = self.client[self.database_name]

    def close(self):
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
