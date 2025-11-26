# rag/rag_manager.py
import os
from typing import List, Dict, Any, Optional
from langchain_classic.schema import Document as LangchainDocument
from .document_processor import DocumentProcessor
from .vector_store import VectorStore
from .indexer import CodeBaseIndexer


class RAGManager:
    """RAG管理器，整合文档处理、向量存储和检索功能"""

    def __init__(self, vector_store_path: str = "./rag/vector_store"):
        self.document_processor = DocumentProcessor()
        self.vector_store = VectorStore(vector_store_path=vector_store_path)
        self.code_indexer = CodeBaseIndexer(
            vector_store=self.vector_store,
            document_processor=self.document_processor
        )

        # 初始化时索引项目自身代码（可选）
        self.project_root = os.path.abspath(os.path.join(
            os.path.dirname(__file__), ".."
        ))

    def index_project_code(self) -> Dict[str, Any]:
        """索引项目自身代码作为RAG数据源

        Returns:
            索引统计信息
        """
        return self.code_indexer.index_project(self.project_root)

    def add_document(self, file_path: str) -> Dict[str, Any]:
        """添加单个文档到RAG系统

        Args:
            file_path: 文件路径

        Returns:
            添加结果信息
        """
        try:
            documents = self.document_processor.process_file(file_path)
            success = self.vector_store.add_documents(documents)

            return {
                "success": success,
                "file_path": file_path,
                "document_chunks": len(documents)
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    def add_web_content(self, url: str, content: str, title: str = None) -> Dict[str, Any]:
        """添加网页内容到RAG系统

        Args:
            url: 网页URL
            content: 网页内容
            title: 网页标题

        Returns:
            添加结果信息
        """
        try:
            documents = self.document_processor.process_web_content(url, content, title)
            success = self.vector_store.add_documents(documents)

            return {
                "success": success,
                "url": url,
                "document_chunks": len(documents)
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    def retrieve(self, query: str, k: int = 5,
                 source_type: str = None) -> List[LangchainDocument]:
        """检索相关文档

        Args:
            query: 查询字符串
            k: 返回结果数量
            source_type: 源类型过滤，可选值：'code', 'web_content', 'document'

        Returns:
            相关文档列表
        """
        # 构建过滤条件
        filter_metadata = None
        if source_type == 'web_content':
            filter_metadata = {"type": "web_content"}

        # 执行检索
        results = self.vector_store.search(query, k=k, filter_metadata=filter_metadata)

        # 如果指定了其他源类型，进行后处理过滤
        if source_type == 'code':
            # 过滤代码文件（.py, .js等）
            results = [doc for doc in results if
                       doc.metadata.get("source", "").endswith(('.py', '.js', '.ts', '.jsx', '.tsx'))]
        elif source_type == 'document':
            # 过滤文档文件（.pdf, .md, .docx等）
            results = [doc for doc in results if
                       doc.metadata.get("source", "").endswith(('.pdf', '.md', '.docx', '.txt')) and
                       doc.metadata.get("type") != "web_content"]

        return results

    def get_rag_context(self, query: str, k: int = 5,
                        source_type: str = None) -> str:
        """获取RAG上下文，用于增强LLM的回答

        Args:
            query: 查询字符串
            k: 返回结果数量
            source_type: 源类型过滤

        Returns:
            格式化的RAG上下文字符串
        """
        documents = self.retrieve(query, k=k, source_type=source_type)

        if not documents:
            return ""

        # 构建上下文
        context_parts = []
        for i, doc in enumerate(documents, 1):
            source = doc.metadata.get("source", "未知源")
            title = doc.metadata.get("title", "")

            source_info = f"[资料 {i}] 来源: {source}"
            if title:
                source_info += f", 标题: {title}"

            context_parts.append(
                f"{source_info}\n内容:\n{doc.page_content}\n"
            )

        return "\n".join(context_parts)

    def get_statistics(self) -> Dict[str, Any]:
        """获取RAG系统统计信息

        Returns:
            统计信息字典
        """
        return {
            "document_count": self.vector_store.get_document_count(),
            "vector_store_path": self.vector_store.vector_store_path
        }

    def clear_all(self):
        """清空RAG系统中的所有数据"""
        self.vector_store.clear()
        return {"success": True}