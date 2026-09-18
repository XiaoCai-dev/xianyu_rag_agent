"""统一日志配置：控制台 + 文件落盘。

bot 与 web 是两个独立进程，各自把日志写到 ``data/logs/<进程名>.log``，
web 进程再通过 ``/api/logs`` 读取这些文件，实现「网页看日志」。

环境变量:
    LOG_DIR   日志目录，默认 data/logs
    LOG_FILE  直接指定日志文件路径（优先于 LOG_DIR）
    LOG_LEVEL 日志级别，默认 INFO
"""

import logging
import os
import sys

from loguru import logger

_CONSOLE_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
    "<level>{message}</level>"
)
_FILE_FORMAT = (
    "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}"
)

# 记录已配置过的进程，避免重复添加 handler
_configured: dict = {}

# 这些关键字命中的标准库日志会被丢弃，避免刷屏
_NOISE_KEYWORDS = (
    "/api/logs",          # 前端轮询日志接口自身，不记录
    "/api/health",
    "/static/",
    "/favicon.ico",
    "Failed to send telemetry event",   # chromadb 遥测在部分环境必然报错，与业务无关
)


class _InterceptHandler(logging.Handler):
    """把标准库 logging（uvicorn / chromadb 等）转发到 loguru。"""

    def emit(self, record: logging.LogRecord):
        try:
            message = record.getMessage()
        except Exception:  # noqa: BLE001
            return
        if any(k in message for k in _NOISE_KEYWORDS):
            return
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        # 用 patch 直接写入原始模块/函数/行号，避免显示成 logging 内部位置
        logger.patch(
            lambda r: r.update(
                name=record.name,
                function=record.funcName,
                line=record.lineno,
            )
        ).opt(exception=record.exc_info).log(level, message)


def resolve_log_path(process_name: str) -> str:
    """按环境变量推导某个进程的日志文件路径（不创建文件）。"""
    explicit = os.getenv("LOG_FILE")
    if explicit:
        return explicit
    log_dir = os.getenv("LOG_DIR", "data/logs")
    return os.path.join(log_dir, f"{process_name}.log")


def setup_logging(process_name: str = "bot", force: bool = False) -> str:
    """初始化 loguru：同时输出到控制台与文件，返回日志文件路径。

    幂等：同一进程名重复调用不会重复添加 handler（除非 force=True）。
    """
    log_path = resolve_log_path(process_name)

    if _configured.get(process_name) and not force:
        return log_path

    level = (os.getenv("LOG_LEVEL") or "INFO").upper()

    logger.remove()
    logger.add(sys.stderr, level=level, format=_CONSOLE_FORMAT)

    log_dir = os.path.dirname(log_path)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)
    logger.add(
        log_path,
        level=level,
        format=_FILE_FORMAT,
        rotation="10 MB",
        retention=10,
        encoding="utf-8",
        backtrace=False,
        diagnose=False,
    )

    _configured[process_name] = True
    return log_path


def intercept_stdlib_logging(level: int = logging.INFO) -> None:
    """把 uvicorn / chromadb 等标准库 logging 收编到 loguru，一起写入日志文件。"""
    logging.basicConfig(handlers=[_InterceptHandler()], level=level, force=True)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "chromadb"):
        lg = logging.getLogger(name)
        lg.handlers = [_InterceptHandler()]
        lg.propagate = False
