"""FastAPI 应用入口。

启动: uvicorn web.app:app --host 0.0.0.0 --port 8000 --reload
"""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from .routers import dashboard, conversations, rag, prompts, config

app = FastAPI(title="闲鱼 RAG Agent 可视化平台", version="0.1.0")

# 允许本地开发时前端跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册 API 路由
app.include_router(dashboard.router)
app.include_router(conversations.router)
app.include_router(rag.router)
app.include_router(prompts.router)
app.include_router(config.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}


# 前端静态资源（JS/CSS）
_STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(_STATIC_DIR):
    app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")


# SPA 入口：根路径返回 index.html，前端用 hash 路由切换页面
@app.get("/")
def spa():
    index = os.path.join(_STATIC_DIR, "index.html")
    if not os.path.exists(index):
        return {"message": "前端尚未构建，请补充 web/static/index.html"}
    return FileResponse(index)
