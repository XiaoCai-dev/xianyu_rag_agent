"""RAG 知识库管理：列表、上传入库、删除、检索测试。"""

import os
import tempfile

from fastapi import APIRouter, File, Form, UploadFile, HTTPException

from ..deps import get_rag, get_context_manager

router = APIRouter(prefix="/api/rag", tags=["rag"])


@router.get("")
def list_docs():
    """列出所有知识文档。"""
    rag = get_rag()
    if not rag:
        raise HTTPException(503, "RAG 未就绪（缺少 API_KEY 或 chromadb）")
    return {"items": rag.list_documents(), "stats": rag.stats()}


@router.post("/ingest")
async def ingest_doc(
    file: UploadFile = File(...),
    scope: str = Form("shop"),
    item_id: str = Form(None),
    title: str = Form(None),
):
    """上传文档并入库。支持 txt/md。"""
    rag = get_rag()
    if not rag:
        raise HTTPException(503, "RAG 未就绪")
    if scope == "item" and not item_id:
        raise HTTPException(400, "scope=item 时必须提供 item_id")

    raw = await file.read()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("gbk", errors="ignore")

    doc_title = title or os.path.splitext(file.filename or "未命名")[0]
    n = rag.ingest(text=text, scope=scope, item_id=item_id, title=doc_title)
    return {"ingested_chunks": n, "title": doc_title, "scope": scope, "item_id": item_id}


@router.delete("/{doc_id}")
def delete_doc(doc_id: str):
    """删除指定文档。"""
    rag = get_rag()
    if not rag:
        raise HTTPException(503, "RAG 未就绪")
    removed = rag.delete_document(doc_id)
    return {"removed": removed, "doc_id": doc_id}


@router.get("/search")
def search_docs(q: str = "", item_id: str = None, top_k: int = 3):
    """检索测试接口。"""
    rag = get_rag()
    if not rag:
        raise HTTPException(503, "RAG 未就绪")
    if not q.strip():
        return {"result": ""}
    return {"query": q, "result": rag.search(q, item_id=item_id, top_k=top_k)}
