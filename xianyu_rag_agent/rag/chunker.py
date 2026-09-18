"""文档切分：先按空行切段落，再合并短段、对超长段落做滑动窗口二次切分。

原实现用单个换行 ``\\n`` 作分隔符（与注释里「按空行切」不符），
导致每一行都变成独立小块（例如标题「发货说明」单独成块），
检索时召回的是零碎片段而非完整语义，质量很差。
现改为：空行切段 → 贪心合并到接近 chunk_size → 超长段滑动窗口切。
"""

import re
from typing import List

# 切分参数，针对闲鱼咨询短文本场景调小
CHUNK_SIZE = 400       # 每块目标字符数上限
CHUNK_OVERLAP = 50     # 相邻块重叠字符数，保证语义连贯
MIN_CHUNK_SIZE = 80    # 小于该长度的块会尝试与相邻块合并，避免碎片化
# 段落边界：一个或多个空行
PARA_SEP_PATTERN = re.compile(r"\n\s*\n")


def chunk_text(
    text: str,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> List[str]:
    """将长文本切分为可检索的小块。

    策略:
        1. 按空行切成段落块（标题与正文之间的单换行不再切开）；
        2. 过短的段落与相邻段合并，避免出现「发货说明」这类碎片块；
        3. 单段超过 chunk_size 时，用滑动窗口二次切分。
    """
    if not text or not text.strip():
        return []

    blocks = [b.strip() for b in PARA_SEP_PATTERN.split(text) if b.strip()]

    # 没有空行的短文本（如逐行 FAQ），退化为按行成段再合并
    if len(blocks) <= 1:
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        if len(lines) > 1:
            blocks = lines

    chunks: List[str] = []
    buffer = ""

    def flush():
        nonlocal buffer
        if buffer:
            chunks.append(buffer)
            buffer = ""

    for block in blocks:
        if len(block) > chunk_size:
            # 先把已攒的内容落盘，再对超长段做滑窗
            flush()
            step = max(chunk_size - overlap, 1)
            for start in range(0, len(block), step):
                piece = block[start:start + chunk_size]
                if piece:
                    chunks.append(piece)
                if start + chunk_size >= len(block):
                    break
            continue

        if not buffer:
            buffer = block
        elif len(buffer) < MIN_CHUNK_SIZE and len(buffer) + len(block) + 1 <= chunk_size:
            # 上一块过短，合并后更利于检索
            buffer = f"{buffer}\n{block}"
        else:
            flush()
            buffer = block

    flush()
    return chunks
