"""运行日志：让网页直接查看 bot / web 两个进程的日志。

实现方式:
    两个进程各自用 loguru 把日志写到 ``data/logs/<进程>.log``，
    本路由按行读取文件尾部返回，前端轮询即可实现「实时日志」。

接口:
    GET    /api/logs/sources            列出可用日志源及文件状态
    GET    /api/logs                    读取日志（source / lines / level / keyword）
    DELETE /api/logs                    清空某个日志源
    GET    /api/logs/download           下载原始日志文件
"""

import os
import re

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from utils.logger_setup import resolve_log_path

router = APIRouter(prefix="/api/logs", tags=["logs"])

# 日志源定义：key -> (显示名, 进程名)
SOURCES = {
    "bot": ("Bot 主进程", "bot"),
    "web": ("Web 服务", "web"),
}

# 单次最多返回行数，防止一次拉爆内存
MAX_LINES = 2000

# loguru 文件格式: 2026-09-18 13:00:00.123 | INFO     | module:func:line - message
_LINE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3})\s*\|\s*(\w+)\s*\|\s*(.*)$")

_LEVEL_ORDER = {"TRACE": 0, "DEBUG": 1, "INFO": 2, "SUCCESS": 3, "WARNING": 4, "ERROR": 5, "CRITICAL": 6}


def _log_path(source: str) -> str:
    if source not in SOURCES:
        raise HTTPException(404, f"未知日志源: {source}")
    return resolve_log_path(SOURCES[source][1])


def _tail(path: str, limit: int) -> list:
    """高效读取文件末尾 limit 行（不整文件读入内存）。"""
    if not os.path.exists(path):
        return []
    with open(path, "rb") as f:
        f.seek(0, os.SEEK_END)
        size = f.tell()
        block = 8192
        data = b""
        newlines = 0
        pos = size
        # 从尾部往前按块读，直到攒够 limit+1 个换行或读到文件头
        while pos > 0 and newlines <= limit:
            step = min(block, pos)
            pos -= step
            f.seek(pos)
            chunk = f.read(step)
            data = chunk + data
            newlines = data.count(b"\n")
    text = data.decode("utf-8", errors="replace")
    lines = text.splitlines()
    return lines[-limit:] if limit > 0 else lines


def _parse(line: str) -> dict:
    """把一行日志解析成结构化对象，解析失败时原样返回。"""
    m = _LINE_RE.match(line)
    if not m:
        return {"time": "", "level": "", "message": line}
    return {"time": m.group(1), "level": m.group(2).upper(), "message": m.group(3)}


@router.get("/sources")
def list_sources():
    """列出日志源、文件路径、大小与行数。"""
    result = []
    for key, (label, proc) in SOURCES.items():
        path = resolve_log_path(proc)
        exists = os.path.exists(path)
        result.append({
            "key": key,
            "label": label,
            "path": path,
            "exists": exists,
            "size": os.path.getsize(path) if exists else 0,
            "mtime": os.path.getmtime(path) if exists else None,
        })
    return {"sources": result}


@router.get("")
def read_logs(
    source: str = Query("bot"),
    lines: int = Query(300, ge=1, le=MAX_LINES),
    level: str = Query("", description="最低日志级别，如 INFO/WARNING/ERROR"),
    keyword: str = Query("", description="关键字过滤（不区分大小写）"),
    raw: bool = Query(False, description="返回原始文本行而非结构化"),
):
    """读取日志尾部，支持级别与关键字过滤。"""
    path = _log_path(source)
    if not os.path.exists(path):
        return {
            "source": source,
            "path": path,
            "exists": False,
            "lines": [],
            "text": "",
            "message": f"日志文件尚未生成（{path}）。启动该进程后即可看到日志。",
        }

    # 过滤时多读一些原始行，避免过滤后为空
    fetch = MAX_LINES if (level or keyword) else lines
    raw_lines = _tail(path, fetch)

    min_rank = _LEVEL_ORDER.get(level.upper(), -1) if level else -1
    kw = keyword.lower()
    filtered = []
    for line in raw_lines:
        item = _parse(line)
        if min_rank >= 0 and _LEVEL_ORDER.get(item["level"], -1) < min_rank:
            continue
        if kw and kw not in line.lower():
            continue
        filtered.append(item)

    filtered = filtered[-lines:]

    return {
        "source": source,
        "path": path,
        "exists": True,
        "size": os.path.getsize(path),
        "total_scanned": len(raw_lines),
        "count": len(filtered),
        "lines": filtered,
        "text": "\n".join(
            f"{i['time']} | {i['level'] or '-':<8} | {i['message']}" if i["time"] else i["message"]
            for i in filtered
        ) if raw else "",
    }


@router.delete("")
def clear_logs(source: str = Query("bot")):
    """清空某个日志源（截断文件，不删除，避免打断正在写入的进程）。"""
    path = _log_path(source)
    if not os.path.exists(path):
        return {"cleared": False, "path": path, "message": "日志文件不存在"}
    with open(path, "w", encoding="utf-8"):
        pass
    return {"cleared": True, "path": path}


@router.get("/download")
def download_logs(source: str = Query("bot")):
    """下载完整日志文件。"""
    path = _log_path(source)
    if not os.path.exists(path):
        raise HTTPException(404, "日志文件不存在")
    return FileResponse(path, media_type="text/plain", filename=os.path.basename(path))
