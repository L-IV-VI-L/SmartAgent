"""
通用工具模块

提供企业级通用工具函数：
- 生成唯一ID：uuid
- 获取当前时间
- 时间格式化
- 字典安全获取
- 版本号生成
"""

import uuid
from datetime import datetime
from typing import Any, Optional, Dict
from .utils_config import COMMON_CONFIG


DEFAULT_DATETIME_FORMAT = COMMON_CONFIG["DEFAULT_DATETIME_FORMAT"]
DEFAULT_DATE_FORMAT = COMMON_CONFIG["DEFAULT_DATE_FORMAT"]
DEFAULT_TIME_FORMAT = COMMON_CONFIG["DEFAULT_TIME_FORMAT"]


def generate_uuid() -> str:
    """
    生成唯一ID
    
    Returns:
        str: UUID字符串
    """
    return str(uuid.uuid4())


def get_current_time() -> datetime:
    """
    获取当前时间
    
    Returns:
        datetime: 当前时间对象
    """
    return datetime.now()


def format_datetime(
    dt: Optional[datetime] = None,
    fmt: str = DEFAULT_DATETIME_FORMAT
) -> str:
    """
    格式化时间
    
    Args:
        dt: 时间对象，为None时使用当前时间
        fmt: 时间格式字符串
    
    Returns:
        str: 格式化后的时间字符串
    """
    if dt is None:
        dt = datetime.now()
    return dt.strftime(fmt)


def format_date(
    dt: Optional[datetime] = None,
    fmt: str = DEFAULT_DATE_FORMAT
) -> str:
    """
    格式化日期
    
    Args:
        dt: 时间对象，为None时使用当前时间
        fmt: 日期格式字符串
    
    Returns:
        str: 格式化后的日期字符串
    """
    if dt is None:
        dt = datetime.now()
    return dt.strftime(fmt)


def format_time(
    dt: Optional[datetime] = None,
    fmt: str = DEFAULT_TIME_FORMAT
) -> str:
    """
    格式化时间
    
    Args:
        dt: 时间对象，为None时使用当前时间
        fmt: 时间格式字符串
    
    Returns:
        str: 格式化后的时间字符串
    """
    if dt is None:
        dt = datetime.now()
    return dt.strftime(fmt)


def safe_dict_get(
    data: Dict[str, Any],
    key: str,
    default: Any = None
) -> Any:
    """
    字典安全获取
    
    Args:
        data: 字典数据
        key: 键名
        default: 默认值
    
    Returns:
        Any: 字典值或默认值
    """
    if not isinstance(data, dict):
        return default
    return data.get(key, default)


def generate_version(
    major: int = COMMON_CONFIG["DEFAULT_VERSION_MAJOR"],
    minor: int = COMMON_CONFIG["DEFAULT_VERSION_MINOR"],
    patch: int = COMMON_CONFIG["DEFAULT_VERSION_PATCH"]
) -> str:
    """
    生成版本号
    
    Args:
        major: 主版本号
        minor: 次版本号
        patch: 补丁版本号
    
    Returns:
        str: 版本号字符串 (如: 1.0.0)
    """
    return f"{major}.{minor}.{patch}"


def timestamp_to_datetime(timestamp: float) -> datetime:
    """
    时间戳转时间对象
    
    Args:
        timestamp: 时间戳
    
    Returns:
        datetime: 时间对象
    """
    return datetime.fromtimestamp(timestamp)


def datetime_to_timestamp(dt: datetime) -> float:
    """
    时间对象转时间戳
    
    Args:
        dt: 时间对象
    
    Returns:
        float: 时间戳
    """
    return dt.timestamp()


def is_valid_uuid(uuid_str: str) -> bool:
    """
    验证UUID是否有效
    
    Args:
        uuid_str: UUID字符串
    
    Returns:
        bool: 是否有效
    """
    try:
        uuid.UUID(uuid_str)
        return True
    except ValueError:
        return False


def get_timestamp_str() -> str:
    """
    获取时间戳字符串
    
    Returns:
        str: 时间戳字符串
    """
    return str(int(datetime.now().timestamp()))


def calculate_time_diff(
    start_time: datetime,
    end_time: Optional[datetime] = None
) -> float:
    """
    计算时间差（秒）
    
    Args:
        start_time: 开始时间
        end_time: 结束时间，为None时使用当前时间
    
    Returns:
        float: 时间差（秒）
    """
    if end_time is None:
        end_time = datetime.now()
    return (end_time - start_time).total_seconds()
