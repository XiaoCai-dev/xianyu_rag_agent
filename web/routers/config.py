"""配置管理：在线读取/编辑 .env 文件，保存后通知主进程重启生效。"""

import os
from typing import List, Optional

from dotenv import dotenv_values, load_dotenv, set_key
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from utils.env_file import ensure_env_file, resolve_env_path

from ..deps import get_context_manager, reset_env_cache

router = APIRouter(prefix="/api/config", tags=["config"])

# 统一成绝对路径，避免因工作目录不同而写错文件
ENV_PATH = resolve_env_path()


def _ensure_env_file():
    """确保 .env 是文件而非目录（Docker 挂载不存在的文件会创建目录）。"""
    ensure_env_file(ENV_PATH)


def _reload_env():
    """把 .env 重新读进当前进程，并让 RAG 之类缓存实例下次重建。"""
    load_dotenv(ENV_PATH, override=True)
    reset_env_cache()


# 可管理的配置项定义：key → (显示名, 是否敏感)
CONFIG_FIELDS = {
    "API_KEY":            ("LLM API Key", True),
    "MODEL_BASE_URL":     ("LLM 地址", False),
    "MODEL_NAME":         ("LLM 模型名称", False),
    "EMBEDDING_PROVIDER": ("向量模型来源", False),
    "EMBEDDING_API_KEY":  ("Embedding API Key", True),
    "EMBEDDING_BASE_URL": ("Embedding 地址", False),
    "EMBEDDING_MODEL":    ("Embedding 模型", False),
    "RAG_MAX_DISTANCE":   ("RAG 相关度阈值", False),
    "COOKIES_STR":        ("闲鱼 Cookie", True),
    "TOGGLE_KEYWORDS":    ("人工接管关键词", False),
    "SIMULATE_HUMAN_TYPING": ("模拟人工输入", False),
    "CONTROL_POLL_INTERVAL": ("控制轮询间隔(秒)", False),
    "LOG_LEVEL":          ("日志级别", False),
}

# 各字段的输入提示，避免前端把说明写死
CONFIG_OPTIONS = {
    "EMBEDDING_PROVIDER": [
        {"value": "auto", "label": "自动（填了 Key 用在线，否则用本地）"},
        {"value": "local", "label": "本地内置模型（离线，无需 Key）"},
        {"value": "api", "label": "在线接口（需填 Embedding API Key）"},
        {"value": "off", "label": "关闭向量检索"},
    ],
    "LOG_LEVEL": [
        {"value": "DEBUG", "label": "DEBUG"},
        {"value": "INFO", "label": "INFO"},
        {"value": "WARNING", "label": "WARNING"},
        {"value": "ERROR", "label": "ERROR"},
    ],
}

# 敏感字段的掩码值，GET 时返回，PUT 时如果值等于掩码则跳过不修改
SENSITIVE_MASKED = {
    "API_KEY":          "••••••••••••••••",
    "EMBEDDING_API_KEY":"••••••••••••••••",
    "COOKIES_STR":      "••••••••••••••••",
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
    _ensure_env_file()
    values = dotenv_values(ENV_PATH)
    result = {}
    for key, (label, sensitive) in CONFIG_FIELDS.items():
        raw = values.get(key) or os.getenv(key, "") or ""
        if key == "EMBEDDING_PROVIDER" and not raw:
            raw = "auto"
        if sensitive and raw:
            result[key] = {"label": label, "value": _mask(key, raw), "sensitive": True}
        else:
            result[key] = {"label": label, "value": raw, "sensitive": sensitive}
        if key in CONFIG_OPTIONS:
            result[key]["options"] = CONFIG_OPTIONS[key]
    return result


class ConfigUpdate(BaseModel):
    API_KEY: Optional[str] = None
    MODEL_BASE_URL: Optional[str] = None
    MODEL_NAME: Optional[str] = None
    EMBEDDING_PROVIDER: Optional[str] = None
    EMBEDDING_API_KEY: Optional[str] = None
    EMBEDDING_BASE_URL: Optional[str] = None
    EMBEDDING_MODEL: Optional[str] = None
    RAG_MAX_DISTANCE: Optional[str] = None
    COOKIES_STR: Optional[str] = None
    TOGGLE_KEYWORDS: Optional[str] = None
    SIMULATE_HUMAN_TYPING: Optional[str] = None
    CONTROL_POLL_INTERVAL: Optional[str] = None
    LOG_LEVEL: Optional[str] = None
    restart: bool = True


@router.put("")
def update_config(body: ConfigUpdate):
    """写入 .env，热加载到 web 进程，并可选通知 bot 进程重启。"""
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

    if updated:
        # web 进程立即生效（否则 RAG 还拿着旧 Key / 旧模型）
        _reload_env()

    pending_control = None
    if restart and updated:
        cm = get_context_manager()
        pending_control = cm.enqueue_control("restart_bot")
        result["control_id"] = pending_control
        result["message"] = "配置已保存，已通知 bot 进程重启以生效"
    elif updated:
        result["message"] = "配置已保存（未重启 bot，主进程仍在用旧配置）"

    return result


class SelfTestRequest(BaseModel):
    targets: List[str] = ["llm"]


@router.post("/test")
def run_test(body: SelfTestRequest):
    """对当前配置做连通性自检：llm / embedding / cookie。"""
    from ..selftest import run_selftest

    targets = [t for t in (body.targets or []) if t]
    if not targets:
        raise HTTPException(400, "请至少选择一个检测项")
    return run_selftest(targets)


@router.get("/env-path")
def env_path():
    """返回 .env 的实际绝对路径，便于用户手动核对。"""
    _ensure_env_file()
    return {"env_path": ENV_PATH, "exists": os.path.exists(ENV_PATH), "size": os.path.getsize(ENV_PATH)}
