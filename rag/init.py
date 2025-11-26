# rag/__init__.py
"""
RAG (Retrieval Augmented Generation) 模块

该模块提供文档索引、向量存储和检索增强生成功能，支持:
1. 项目自身文档作为RAG数据源
2. PDF/Markdown知识库支持
3. 网页信息的持久存储
"""

from .rag_manager import RAGManager
from .document_processor import DocumentProcessor
from .vector_store import VectorStore
from .indexer import CodeBaseIndexer

__all__ = ["RAGManager", "DocumentProcessor", "VectorStore", "CodeBaseIndexer"]