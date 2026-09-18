"""RAGRetriever — 检索增强生成入口。

职责:
    - 通过可切换的 embedding 后端（在线 API / 本地 ONNX）计算向量；
    - ingest: 文档切分 → 批量 embedding → 写入 Chroma + 元数据表；
    - search: query embedding → 向量检索 → 返回拼好的知识文本；
    - delete: 同步删向量库与元数据表。

与主进程的集成:
    XianyuReplyBot 初始化时创建一个 RAGRetriever 单例，注入 TechAgent。
    retriever 不持有 DB 连接，元数据表操作通过传入的 ChatContextManager 完成，
    避免与主进程的 SQLite 句柄冲突。
"""

import os
from typing import Dict, List, Optional

from loguru import logger

from .chunker import chunk_text
from .embedder import build_embedder
from .store import ChromaStore


class RAGRetriever:
    """向量检索器，对 Agent 层暴露 search/ingest/delete。"""

    def __init__(
        self,
        context_manager=None,
        persist_dir: str = "data/chroma",
        collection_name: str = "knowledge_base",
    ):
        self.cm = context_manager  # ChatContextManager，用于元数据表 CRUD
        self.store = ChromaStore(persist_dir, collection_name)

        # 向量化后端：由 EMBEDDING_PROVIDER 决定（api / local / off / auto）
        self.embedder = build_embedder()
        logger.info(f"Embedding 后端就绪: {self.embedder.describe()}")

    # ---------- embedding ----------
    def _embed(self, texts: List[str]) -> List[List[float]]:
        """批量计算 embedding。"""
        return self.embedder.embed(texts)

    # ---------- 写入 ----------
    def ingest(
        self,
        text: str,
        scope: str = "shop",
        item_id: Optional[str] = None,
        title: Optional[str] = None,
        source: str = "manual_upload",
    ) -> int:
        """切分并入库一份文档，返回写入块数。

        Args:
            text: 文档原文
            scope: "shop"(店铺通用) | "item"(指定商品)
            item_id: scope 为 item 时必填
            title: 文档标题，用于管理界面展示
            source: 来源标记
        """
        if scope == "item" and not item_id:
            raise ValueError("scope=item 时必须提供 item_id")

        chunks = chunk_text(text)
        if not chunks:
            logger.warning("文档切分后为空，跳过入库")
            return 0

        embeddings = self._embed(chunks)

        # 先在元数据表登记一份文档记录，拿到 doc_id
        doc_id = None
        if self.cm is not None:
            doc_id = self.cm.add_rag_document(
                title=title or "未命名文档",
                scope=scope,
                item_id=item_id,
                source=source,
                chunk_count=len(chunks),
            )

        # 每个块携带完整元数据，便于检索时过滤与溯源
        base_meta = {
            "scope": scope,
            "item_id": item_id or "",
            "title": title or "",
            "doc_id": doc_id or "",
            "source": source,
        }
        metadatas = [dict(base_meta) for _ in chunks]
        chunk_ids = self.store.add(
            texts=chunks,
            embeddings=embeddings,
            metadatas=metadatas,
        )

        logger.info(f"RAG 入库完成: {len(chunks)} 块, scope={scope}, item_id={item_id}, doc_id={doc_id}")
        return len(chunks)

    # ---------- 检索 ----------
    def search(
        self,
        query: str,
        item_id: Optional[str] = None,
        top_k: int = 3,
    ) -> str:
        """检索知识并拼成可注入 prompt 的文本块。

        召回策略:
            - 给定 item_id: 同时召回「店铺通用」和「该商品专属」知识；
            - 不给 item_id: 只召回「店铺通用」知识。
        距离过远（cosine 距离 > 0.6）的结果会被丢弃，避免噪声。
        """
        if not query or not query.strip():
            return ""

        try:
            q_emb = self._embed([query.strip()])[0]
        except Exception as e:
            logger.error(f"RAG 查询 embedding 失败: {e}")
            return ""

        where = self._build_where(item_id)
        results = self.store.query(
            query_embedding=q_emb,
            where=where,
            n_results=top_k,
        )

        # 过滤距离过远的弱相关结果（阈值随 embedding 后端变化，见 _max_distance）
        threshold = self._max_distance()
        filtered = [r for r in results if r["distance"] <= threshold]
        logger.debug(f"RAG 检索命中 {len(results)} 条，阈值 {threshold} 过滤后保留 {len(filtered)} 条")
        if not filtered:
            return ""

        lines = []
        for idx, r in enumerate(filtered, 1):
            lines.append(f"[{idx}] {r['content']}")
        return "\n".join(lines)

    def _max_distance(self) -> float:
        """弱相关过滤阈值。

        不同 embedding 后端的余弦距离分布差异很大（本地 ONNX 模型对中文的
        距离整体偏大），沿用固定的 0.6 会把正确结果一起滤掉，因此：
            - 显式配置 RAG_MAX_DISTANCE 时以其为准；
            - 否则 api 后端用 0.6，本地后端用 0.75。
        """
        raw = (os.getenv("RAG_MAX_DISTANCE") or "").strip()
        if raw:
            try:
                return float(raw)
            except ValueError:
                logger.warning(f"RAG_MAX_DISTANCE 不是合法数字: {raw}，改用默认值")
        return 0.6 if getattr(self.embedder, "provider", "") == "api" else 0.75

    def _build_where(self, item_id: Optional[str]) -> Optional[Dict]:
        """构造 Chroma where 过滤条件。"""
        if item_id:
            # 通用知识 OR 该商品专属知识
            return {"$or": [{"scope": "shop"}, {"item_id": item_id}]}
        return {"scope": "shop"}

    # ---------- 删除 ----------
    def delete_document(self, doc_id: str) -> int:
        """按 doc_id 删除该文档的所有向量块，返回删除条数。"""
        removed = self.store.delete_by_metadata({"doc_id": doc_id})
        if self.cm is not None:
            self.cm.delete_rag_document(doc_id)
        logger.info(f"RAG 删除文档 doc_id={doc_id}, 清理 {removed} 块")
        return removed

    # ---------- 管理/调试 ----------
    def list_documents(self) -> List[Dict]:
        """列出元数据表中的所有文档记录。"""
        if self.cm is not None:
            return self.cm.list_rag_documents()
        # 没有 DB 时退化为从向量库聚合
        return self.store.list_all()

    def stats(self) -> Dict:
        return {
            "available": True,
            "vector_count": self.store.count(),
            "doc_count": len(self.list_documents()),
            "embedding": self.embedder.describe(),
            "max_distance": self._max_distance(),
        }
