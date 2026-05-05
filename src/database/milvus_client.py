"""
Milvus 向量数据库客户端
提供 Milvus 连接对象和向量检索功能
"""

import os
import time
from typing import Optional, List, Dict, Any, Callable

import requests

try:
    from pymilvus import MilvusClient as _MilvusClient, DataType, FieldSchema, CollectionSchema  # type: ignore
except Exception:  # pragma: no cover - fallback for incompatible runtime/deps
    _MilvusClient = None
    DataType = FieldSchema = CollectionSchema = None

try:
    from pymilvus.milvus_client import IndexParams  # type: ignore
except Exception:
    IndexParams = None

from .db_config import MILVUS_CONFIG, MILVUS_COLLECTIONS, MILVUS_VECTOR_DIM, MILVUS_INDEX_PARAMS
from ..utils.logger import get_logger

logger = get_logger(__name__)

MILVUS_VECTOR_FIELD = "vector"
MILVUS_LEGACY_VECTOR_FIELD = "embedding"


class MilvusVectorStore:
    """Milvus 向量存储类，封装集合创建、写入和检索。"""

    DASHSCOPE_EMBEDDING_URL = "https://dashscope.aliyuncs.com/api/v1/services/embeddings/text-embedding/text-embedding"
    EMBEDDING_MODEL = "text-embedding-v3"

    def __init__(
        self,
        uri: str,
        token: Optional[str] = None,
        embedding_fn: Optional[Callable[[str], Optional[List[float]]]] = None,
        embedding_dimension: int = MILVUS_VECTOR_DIM,
    ):
        self.uri = uri
        self.token = token
        self.dimension = embedding_dimension
        self.collection_name = MILVUS_COLLECTIONS["long_memory"]
        self.embedding_fn = embedding_fn
        self.client = _MilvusClient(uri=uri, token=token) if (_MilvusClient and token) else (_MilvusClient(uri=uri) if _MilvusClient else None)
        self._collection_created = False
    
    def _ensure_collection(self):
        """确保 Milvus 集合已创建。"""
        if self._collection_created or self.client is None:
            return
        try:
            if not self.client.has_collection(self.collection_name):
                fields = [
                    FieldSchema(name="id", dtype=DataType.VARCHAR, is_primary=True, max_length=128),
                    FieldSchema(name="doc_id", dtype=DataType.VARCHAR, max_length=128),
                    FieldSchema(name="user_id", dtype=DataType.VARCHAR, max_length=256),
                    FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535),
                    FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=65535),
                    FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=self.dimension),
                    FieldSchema(name="weight", dtype=DataType.DOUBLE, default=0.0),
                    FieldSchema(name="create_time", dtype=DataType.DOUBLE),
                    FieldSchema(name="update_time", dtype=DataType.DOUBLE, default=0.0),
                    FieldSchema(name="active", dtype=DataType.BOOL, default=True),
                    FieldSchema(name="metadata", dtype=DataType.JSON),
                ]
                schema = CollectionSchema(fields, "Long term memory collection")
                self.client.create_collection(collection_name=self.collection_name, schema=schema)
                if IndexParams is not None:
                    index_params = IndexParams()
                    index_params.add_index(
                        field_name="vector",
                        index_name="vector_idx",
                        index_type=MILVUS_INDEX_PARAMS["index_type"],
                        metric_type=MILVUS_INDEX_PARAMS["metric_type"],
                        params={},
                    )
                    self.client.create_index(
                        collection_name=self.collection_name,
                        index_params=index_params,
                    )
                else:
                    index_params = {
                        "metric_type": MILVUS_INDEX_PARAMS["metric_type"],
                        "index_type": MILVUS_INDEX_PARAMS["index_type"],
                        "params": {},
                    }
                    self.client.create_index(
                        collection_name=self.collection_name,
                        field_name="vector",
                        index_params=index_params,
                    )
                logger.info("创建集合 %s 成功", self.collection_name)
            else:
                logger.info("集合 %s 已存在", self.collection_name)
            self.client.load_collection(self.collection_name)
            self._collection_created = True
        except Exception as e:
            logger.error("创建集合失败: %s", e)
            raise

    def _get_embedding(self, text: str) -> Optional[List[float]]:
        """获取文本向量（支持自定义函数或默认调用 DashScope API）。"""
        if self.embedding_fn is not None:
            result = self.embedding_fn(text)
            if result is not None:
                return result

        api_key = os.getenv("DASHSCOPE_API_KEY")
        if not api_key:
            logger.warning("缺少环境变量 DASHSCOPE_API_KEY，无法获取向量")
            return None

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.EMBEDDING_MODEL,
            "input": {"texts": [text]},
            "parameters": {"text_type": "query", "dimensions": self.dimension},
        }

        try:
            resp = requests.post(self.DASHSCOPE_EMBEDDING_URL, headers=headers, json=payload, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            embeddings = data.get("output", {}).get("embeddings", [])
            if embeddings:
                embedding = embeddings[0].get("embedding", [])
                if len(embedding) < self.dimension:
                    embedding = embedding + [0.0] * (self.dimension - len(embedding))
                elif len(embedding) > self.dimension:
                    embedding = embedding[:self.dimension]
                return embedding
            return None
        except Exception as e:
            logger.error("获取向量失败: %s", e)
            return None

    def search(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """向量相似度检索。"""
        if self.client is None:
            return []

        self._ensure_collection()

        try:
            embedding = self._get_embedding(query)
            if embedding is None:
                logger.warning("无法获取查询向量，返回空结果")
                return []

            filter_expr = None
            if filters:
                conditions = []
                for key, value in filters.items():
                    if key.startswith("metadata."):
                        json_key = key.split(".", 1)[1]
                        if isinstance(value, list):
                            items = '", "'.join(str(v) for v in value)
                            conditions.append(f'metadata["{json_key}"] in ["{items}"]')
                        elif isinstance(value, str):
                            conditions.append(f'metadata["{json_key}"] == "{value}"')
                        else:
                            conditions.append(f'metadata["{json_key}"] == {value}')
                    else:
                        if isinstance(value, str):
                            conditions.append(f'{key} == "{value}"')
                        else:
                            conditions.append(f'{key} == {value}')
                filter_expr = " and ".join(conditions) if conditions else None

            raw_results = self.client.search(
                collection_name=self.collection_name,
                data=[embedding],
                anns_field="vector",
                limit=top_k,
                filter=filter_expr,
                output_fields=["id", "doc_id", "user_id", "text", "content", "weight"],
            )

            results = []
            for hit_list in raw_results or []:
                for hit in hit_list:
                    entity = hit.get("entity", {})
                    metadata = {}
                    metadata.update({
                        "id": hit.get("id"),
                        "doc_id": hit.get("entity", {}).get("doc_id"),
                        "user_id": hit.get("entity", {}).get("user_id"),
                    })
                    results.append({
                        "content": hit.get("entity", {}).get("text") or hit.get("entity", {}).get("content", ""),
                        "score": hit.get("distance", 0.0),
                        "weight": hit.get("entity", {}).get("weight", 0.0),
                        "metadata": metadata,
                    })
            return results[:top_k]
        except Exception as e:
            logger.error("向量检索失败: %s", e)
            return []
    
    def add_documents(self, documents: List[Dict[str, Any]], user_id: Optional[str] = None):
        """添加文档到向量库。"""
        self._ensure_initialized()
        try:
            payload = []
            for idx, doc in enumerate(documents):
                content = doc.get("content", "")
                metadata = dict(doc.get("metadata", {}))
                if user_id:
                    metadata["user_id"] = user_id
                generated_id = f"{user_id or 'default'}_{int(time.time() * 1000)}_{idx}"
                metadata.setdefault("id", generated_id)
                metadata.setdefault("doc_id", generated_id)
                payload.append(self._normalize_record({
                    "id": metadata["id"],
                    "doc_id": metadata["doc_id"],
                    "user_id": metadata.get("user_id", user_id or ""),
                    "text": content,
                    "content": content,
                    "vector": [0.0] * self.dimension,
                    "metadata": metadata,
                }))

            if self.client is None:
                return
            self.client.insert(collection_name=self.collection_name, data=payload)

            logger.info("成功添加 %d 个文档到向量库", len(documents))
        except Exception as e:
            logger.error("添加文档失败: %s", e)
            raise
    
    def _normalize_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """将旧写入字段归一化为当前 Milvus schema。"""
        now = time.time()
        vector = record.get(MILVUS_VECTOR_FIELD) or record.get(MILVUS_LEGACY_VECTOR_FIELD)
        text = record.get("text") or record.get("content") or ""
        metadata = record.get("metadata") or {}
        if not isinstance(metadata, dict):
            metadata = {}
        user_id = record.get("user_id") or metadata.get("user_id") or ""
        doc_id = record.get("doc_id") or record.get("id") or f"{user_id or 'default'}_{int(now * 1000)}"
        return {
            "id": str(record.get("id") or doc_id),
            "doc_id": str(doc_id),
            "user_id": str(user_id),
            "text": str(text),
            "content": str(record.get("content") or text),
            "vector": vector or [0.0] * self.dimension,
            "weight": float(record.get("weight", metadata.get("weight", 0.0)) or 0.0),
            "create_time": float(record.get("create_time", now) or now),
            "update_time": float(record.get("update_time", now) or now),
            "active": bool(record.get("active", True)),
            "metadata": metadata,
        }

    def insert(self, data: List[Dict[str, Any]]) -> None:
        """兼容旧字段 embedding，按当前 schema 写入 Milvus。"""
        if self.client is None:
            return
        payload = [self._normalize_record(record) for record in data]
        self.client.insert(collection_name=self.collection_name, data=payload)

    def create_index(self, index_type: str = "AUTOINDEX"):
        """创建向量索引。"""
        try:
            if self.client is None:
                return
            if not self.client.has_collection(self.collection_name):
                fields = [
                    FieldSchema(name="id", dtype=DataType.VARCHAR, is_primary=True, max_length=128),
                    FieldSchema(name="doc_id", dtype=DataType.VARCHAR, max_length=128),
                    FieldSchema(name="user_id", dtype=DataType.VARCHAR, max_length=256),
                    FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535),
                    FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=65535),
                    FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=self.dimension),
                    FieldSchema(name="weight", dtype=DataType.DOUBLE, default=0.0),
                    FieldSchema(name="create_time", dtype=DataType.DOUBLE),
                    FieldSchema(name="update_time", dtype=DataType.DOUBLE, default=0.0),
                    FieldSchema(name="active", dtype=DataType.BOOL, default=True),
                    FieldSchema(name="metadata", dtype=DataType.JSON),
                ]
                schema = CollectionSchema(fields, "Long term memory collection")
                self.client.create_collection(collection_name=self.collection_name, schema=schema)
                index_params = {
                    "metric_type": MILVUS_INDEX_PARAMS["metric_type"],
                    "index_type": MILVUS_INDEX_PARAMS["index_type"] if index_type == "AUTOINDEX" else index_type,
                    "params": {"M": 16, "efConstruction": 256} if index_type == "HNSW" else {},
                }
                self.client.create_index(collection_name=self.collection_name, field_name="vector", index_params=index_params)
                logger.info("创建集合 %s 成功，索引类型： %s", self.collection_name, index_type)
            else:
                logger.info("集合 %s 已存在", self.collection_name)
        except Exception as e:
            logger.error("创建索引失败: %s", e)
            raise
    
    def delete_collection(self):
        """删除集合"""
        try:
            if self.client.has_collection(self.collection_name):
                self.client.drop_collection(self.collection_name)
                logger.info("已删除集合 %s", self.collection_name)
        except Exception as e:
            logger.error("删除集合失败: %s", e)
    
    def close(self):
        """关闭连接"""
        try:
            self.client.close()
        except Exception:
            pass


