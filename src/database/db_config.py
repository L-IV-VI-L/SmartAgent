"""
数据库连接配置文件

所有数据库的连接配置都集中在这里
"""

# Redis 配置
REDIS_CONFIG = {
    "host": "localhost",
    "port": 6379,
    "db": 0,
    "password": None,
}

# MongoDB 配置
MONGODB_CONFIG = {
    "host": "localhost",
    "port": 27017,
    "database": "default",
    "username": None,
    "password": None,
}

# Milvus 配置
MILVUS_CONFIG = {
    "uri": "http://localhost:19530",
    "token": None,
}

# 数据库类型映射
DB_TYPES = {
    "redis": "redis",
    "mongodb": "mongodb",
    "milvus": "milvus",
}


# ==============================================
# 数据库表/集合/键名 统一配置
# ==============================================

# ----------------------
# MongoDB 集合
# ----------------------
MONGO_COLLECTIONS = {
    # 【表1】智能体自身的人格、语气、权重
    "persona": "agent_personality",
    "agent_personality": "agent_personality",

    # 【表2】用户画像：用户是什么样的人
    "user_profile": "user_profile",
}

# ==========================================
# 表1：智能体人格配置（Agent自己的性格）
# ==========================================
MONGO_AGENT_PERSONALITY_SCHEMA = {
    "user_id": str,                # 绑定用户
    "personality_weights": dict,   # 人格 0~3
    "tone_weights": dict,          # 语气 0~1
    "create_time": float,
    "update_time": float
}

# ==========================================
# 表2：用户画像
# 通过对话分析：用户是什么样的人
# ==========================================
MONGO_USER_PROFILE_SCHEMA = {
    "user_id": str,                # 唯一
    "gender": str,                 # 性别（推测）
    "age_group": str,              # 年龄层（推测）
    "personality": str,            # 用户性格：外向/内向/理性/感性
    "hobbies": list,               # 爱好
    "job": str,                    # 职业
    "habits": list,                # 行为/对话习惯
    "preferences": dict,           # 偏好
    "personality_tags": list,      # 画像标签
    "summary": str,                # 一句话总结用户
    "create_time": float,
    "update_time": float
}

# 索引
MONGO_INDEXES = {
    "agent_personality": ["user_id"],
    "user_profile": ["user_id"],   
}

# ----------------------
# Redis 键结构
# ----------------------
REDIS_KEYS = {
    # 短期对话历史
    "short_history": "short_history:{user_id}",
}

# 每条对话结构
REDIS_SHORT_HISTORY = {
    "session_id": str,     # 会话ID
    "role": str,           # user / assistant
    "content": str,        # 内容
    "timestamp": float,     # 时间戳
    "turn_id": int,         # 轮次
}

# 保留最近 15 轮
REDIS_MAX_HISTORY_COUNT = 15
REDIS_EXPIRE = 86400 * 3  # 3天过期

# ----------------------
# Milvus 集合
# ----------------------
MILVUS_COLLECTIONS = {
    "long_memory": "long_term_memory"
}

# 向量维度（根据你用的模型）
MILVUS_VECTOR_DIM = 1536

# 长时记忆固定字段
MILVUS_LONG_MEMORY_SCHEMA = {
    "id": str,                          # 主键ID（字符串，避免不同 schema 冲突）
    "doc_id": str,                     # 文档ID（兼容不同写入流程）
    "user_id": str,                    # 用户ID
    "text": str,                      # 记忆文本（兼容 LlamaIndex / 直接写入）
    "content": str,                   # 记忆原文
    "vector": list,                   # 向量
    "weight": float,                   # 记忆权重 0~5
    "create_time": float,              # 创建时间
    "update_time": float,              # 最后强化时间
    "active": bool,                    # 是否有效（低于阈值定期清除）
    "metadata": dict                   # 扩展元数据
}

# Milvus 索引
MILVUS_INDEX_PARAMS = {
    "index_type": "AUTOINDEX",
    "metric_type": "COSINE"
}