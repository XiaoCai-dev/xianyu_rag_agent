"""ChromaDB 向量库封装。

设计要点:
    - embedding 由调用方（RAGRetriever）预计算后传入，store 不绑定具体 embedding 模型；
    - 支持元数据过滤（scope / item_id），用于按商品范围检索；
    - 持久化到本地目录，与主进程共享。
"""

import os
import uuid as _uuid
from typing import Dict, List, Optional

from loguru import logger

# Chroma 在某些环境会输出大量 telemetry 日志，提前抑制
os.environ.setdefault("CHROMA_TELEMETRY_DISABLED", "1")


class ChromaStore:
    """对 ChromaDB 的薄封装，屏蔽其 API 细节，便于后续替换向量库。"""

    def __init__(
        self,
        persist_dir: str = "data/chroma",
        collection_name: str = "knowledge_base",
    ):
        import chromadb
        from chromadb.config import Settings

        self.persist_dir = persist_dir
        if persist_dir:
            os.makedirs(persist_dir, exist_ok=True)

        # 使用持久化客户端，进程退出后数据落盘
        self._client = chromadb.PersistentClient(
            path=persist_dir,
            settings=Settings(anonymized_telemetry=False, allow_reset=False),
        )
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        logger.debug(f"Chroma 集合就绪: {collection_name} @ {persist_dir}")

    # ---- 写入 ----
    def add(
        self,
        texts: List[str],
        embeddings: List[List[float]],
        metadatas: List[Dict],
        ids: Optional[List[str]] = None,
    ) -> List[str]:
        """写入一批文档块，返回块 id 列表。"""
        if not texts:
            return []
        if ids is None:
            ids = [_uuid.uuid4().hex for _ in texts]
        # upsert：同 id 会覆盖，便于重建索引
        self._collection.upsert(
            ids=ids,
            documents=texts,
            embeddings=embeddings,
            metadatas=metadatas,
        )
        return ids

    # ---- 检索 ----
    def query(
        self,
        query_embedding: List[float],
        where: Optional[Dict] = None,
        n_results: int = 3,
    ) -> List[Dict]:
        """向量检索，返回 top-k 结果（含原文、元数据、距离）。"""
        kwargs = dict(
            query_embeddings=[query_embedding],
            n_results=n_results,
            include=["documents", "metadatas", "distances"],
        )
        if where:
            kwargs["where"] = where

        res = self._collection.query(**kwargs)
        docs = res.get("documents", [[]])[0]
        metas = res.get("metadatas", [[]])[0]
        dists = res.get("distances", [[]])[0]
        ids = res.get("ids", [[]])[0]

        return [
            {
                "id": ids[i],
                "content": docs[i],
                "metadata": metas[i],
                "distance": dists[i],
            }
            for i in range(len(docs))
        ]

    # ---- 删除 ----
    def delete(self, ids: List[str]) -> None:
        if ids:
            self._collection.delete(ids=ids)

    def delete_by_metadata(self, where: Dict) -> int:
        """按元数据删除，返回删除条数。"""
        got = self._collection.get(where=where, include=[])
        ids = got.get("ids", [])
        if ids:
            self._collection.delete(ids=ids)
        return len(ids)

    # ---- 查询全部（用于管理界面列表）----
    def list_all(self, where: Optional[Dict] = None, limit: int = 1000) -> List[Dict]:
        """列出文档块，可按元数据过滤。"""
        got = self._collection.get(where=where, limit=limit, include=["documents", "metadatas"])
        ids = got.get("ids", [])
        docs = got.get("documents", [])
        metas = got.get("metadatas", [])
        return [
            {"id": ids[i], "content": docs[i], "metadata": metas[i]}
            for i in range(len(ids))
        ]

    def count(self) -> int:
        return self._collection.count()
