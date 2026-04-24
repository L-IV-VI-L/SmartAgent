"""
状态工具处理模块 - 配置文件

集中管理：
1. 人格与语气标签的默认配置
2. 数据存储格式（MongoDB / Redis）
3. 更新阈值与微调步长参数
"""

# ==========================================
# 默认配置
# ==========================================

# 人格标签（权重 0~5）
DEFAULT_PERSONALITY = {
    "热情开朗": 5.0,
    "温和耐心": 0.0,
    "理性专业": 0.0,
    "沉稳治愈": 0.0,
    "简洁干练": 0.0,
    "幽默轻松": 0.0
}

# 语气标签（权重 0~1）
DEFAULT_TONE = {
    "亲切口语": 1.0,
    "温柔舒缓": 0.0,
    "鼓励支持": 0.0,
    "冷静客观": 0.0,
    "共情安慰": 0.0,
    "正式严谨": 0.0,
    "轻松调侃": 0.0,
    "傲娇轻视": 0.0,
    "专业严格": 0.0
}

# ==========================================
# 动态更新参数
# ==========================================

# 人格权重更新阈值（单标签步长绝对值超过此值才触发 MongoDB 更新）
PERSONA_UPDATE_THRESHOLD = 0.3

# 语气权重更新阈值
TONE_UPDATE_THRESHOLD = 0.15

# 每次微调步长基数（用于默认降级方案）
UPDATE_STEP = 0.05

# ==========================================
# MongoDB 数据存储格式
# ==========================================

# 集合名称
MONGO_AGENT_PERSONALITY_COLLECTION = "agent_personality"

# 文档结构
MONGO_AGENT_PERSONALITY_SCHEMA = {
    "user_id": str,                    # 用户 ID（唯一索引）
    "nickname": str,                   # 用户称呼
    "custom_persona": str,             # 用户自定义设定
    "personality_weights": dict,       # 人格权重 {"热情开朗": 5.0, ...}
    "tone_weights": dict,              # 语气权重 {"亲切口语": 1.0, ...}
    "create_time": float,              # 创建时间戳
    "update_time": float               # 最后更新时间戳
}

# MongoDB 查询字段
MONGO_PERSONALITY_FIELDS = [
    "user_id", "nickname", "custom_persona",
    "personality_weights", "tone_weights"
]

# ==========================================
# Redis 数据存储格式
# ==========================================

# Redis Key 模板
REDIS_PERSONA_STEP_KEY = "persona_step:{user_id}"
REDIS_TONE_STEP_KEY = "tone_step:{user_id}"

# Redis 数据结构
REDIS_PERSONA_STEP_SCHEMA = {
    "user_id": str,                    # 用户 ID
    "persona_step": dict,              # 人格微调步长 {"热情开朗": 0.1, ...}
    "tone_step": dict,                 # 语气微调步长 {"亲切口语": 0.05, ...}
    "timestamp": float                 # 记录时间戳
}

REDIS_TONE_STEP_SCHEMA = {
    "tone_step": dict,
    "timestamp": float
}

# ==========================================
# 情绪到人格/语气的映射（降级方案）
# ==========================================

# 情绪 -> 需要增强的人格标签及倍数
EMOTION_PERSONA_MAP = {
    "negative": {"热情开朗": 1.0, "沉稳治愈": 1.5},
    "anxious": {"温和耐心": 1.5, "沉稳治愈": 1.0},
    "angry": {"沉稳治愈": 1.5, "温和耐心": 1.0},
    "confused": {"理性专业": 1.5, "简洁干练": 1.0},
    "positive": {"热情开朗": 1.0, "幽默轻松": 1.0},
}

# 情绪 -> 需要增强的语气标签及倍数
EMOTION_TONE_MAP = {
    "negative": {"共情安慰": 1.5, "温柔舒缓": 1.0},
    "anxious": {"鼓励支持": 1.5, "温柔舒缓": 1.0},
    "angry": {"共情安慰": 1.5, "温柔舒缓": 1.0},
    "confused": {"冷静客观": 1.5, "专业严格": 1.0},
    "positive": {"亲切口语": 1.0, "轻松调侃": 1.0},
}
