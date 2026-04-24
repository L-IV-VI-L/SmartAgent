"""
Milvus 向量数据库客户端
提供 Milvus 连接对象和向量检索功能
"""

import time
from typing import Optional, List, Dict, Any

try:
    from pymilvus import MilvusClient as _MilvusClient, DataType, FieldSchema, CollectionSchema  # type: ignore
except Exception:  # pragma: no cover - fallback for incompatible runtime/deps
    _MilvusClient = None
    DataType = FieldSchema = CollectionSchema = None

from .db_config import MILVUS_CONFIG, MILVUS_COLLECTIONS, MILVUS_VECTOR_DIM, MILVUS_INDEX_PARAMS


class MilvusVectorStore:
    """Milvus 向量存储类，封装集合创建、写入和检索。"""

    def __init__(self, uri: str, token: Optional[str] = None):
        self.uri = uri
        self.token = token
        self.dimension = MILVUS_VECTOR_DIM
        self.collection_name = MILVUS_COLLECTIONS["long_memory"]
        self._initialized = False
        self.index = None
        self.query_engine = None
        self.client = _MilvusClient(uri=uri, token=token) if (_MilvusClient and token) else (_MilvusClient(uri=uri) if _MilvusClient else None)
    
    def _ensure_initialized(self):
        """确保索引组件已初始化。"""
        if self._initialized:
            return
        if self.client is None:
            self._initialized = True
            return
        self._init_llama_index()
        self._initialized = True

    def _init_llama_index(self):
        """初始化本地查询能力，不依赖额外的 llama_index 插件。"""
        self.vector_store = None
        self.index = None
        self.query_engine = None
        print(f"Milvus 查询组件已准备 - 集合：{self.collection_name}")
    
    def search(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """向量检索。"""
        self._ensure_initialized()
        try:
            if self.index is not None and self.query_engine is not None:
                response = self.query_engine.query(query)
                results: List[Dict[str, Any]] = []
                if hasattr(response, "source_nodes") and response.source_nodes:
                    for node_with_score in response.source_nodes:
                        node = node_with_score.node
                        result = {
                            "content": node.get_content(),
                            "score": node_with_score.score,
                            "metadata": node.metadata or {},
                        }
                        if not filters or self._match_filters(result["metadata"], filters):
                            results.append(result)
                return results[:top_k]

            search_params = {
                "collection_name": self.collection_name,
                "filter": None,
                "output_fields": ["id", "doc_id", "text", "embedding"],
                "limit": top_k,
            }
            if filters:
                search_params["filter"] = " and ".join(
                    [f'{k} == \"{v}\"' if isinstance(v, str) else f'{k} == {v}' for k, v in filters.items()]
                )
            if self.client is None:
                return []
            raw_results = self.client.query(**{k: v for k, v in search_params.items() if v is not None})
            results = []
            for item in raw_results or []:
                results.append({
                    "content": item.get("text", ""),
                    "score": 0.0,
                    "metadata": {
                        "id": item.get("id"),
                        "doc_id": item.get("doc_id"),
                    },
                })
            return results[:top_k]
        except Exception as e:
            print(f"向量检索失败：{e}")
            return []
    
    def _match_filters(self, metadata: Dict[str, Any], filters: Dict[str, Any]) -> bool:
        for key, value in filters.items():
            if metadata.get(key) != value:
                return False
        return True
    
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
                payload.append({
                    "id": metadata["id"],
                    "doc_id": metadata["doc_id"],
                    "text": content,
                    "embedding": [0.0] * self.dimension,
                })

            if self.client is None:
                return
            self.client.insert(collection_name=self.collection_name, data=payload)

            print(f"成功添加 {len(documents)} 个文档到向量库")
        except Exception as e:
            print(f"添加文档失败：{e}")
            raise
    
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
                print(f"创建集合 {self.collection_name} 成功，索引类型：{index_type}")
            else:
                print(f"集合 {self.collection_name} 已存在")
        except Exception as e:
            print(f"创建索引失败：{e}")
            raise
    
    def delete_collection(self):
        """删除集合"""
        try:
            if self.client.has_collection(self.collection_name):
                self.client.drop_collection(self.collection_name)
                print(f"已删除集合 {self.collection_name}")
        except Exception as e:
            print(f"删除集合失败：{e}")
    
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
        self.client = _MilvusClient(uri=self.uri, token=self.token) if self.token else _MilvusClient(uri=self.uri)
        self.vector_store = None
    
    def init_vector_store(self):
        if self.vector_store is None:
            self.vector_store = MilvusVectorStore(uri=self.uri, token=self.token)
        return self.vector_store
    
    def get_query_engine(self):
        if self.vector_store is None:
            self.init_vector_store()
        return self.vector_store.query_engine
    
    def search(self, query: str, top_k: int = 5, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        if self.vector_store is None:
            self.init_vector_store()
        return self.vector_store.search(query, top_k, filters)
    
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
