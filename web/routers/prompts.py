"""提示词管理：读取/编辑四个 prompt 文件，编辑后通过命令队列触发热更新。"""

import os

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..deps import get_context_manager

router = APIRouter(prefix="/api/prompts", tags=["prompts"])

PROMPT_DIR = os.getenv("PROMPT_DIR", "prompts")
# 与 XianyuAgent._init_system_prompts 保持一致的文件名约定
PROMPT_FILES = {
    "classify": "classify_prompt",
    "price": "price_prompt",
    "tech": "tech_prompt",
    "default": "default_prompt",
}


def _resolve_path(key: str) -> str:
    name = PROMPT_FILES[key]
    target = os.path.join(PROMPT_DIR, f"{name}.txt")
    if os.path.exists(target):
        return target
    example = os.path.join(PROMPT_DIR, f"{name}_example.txt")
    if os.path.exists(example):
        return example
    raise HTTPException(404, f"提示词文件不存在: {name}")


class PromptUpdate(BaseModel):
    content: str
    reload: bool = True  # 编辑后是否触发热更新


@router.get("")
def list_prompts():
    """列出各 prompt 当前内容。"""
    result = {}
    for key in PROMPT_FILES:
        path = _resolve_path(key)
        with open(path, "r", encoding="utf-8") as f:
            result[key] = {"content": f.read(), "path": os.path.basename(path)}
    return result


@router.put("/{key}")
def update_prompt(key: str, body: PromptUpdate):
    """编辑 prompt 文件并可选触发热更新。"""
    if key not in PROMPT_FILES:
        raise HTTPException(404, f"未知 prompt: {key}")
    name = PROMPT_FILES[key]
    # 始终写入非 example 的正式文件，确保主进程加载用户自定义版
    path = os.path.join(PROMPT_DIR, f"{name}.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(body.content)

    # 通过命令队列通知主进程热更新
    result = {"saved": path}
    if body.reload:
        cm = get_context_manager()
        cid = cm.enqueue_control("reload_prompts")
        result["control_id"] = cid
        result["message"] = "已写入命令队列，主进程将在下次轮询时重载提示词"
    return result
