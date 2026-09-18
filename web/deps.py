"""共享依赖：单例化 ChatContextManager 与 RAGRetriever。

两个进程（bot 主进程 / web 进程）各自持有自己的实例，
通过共享的 SQLite 文件 + Chroma 持久化目录交换数据，
不在进程间传递 Python 对象。

RAG 实例会记住构造时的关键环境变量，配置变更（网页保存 .env）后
下次取用会自动重建，避免继续用旧的 API Key / 模型。
"""

import os
import threading

from context_manager import ChatContextManager

# 复用主项目的数据库路径（web/__init__ 已加载 .env，此处读取即为最终值）
_DB_PATH = os.getenv("CHAT_DB_PATH", "data/chat_history.db")
_cm_instance = None
_cm_lock = threading.Lock()

_rag_instance = None
_rag_signature = None
_rag_error = None
_rag_lock = threading.Lock()


def _rag_signature_now() -> tuple:
    """影响 RAG 客户端的环境变量快照，变化即需要重建。"""
    return (
        os.getenv("EMBEDDING_PROVIDER", "auto"),
        os.getenv("EMBEDDING_API_KEY", ""),
        os.getenv("EMBEDDING_BASE_URL", ""),
        os.getenv("EMBEDDING_MODEL", ""),
        os.getenv("RAG_MAX_DISTANCE", ""),
    )


def get_context_manager() -> ChatContextManager:
    """单例 ChatContextManager，web 进程内复用同一连接池。"""
    global _cm_instance
    if _cm_instance is None:
        with _cm_lock:
            if _cm_instance is None:
                _cm_instance = ChatContextManager(db_path=_DB_PATH)
    return _cm_instance


def reset_env_cache():
    """配置保存后调用：让下次 get_rag() 用新的环境变量重建实例。"""
    global _rag_instance, _rag_signature, _rag_error
    with _rag_lock:
        _rag_instance = None
        _rag_signature = None
        _rag_error = None


def get_rag():
    """惰性初始化 RAGRetriever；失败时返回 None（原因记录在 get_rag_error）。"""
    global _rag_instance, _rag_signature, _rag_error

    sig = _rag_signature_now()
    if _rag_instance is not None and _rag_signature == sig:
        return _rag_instance

    with _rag_lock:
        if _rag_instance is not None and _rag_signature == sig:
            return _rag_instance
        try:
            from xianyu_rag_agent.rag.retriever import RAGRetriever

            _rag_instance = RAGRetriever(context_manager=get_context_manager())
            _rag_signature = sig
            _rag_error = None
        except Exception as e:  # noqa: BLE001 - 需要把原因透出给前端
            _rag_instance = None
            _rag_signature = sig
            _rag_error = f"{type(e).__name__}: {e}"
        return _rag_instance


def get_rag_error():
    """最近一次 RAG 初始化失败原因（成功时为 None）。"""
    get_rag()
    return _rag_error
