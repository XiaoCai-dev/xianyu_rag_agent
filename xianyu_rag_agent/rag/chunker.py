"""文档切分：先按段落，再对超长段落做滑动窗口二次切分。"""

from typing import List

# 切分参数，针对闲鱼咨询短文本场景调小
CHUNK_SIZE = 400       # 每块目标字符数上限
CHUNK_OVERLAP = 50     # 相邻块重叠字符数，保证语义连贯
PARA_SEP = "\n"        # 段落分隔符（连续换行视为段落边界）


def chunk_text(
    text: str,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> List[str]:
    """将长文本切分为可检索的小块。

    策略:
        1. 先按空行切成段落，剔除空段；
        2. 若段落本身超过 chunk_size，再用滑动窗口二次切分；
        3. 否则段落即一块，保持语义完整。
    """
    if not text or not text.strip():
        return []

    # 按连续空行/换行切段落
    paragraphs = [p.strip() for p in text.split(PARA_SEP) if p.strip()]
    chunks: List[str] = []

    for para in paragraphs:
        if len(para) <= chunk_size:
            chunks.append(para)
            continue
        # 超长段落滑动窗口切分
        step = max(chunk_size - overlap, 1)
        for start in range(0, len(para), step):
            piece = para[start:start + chunk_size]
            if piece:
                chunks.append(piece)
            if start + chunk_size >= len(para):
                break

    return chunks
