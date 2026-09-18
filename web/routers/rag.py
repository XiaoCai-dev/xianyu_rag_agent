"""RAG 知识库管理：列表、上传入库、删除、检索测试。"""

import os
import tempfile

from fastapi import APIRouter, File, Form, UploadFile, HTTPException

from ..deps import get_rag, get_rag_error, get_context_manager

router = APIRouter(prefix="/api/rag", tags=["rag"])


def _rag_or_503():
    """取 RAG 实例，不可用时抛出带原因的 503，便于前端定位配置问题。"""
    rag = get_rag()
    if not rag:
        raise HTTPException(503, f"RAG 未就绪：{get_rag_error() or '未知原因'}")
    return rag


@router.get("")
def list_docs():
    """列出所有知识文档。"""
    rag = _rag_or_503()
    return {"items": rag.list_documents(), "stats": rag.stats()}


@router.post("/ingest")
async def ingest_doc(
    file: UploadFile = File(...),
    scope: str = Form("shop"),
    item_id: str = Form(None),
    title: str = Form(None),
):
    """上传文档并入库。支持 txt/md。"""
    rag = _rag_or_503()
    if scope == "item" and not item_id:
        raise HTTPException(400, "scope=item 时必须提供 item_id")

    raw = await file.read()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("gbk", errors="ignore")

    doc_title = title or os.path.splitext(file.filename or "未命名")[0]
    try:
        n = rag.ingest(text=text, scope=scope, item_id=item_id, title=doc_title)
    except Exception as e:  # noqa: BLE001 - 把向量化失败原因透出
        raise HTTPException(500, f"入库失败（向量化异常）：{e}") from e
    return {"ingested_chunks": n, "title": doc_title, "scope": scope, "item_id": item_id}


@router.delete("/{doc_id}")
def delete_doc(doc_id: str):
    """删除指定文档。"""
    rag = _rag_or_503()
    removed = rag.delete_document(doc_id)
    return {"removed": removed, "doc_id": doc_id}


@router.get("/search")
def search_docs(q: str = "", item_id: str = None, top_k: int = 3):
    """检索测试接口。"""
    rag = _rag_or_503()
    if not q.strip():
        return {"result": ""}
    return {"query": q, "result": rag.search(q, item_id=item_id, top_k=top_k)}
