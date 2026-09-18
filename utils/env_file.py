"""统一的 .env 文件定位与自愈，bot 与 web 两个进程共用。

为什么需要它：
    1. docker-compose 把 `./.env` 以 bind mount 方式挂进容器，若宿主机没有这个文件，
       Docker 会**创建一个同名目录**，导致后续 open()/set_key() 全部失败；
    2. 镜像内可能没有 `.env`（用户还没填），需要从 `.env.example` 生成一份模板，
       网页「配置管理」才有东西可改。

因此在两个进程启动的最早期都调用一次 `ensure_env_file()`。
"""

import os
import shutil
from typing import Optional

# 项目根目录：本文件位于 <root>/utils/env_file.py
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def resolve_env_path() -> str:
    """返回 .env 的绝对路径（支持 ENV_PATH 覆盖）。"""
    raw = os.getenv("ENV_PATH") or ".env"
    if os.path.isabs(raw):
        return raw
    return os.path.abspath(os.path.join(PROJECT_ROOT, raw))


def ensure_env_file(env_path: Optional[str] = None) -> str:
    """保证 .env 是一个可读写的文件；必要时用 .env.example 初始化。"""
    path = env_path or resolve_env_path()

    if os.path.isdir(path):
        # Docker 挂载不存在的文件时会生成目录，这里修掉
        shutil.rmtree(path, ignore_errors=True)

    if not os.path.exists(path):
        example = os.path.join(os.path.dirname(path), ".env.example")
        try:
            if os.path.exists(example):
                shutil.copy(example, path)
            else:
                with open(path, "w", encoding="utf-8"):
                    pass
        except OSError:
            # 目录不可写时不要阻断启动，交由上层决定
            pass

    return path
