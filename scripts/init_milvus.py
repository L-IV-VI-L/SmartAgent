#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Milvus 集合初始化脚本。

用于创建或重建 Milvus 长期记忆集合，确保 schema 与代码定义匹配。

用法：
    python scripts/init_milvus.py

选项：
    --drop        删除现有集合后重新创建（危险操作，会清空所有数据）
    --check-only  仅检查集合状态，不进行修改
"""

from __future__ import annotations

import argparse
import sys
import os

# 确保项目根目录在 sys.path 中
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.database.milvus_client import MilvusVectorStore, _MilvusClient, DataType, FieldSchema, CollectionSchema
from src.database.db_config import MILVUS_CONFIG, MILVUS_COLLECTIONS


def get_collection_schema() -> CollectionSchema:
    """获取当前 Milvus 集合的 schema 定义。

    返回包含所有必需字段的 CollectionSchema 对象。
    """
    fields = [
        FieldSchema(name="id", dtype=DataType.VARCHAR, is_primary=True, max_length=128),
        FieldSchema(name="doc_id", dtype=DataType.VARCHAR, max_length=128),
        FieldSchema(name="user_id", dtype=DataType.VARCHAR, max_length=256),
        FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535),
        FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=65535),
        FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=1024),
        FieldSchema(name="weight", dtype=DataType.DOUBLE, default=0.0),
        FieldSchema(name="create_time", dtype=DataType.DOUBLE),
        FieldSchema(name="update_time", dtype=DataType.DOUBLE, default=0.0),
        FieldSchema(name="active", dtype=DataType.BOOL, default=True),
        FieldSchema(name="metadata", dtype=DataType.JSON),
    ]
    return CollectionSchema(fields, "SmartAgent long term memory collection")


def check_collection_status(vector_store: MilvusVectorStore) -> dict:
    """检查集合当前状态。

    Returns:
        dict: 包含集合状态的信息
    """
    result = {
        "exists": False,
        "schema_fields": [],
        "has_vector_field": False,
        "vector_dim": None,
        "message": "",
    }

    try:
        if not vector_store.client.has_collection(vector_store.collection_name):
            result["message"] = f"集合 '{vector_store.collection_name}' 不存在"
            return result

        result["exists"] = True

        # 获取集合 schema
        schema_info = vector_store.client.describe_collection(vector_store.collection_name)
        fields = schema_info.get("fields", [])

        for field in fields:
            field_name = field.get("name", "")
            result["schema_fields"].append(field_name)

            if field_name == "vector":
                result["has_vector_field"] = True
                result["vector_dim"] = field.get("params", {}).get("dim")

        if result["has_vector_field"]:
            result["message"] = (
                f"集合 '{vector_store.collection_name}' 已存在且包含 vector 字段 "
                f"(dim={result['vector_dim']})"
            )
        else:
            result["message"] = (
                f"集合 '{vector_store.collection_name}' 存在但缺少 vector 字段！"
            )

    except Exception as e:
        result["message"] = f"检查集合状态失败: {e}"

    return result


def init_collection(vector_store: MilvusVectorStore, drop_existing: bool = False) -> bool:
    """初始化 Milvus 集合。

    Args:
        vector_store: MilvusVectorStore 实例
        drop_existing: 是否删除现有集合

    Returns:
        bool: 是否成功
    """
    try:
        # 检查集合是否已存在
        if vector_store.client.has_collection(vector_store.collection_name):
            if drop_existing:
                print(f"[WARN] 删除现有集合 '{vector_store.collection_name}'...")
                vector_store.client.drop_collection(vector_store.collection_name)
            else:
                print(f"[INFO] 集合 '{vector_store.collection_name}' 已存在，跳过创建")
                return True

        # 创建集合
        schema = get_collection_schema()
        vector_store.client.create_collection(
            collection_name=vector_store.collection_name,
            schema=schema,
        )

        print(f"[OK] 集合 '{vector_store.collection_name}' 创建成功")
        print(f"  Schema 字段:")
        for field in schema.fields:
            print(f"    - {field.name} ({field.dtype})")

        # 创建索引
        index_params = vector_store.client.prepare_index_params()
        index_params.add_index(
            field_name="vector",
            index_name="vector_idx",
            index_type="IVF_FLAT",
            metric_type="COSINE",
            params={"nlist": 128},
        )
        vector_store.client.create_index(
            collection_name=vector_store.collection_name,
            index_params=index_params,
        )

        print(f"[OK] 向量索引创建成功 (IVF_FLAT, COSINE)")

        # 加载集合
        vector_store.client.load_collection(vector_store.collection_name)
        print(f"[OK] 集合已加载到内存")

        return True

    except Exception as e:
        print(f"[FAIL] 集合初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(description="Milvus 集合初始化工具")
    parser.add_argument("--drop", action="store_true", help="删除现有集合后重新创建")
    parser.add_argument("--check-only", action="store_true", help="仅检查集合状态")
    args = parser.parse_args()

    print("=" * 60)
    print("Milvus 集合初始化工具")
    print("=" * 60)
    print(f"URI: {MILVUS_CONFIG.get('uri', 'http://localhost:19530')}")
    print(f"Token: {'***' + MILVUS_CONFIG.get('token', '')[-4:] if MILVUS_CONFIG.get('token') else 'None'}")
    print(f"集合名: {MILVUS_COLLECTIONS['long_memory']}")
    print("=" * 60)

    if _MilvusClient is None:
        print("[FAIL] pymilvus 未安装，请先运行: pip install pymilvus")
        sys.exit(1)

    vector_store = MilvusVectorStore(
        uri=MILVUS_CONFIG.get("uri", "http://localhost:19530"),
        token=MILVUS_CONFIG.get("token"),
    )

    if not vector_store.client:
        print("[FAIL] Milvus 客户端初始化失败")
        sys.exit(1)

    # 检查集合状态
    status = check_collection_status(vector_store)
    print(f"\n集合状态:")
    print(f"  {status['message']}")

    if status["exists"]:
        print(f"  当前字段: {', '.join(status['schema_fields'])}")
        if status["has_vector_field"]:
            print(f"  vector 字段: 存在 (dim={status['vector_dim']})")
        else:
            print(f"  vector 字段: 缺失!")

    if args.check_only:
        print("\n[INFO] 仅检查模式，退出")
        sys.exit(0)

    # 如果集合已存在，始终检查并可能需要重建
    if status["exists"]:
        if args.drop:
            print(f"\n[WARN] 使用 --drop 选项，将删除现有集合并重新创建")
            success = init_collection(vector_store, drop_existing=True)
            if success:
                print("\n[OK] Milvus 集合重建完成!")
            else:
                print("\n[FAIL] Milvus 集合重建失败")
                sys.exit(1)
        else:
            print("\n[INFO] 集合已存在，使用 --drop 可重新创建")
    else:
        print(f"\n开始初始化集合...")
        success = init_collection(vector_store, drop_existing=False)
        if success:
            print("\n[OK] Milvus 集合初始化完成!")
        else:
            print("\n[FAIL] Milvus 集合初始化失败")
            sys.exit(1)


if __name__ == "__main__":
    main()
