"""Embedding 后端抽象。

背景:
    原实现把 ``EMBEDDING_*`` 直接回退到 LLM 的 key/base_url，
    一旦 LLM 供应商（如 agnes）不提供 embedding 接口，
    RAG 会以 401/503 静默失败，且网页只看到一句「RAG 未就绪」。

本模块提供可切换的向量化后端:
    - ``api``   调用 OpenAI 兼容的 /embeddings 接口（需 EMBEDDING_API_KEY）
    - ``local`` 使用 ChromaDB 内置的 ONNX 模型，完全离线（首次会下载一次模型）
    - ``off``   关闭向量化，RAG 明确降级

选择逻辑（EMBEDDING_PROVIDER）:
    auto  -> 填了 EMBEDDING_API_KEY 就用 api，否则用 local
    api / local / off -> 强制指定
"""

import os
from typing import Dict, List

from loguru import logger

# 单次 embedding 请求条数上限（DashScope 等平台普遍为 25），超量自动分批
_EMBED_BATCH_SIZE = 25


class BaseEmbedder:
    """向量化后端接口。"""

    provider = "base"

    def embed(self, texts: List[str]) -> List[List[float]]:
        raise NotImplementedError

    def describe(self) -> Dict:
        """给管理界面/日志用的描述信息。"""
        return {"provider": self.provider}


class ApiEmbedder(BaseEmbedder):
    """OpenAI 兼容 /embeddings 接口。"""

    provider = "api"

    def __init__(self, api_key: str, base_url: str, model: str):
        from openai import OpenAI

        if not api_key:
            raise ValueError("EMBEDDING_PROVIDER=api 时必须配置 EMBEDDING_API_KEY")
        self._client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        self.base_url = base_url

    def embed(self, texts: List[str]) -> List[List[float]]:
        vecs: List[List[float]] = []
        for i in range(0, len(texts), _EMBED_BATCH_SIZE):
            batch = texts[i:i + _EMBED_BATCH_SIZE]
            resp = self._client.embeddings.create(model=self.model, input=batch)
            # OpenAI 兼容协议保证按 input 顺序返回
            vecs.extend([d.embedding for d in resp.data])
        return vecs

    def describe(self) -> Dict:
        return {"provider": self.provider, "model": self.model, "base_url": self.base_url}


class LocalEmbedder(BaseEmbedder):
    """ChromaDB 内置 ONNX 模型（all-MiniLM-L6-v2），无需任何外部 API。"""

    provider = "local"
    model = "chroma-default-onnx-minilm-l6-v2"

    def __init__(self):
        from chromadb.utils import embedding_functions

        self._fn = embedding_functions.DefaultEmbeddingFunction()

    def embed(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        raw = self._fn(texts)
        return [[float(x) for x in v] for v in raw]

    def describe(self) -> Dict:
        return {"provider": self.provider, "model": self.model, "offline": True}


class DisabledEmbedder(BaseEmbedder):
    """显式关闭向量化。"""

    provider = "off"

    def embed(self, texts: List[str]) -> List[List[float]]:
        raise RuntimeError("Embedding 已被关闭（EMBEDDING_PROVIDER=off）")


def resolve_provider() -> str:
    """解析生效的 embedding 后端类型。"""
    provider = (os.getenv("EMBEDDING_PROVIDER") or "auto").strip().lower()
    if provider not in ("auto", "api", "local", "off"):
        logger.warning(f"未知的 EMBEDDING_PROVIDER={provider}，按 auto 处理")
        provider = "auto"
    if provider == "auto":
        return "api" if (os.getenv("EMBEDDING_API_KEY") or "").strip() else "local"
    return provider


def build_embedder() -> BaseEmbedder:
    """按配置构造 embedding 后端，配置不合法时抛出可读异常。"""
    provider = resolve_provider()

    if provider == "off":
        return DisabledEmbedder()

    if provider == "api":
        return ApiEmbedder(
            api_key=(os.getenv("EMBEDDING_API_KEY") or "").strip(),
            base_url=(
                os.getenv("EMBEDDING_BASE_URL")
                or os.getenv("MODEL_BASE_URL")
                or "https://dashscope.aliyuncs.com/compatible-mode/v1"
            ),
            model=os.getenv("EMBEDDING_MODEL", "text-embedding-v3"),
        )

    # local：ChromaDB 自带 ONNX，失败时给出可操作的提示
    try:
        return LocalEmbedder()
    except Exception as e:
        raise RuntimeError(
            f"本地 embedding 初始化失败（{e}）。"
            "可执行 pip install onnxruntime 后重试，或在配置中填写 EMBEDDING_API_KEY 使用在线向量模型。"
        ) from e
