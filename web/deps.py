"""共享依赖：单例化 ChatContextManager 与 RAGRetriever。

两个进程（bot 主进程 / web 进程）各自持有自己的实例，
通过共享的 SQLite 文件 + Chroma 持久化目录交换数据，
不在进程间传递 Python 对象。
"""

import os

from context_manager import ChatContextManager

# 复用主项目的数据库路径
_DB_PATH = os.getenv("CHAT_DB_PATH", "data/chat_history.db")
_cm_instance = None


def get_context_manager() -> ChatContextManager:
    """单例 ChatContextManager，web 进程内复用同一连接池。"""
    global _cm_instance
    if _cm_instance is None:
        _cm_instance = ChatContextManager(db_path=_DB_PATH)
    return _cm_instance


def get_rag():
    """惰性初始化 RAGRetriever，无 API key 时返回 None 不阻断。"""
    try:
        from xianyu_rag_agent.rag.retriever import RAGRetriever
        return RAGRetriever(context_manager=get_context_manager())
    except Exception:
        return None