class MilvusClient:
    """Milvus 客户端类。"""

    def __init__(self, **kwargs):
        config = {**MILVUS_CONFIG, **kwargs}
        self.uri = config["uri"]
        self.token = config["token"]
        self.collection_name = MILVUS_COLLECTIONS.get("long_memory", "long_term_memory")
        
        if _MilvusClient is not None:
            try:
                self.client = _MilvusClient(uri=self.uri, token=self.token) if self.token else _MilvusClient(uri=self.uri)
            except Exception as e:
                logger.error("Milvus 初始化失败: %s", e)
                self.client = None
        else:
            self.client = None
        
        self.vector_store = None
    
    def init_vector_store(self):
        if self.vector_store is None:
            self.vector_store = MilvusVectorStore(uri=self.uri, token=self.token)
        return self.vector_store
    
    def get_query_engine(self):
        if self.vector_store is None:
            self.init_vector_store()
        return self.vector_store
    
    def search(self, query: str, top_k: int = 5, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        if self.vector_store is None:
            self.init_vector_store()
        return self.vector_store.search(query, top_k, filters)

    def insert(self, data: List[Dict[str, Any]]) -> None:
        if self.vector_store is None:
            self.init_vector_store()
        self.vector_store.insert(data)

    def query(self, filter_expr: str, output_fields: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """按条件查询记忆（非向量搜索）。"""
        if self.client is None:
            return []
        if output_fields is None:
            output_fields = ["id", "user_id", "weight", "update_time", "active"]
        return self.client.query(
            collection_name=self.collection_name,
            filter=filter_expr,
            output_fields=output_fields,
        )

    def update_memory(self, memory_id: str, data: Dict[str, Any]) -> None:
        """更新指定记忆的字段（通过 upsert 实现）。"""
        if self.client is None:
            return
        payload = dict(data)
        payload["id"] = memory_id
        try:
            self.client.upsert(
                collection_name=self.collection_name,
                data=payload,
            )
        except Exception as e:
            logger.warning("记忆更新失败（upsert）: %s", e)

    def delete_memory(self, memory_id: str) -> None:
        """删除指定记忆。"""
        if self.client is None:
            return
        self.client.delete(
            collection_name=self.collection_name,
            filter=f'id == "{memory_id}"',
        )
    
    def close(self):
        try:
            if self.vector_store:
                self.vector_store.close()
            self.client.close()
        except Exception:
            pass
    
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
