"""配置管理：在线读取/编辑 .env 文件，保存后通知主进程重启生效。"""

import os
import shutil
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from ..deps import get_context_manager

router = APIRouter(prefix="/api/config", tags=["config"])

ENV_PATH = os.getenv("ENV_PATH", ".env")


def _ensure_env_file():
    """确保 .env 是文件而非目录（Docker 挂载不存在的文件会创建目录）。"""
    if os.path.isdir(ENV_PATH):
        shutil.rmtree(ENV_PATH)
    if not os.path.exists(ENV_PATH):
        example = os.path.join(os.path.dirname(ENV_PATH) or ".", ".env.example")
        if os.path.exists(example):
            shutil.copy(example, ENV_PATH)
        else:
            with open(ENV_PATH, "w", encoding="utf-8") as f:
                pass

# 可管理的配置项定义：key → (显示名, 是否敏感)
CONFIG_FIELDS = {
    "API_KEY":            ("API Key", True),
    "MODEL_BASE_URL":     ("模型地址", False),
    "MODEL_NAME":         ("模型名称", False),
    "EMBEDDING_MODEL":    ("Embedding 模型", False),
    "COOKIES_STR":        ("闲鱼 Cookie", True),
    "TOGGLE_KEYWORDS":    ("人工接管关键词", False),
    "SIMULATE_HUMAN_TYPING": ("模拟人工输入", False),
    "CONTROL_POLL_INTERVAL": ("控制轮询间隔(秒)", False),
    "LOG_LEVEL":          ("日志级别", False),
}

# 敏感字段的掩码值，GET 时返回，PUT 时如果值等于掩码则跳过不修改
SENSITIVE_MASKED = {
    "API_KEY":     "••••••••••••••••",
    "COOKIES_STR": "••••••••••••••••",
}


def _mask(key: str, value: str) -> str:
    """敏感值只显示首尾，中间用星号代替。"""
    if not value:
        return ""
    if len(value) <= 10:
        return "••••••"
    return value[:6] + "•" * 6 + value[-4:]


@router.get("")
def get_config():
    """读取 .env 配置，敏感字段掩码返回。"""
    from dotenv import dotenv_values

    _ensure_env_file()
    values = dotenv_values(ENV_PATH)
    result = {}
    for key, (label, sensitive) in CONFIG_FIELDS.items():
        raw = values.get(key, os.getenv(key, ""))
        if sensitive and raw:
            result[key] = {"label": label, "value": _mask(key, raw), "sensitive": True}
        else:
            result[key] = {"label": label, "value": raw or "", "sensitive": sensitive}
    return result


class ConfigUpdate(BaseModel):
    API_KEY: Optional[str] = None
    MODEL_BASE_URL: Optional[str] = None
    MODEL_NAME: Optional[str] = None
    EMBEDDING_MODEL: Optional[str] = None
    COOKIES_STR: Optional[str] = None
    TOGGLE_KEYWORDS: Optional[str] = None
    SIMULATE_HUMAN_TYPING: Optional[str] = None
    CONTROL_POLL_INTERVAL: Optional[str] = None
    LOG_LEVEL: Optional[str] = None
    restart: bool = True


@router.put("")
def update_config(body: ConfigUpdate):
    """写入 .env 并可选通知主进程重启。"""
    from dotenv import set_key

    _ensure_env_file()

    data = body.model_dump()
    restart = data.pop("restart", True)

    updated = []
    for key in CONFIG_FIELDS:
        val = data.get(key)
        if val is None:
            continue
        # 敏感字段如果值是掩码或空，跳过不修改
        if key in SENSITIVE_MASKED:
            if not val or val == SENSITIVE_MASKED[key] or "•" in val:
                continue
        set_key(ENV_PATH, key, val)
        updated.append(key)

    result = {"updated": updated}

    if restart and updated:
        cm = get_context_manager()
        cid = cm.enqueue_control("restart_bot")
        result["control_id"] = cid
        result["message"] = "配置已保存，已通知 bot 进程重启以生效"

    return result
