"""
AI Travel Video Factory — 通用工具函数

文件操作、日志、临时目录管理等。
"""

import json
import logging
import shutil
from pathlib import Path
from datetime import datetime


def setup_logging(log_dir: Path, verbose: bool = False) -> logging.Logger:
    """
    初始化日志系统。

    Args:
        log_dir: 日志输出目录
        verbose: 是否输出 DEBUG 级别日志

    Returns:
        配置完成的 logger 实例
    """
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"pipeline_{datetime.now().strftime('%Y%m%d')}.log"

    level = logging.DEBUG if verbose else logging.INFO

    logger = logging.getLogger("ai_travel_video")
    logger.setLevel(level)

    # 避免重复添加 handler
    if not logger.handlers:
        # 文件 handler
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setLevel(level)
        fh.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        ))
        logger.addHandler(fh)

        # 控制台 handler
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        ch.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
        logger.addHandler(ch)

    return logger


def load_json(path: Path) -> dict:
    """
    加载 JSON 文件。

    Args:
        path: JSON 文件路径

    Returns:
        解析后的字典

    Raises:
        FileNotFoundError: 文件不存在
        json.JSONDecodeError: JSON 解析失败
    """
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(data: dict | list, path: Path, indent: int = 2) -> None:
    """
    保存数据为 JSON 文件，自动创建父目录。

    Args:
        data: 要保存的字典或列表
        path: 目标路径
        indent: JSON 缩进
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=indent)


def ensure_dir(path: Path) -> Path:
    """
    确保目录存在，不存在则创建。

    Args:
        path: 目录路径

    Returns:
        传入的路径（链式调用用）
    """
    path.mkdir(parents=True, exist_ok=True)
    return path


def clean_temp(temp_dir: Path) -> None:
    """
    清空临时目录。

    Args:
        temp_dir: 临时目录路径
    """
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir(parents=True, exist_ok=True)


def timestamp() -> str:
    """返回当前时间戳字符串，用于文件命名。"""
    return datetime.now().strftime("%Y%m%d_%H%M%S")
