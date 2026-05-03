"""统一日志管理器。

提供 LogManager 类，封装 Python 标准 logging 库，
支持控制台 + 文件双输出，以及按模块名获取独立 logger。
"""

from __future__ import annotations

import logging
import logging.handlers
import os
from pathlib import Path

# 日志配置常量

LOG_DIR = os.getenv("LOG_DIR", "logs")

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
VALID_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
if LOG_LEVEL not in VALID_LEVELS:
    LOG_LEVEL = "INFO"

MAX_BYTES = int(os.getenv("LOG_MAX_BYTES", 10 * 1024 * 1024))

BACKUP_COUNT = int(os.getenv("LOG_BACKUP_COUNT", 5))

ENABLE_FILE = os.getenv("LOG_ENABLE_FILE", "true").lower() == "true"

ENABLE_CONSOLE = os.getenv("LOG_ENABLE_CONSOLE", "true").lower() == "true"

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s - %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# 日志管理器

_initialized = False

def setup_logging() -> None:
    """初始化日志系统，全局仅调用一次。"""
    global _initialized
    if _initialized:
        return

    Path(LOG_DIR).mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, LOG_LEVEL))

    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)

    if ENABLE_CONSOLE:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

    if ENABLE_FILE:
        all_log_file = os.path.join(LOG_DIR, "app.log")
        file_handler = logging.handlers.RotatingFileHandler(
            all_log_file,
            maxBytes=MAX_BYTES,
            backupCount=BACKUP_COUNT,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

        error_log_file = os.path.join(LOG_DIR, "error.log")
        error_handler = logging.handlers.RotatingFileHandler(
            error_log_file,
            maxBytes=MAX_BYTES,
            backupCount=BACKUP_COUNT,
            encoding="utf-8",
        )
        error_handler.setFormatter(formatter)
        error_handler.setLevel(logging.ERROR)
        root_logger.addHandler(error_handler)

    _initialized = True

def get_logger(name: str) -> logging.Logger:
    """获取指定模块名的 logger。

    Args:
        name: 模块名称，通常使用 __name__。

    Returns:
        配置好的 logging.Logger 实例。
    """
    setup_logging()
    return logging.getLogger(name)
