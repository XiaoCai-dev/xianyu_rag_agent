"""RAG 命令行工具：手动入库 / 检索 / 列表 / 删除。

用法:
    python -m xianyu_rag_agent.rag.cli ingest <file> --scope shop [--item-id ID] [--title 标题]
    python -m xianyu_rag_agent.rag.cli search "查询语句" [--item-id ID] [--top-k 3]
    python -m xianyu_rag_agent.rag.cli list [--scope shop|item] [--item-id ID]
    python -m xianyu_rag_agent.rag.cli delete <doc_id>
    python -m xianyu_rag_agent.rag.cli stats
"""

import argparse
import os
import sys

from dotenv import load_dotenv
from loguru import logger

from .retriever import RAGRetriever
from context_manager import ChatContextManager


def _bootstrap():
    """加载环境变量与日志，复用主项目配置。"""
    if os.path.exists(".env"):
        load_dotenv()
    if os.path.exists(".env.example"):
        load_dotenv(".env.example")  # 不覆盖已存在变量

    logger.remove()
    logger.add(sys.stderr, level="INFO",
               format="<green>{time:HH:mm:ss}</green> | <level>{level:<7}</level> | {message}")


def _make_retriever():
    cm = ChatContextManager()
    return RAGRetriever(context_manager=cm)


def cmd_ingest(args):
    if not os.path.exists(args.file):
        logger.error(f"文件不存在: {args.file}")
        sys.exit(1)
    with open(args.file, "r", encoding="utf-8") as f:
        text = f.read()
    retriever = _make_retriever()
    n = retriever.ingest(
        text=text,
        scope=args.scope,
        item_id=args.item_id,
        title=args.title or os.path.basename(args.file),
    )
    print(f"入库完成: {n} 个文本块, scope={args.scope}, item_id={args.item_id or '-'}")


def cmd_search(args):
    retriever = _make_retriever()
    result = retriever.search(args.query, item_id=args.item_id, top_k=args.top_k)
    if not result:
        print("（未命中知识库）")
        return
    print("=== 检索结果 ===")
    print(result)


def cmd_list(args):
    retriever = _make_retriever()
    docs = retriever.list_documents()
    if args.scope:
        docs = [d for d in docs if d.get("scope") == args.scope]
    if args.item_id:
        docs = [d for d in docs if d.get("item_id") == args.item_id]
    if not docs:
        print("（知识库为空）")
        return
    print(f"共 {len(docs)} 份文档:")
    for d in docs:
        print(f"  [{d['doc_id'][:8]}] {d.get('title')} | scope={d.get('scope')} "
              f"item={d.get('item_id') or '-'} chunks={d.get('chunk_count')}")


def cmd_delete(args):
    retriever = _make_retriever()
    n = retriever.delete_document(args.doc_id)
    print(f"已删除 doc_id={args.doc_id}, 清理 {n} 个向量块")


def cmd_stats(args):
    retriever = _make_retriever()
    print(retriever.stats())


def build_parser():
    parser = argparse.ArgumentParser(description="Xianyu RAG 知识库命令行工具")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("ingest", help="入库文档")
    p.add_argument("file", help="文档路径(txt/md)")
    p.add_argument("--scope", choices=["shop", "item"], default="shop", help="知识范围")
    p.add_argument("--item-id", default=None, help="scope=item 时的商品ID")
    p.add_argument("--title", default=None, help="文档标题")
    p.set_defaults(func=cmd_ingest)

    p = sub.add_parser("search", help="检索测试")
    p.add_argument("query", help="查询语句")
    p.add_argument("--item-id", default=None, help="限定商品范围")
    p.add_argument("--top-k", type=int, default=3)
    p.set_defaults(func=cmd_search)

    p = sub.add_parser("list", help="列出文档")
    p.add_argument("--scope", choices=["shop", "item"], default=None)
    p.add_argument("--item-id", default=None)
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("delete", help="删除文档")
    p.add_argument("doc_id", help="文档ID")
    p.set_defaults(func=cmd_delete)

    p = sub.add_parser("stats", help="统计信息")
    p.set_defaults(func=cmd_stats)

    return parser


def main():
    _bootstrap()
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
