# rag/indexer.py
import os
import fnmatch
from typing import List, Dict, Any, Optional
from langchain_classic.schema import Document as LangchainDocument
from .document_processor import DocumentProcessor
from .vector_store import VectorStore


class CodeBaseIndexer:
    """代码库索引器，用于索引项目自身代码"""

    def __init__(self, vector_store: VectorStore,
                 document_processor: DocumentProcessor = None):
        self.vector_store = vector_store
        self.document_processor = document_processor or DocumentProcessor()

        # 定义要包含的文件扩展名
        self.included_extensions = [".py", ".md", ".txt", ".json"]
        # 定义要排除的目录
        self.excluded_dirs = [
            "__pycache__", ".git", ".trae", "venv", "env",
            "node_modules", ".pytest_cache", "build", "dist",
            ".egg-info", "*.log", "logs", "assets/downloads"
        ]

    def index_project(self, project_path: str,
                      include_comments_only: bool = False) -> Dict[str, Any]:
        """索引整个项目代码库

        Args:
            project_path: 项目路径
            include_comments_only: 是否只索引注释（忽略代码）

        Returns:
            包含索引统计信息的字典
        """
        if not os.path.exists(project_path):
            raise FileNotFoundError(f"项目路径不存在: {project_path}")

        # 收集所有要处理的文件
        files_to_process = []
        for root, dirs, files in os.walk(project_path):
            # 过滤排除的目录
            dirs[:] = [d for d in dirs if d not in self.excluded_dirs]

            for file in files:
                file_ext = os.path.splitext(file)[1].lower()
                if file_ext in self.included_extensions:
                    file_path = os.path.join(root, file)
                    # 检查文件路径是否包含排除的模式
                    if not any(excluded in file_path for excluded in self.excluded_dirs):
                        files_to_process.append(file_path)

        # 处理每个文件
        all_documents = []
        processed_files = 0
        failed_files = 0

        for file_path in files_to_process:
            try:
                documents = self.document_processor.process_file(file_path)
                all_documents.extend(documents)
                processed_files += 1
                print(f"已处理文件: {file_path}")
            except Exception as e:
                print(f"处理文件失败 {file_path}: {e}")
                failed_files += 1

        # 添加到向量存储
        if all_documents:
            success = self.vector_store.add_documents(all_documents)
        else:
            success = False

        # 返回统计信息
        return {
            "total_files": len(files_to_process),
            "processed_files": processed_files,
            "failed_files": failed_files,
            "total_documents": len(all_documents),
            "added_to_store": success
        }

    def index_single_file(self, file_path: str) -> Dict[str, Any]:
        """索引单个文件

        Args:
            file_path: 文件路径

        Returns:
            包含索引结果的字典
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"文件不存在: {file_path}")

        try:
            documents = self.document_processor.process_file(file_path)
            success = self.vector_store.add_documents(documents)

            return {
                "file_path": file_path,
                "processed": True,
                "documents_created": len(documents),
                "added_to_store": success
            }
        except Exception as e:
            print(f"处理文件失败 {file_path}: {e}")
            return {
                "file_path": file_path,
                "processed": False,
                "error": str(e)
            }

    def index_directory(self, directory_path: str,
                        pattern: str = "*.py") -> Dict[str, Any]:
        """索引指定目录中的文件，支持通配符模式

        Args:
            directory_path: 目录路径
            pattern: 文件匹配模式，如 "*.py", "*.md"

        Returns:
            包含索引统计信息的字典
        """
        if not os.path.exists(directory_path):
            raise FileNotFoundError(f"目录不存在: {directory_path}")

        # 收集匹配的文件
        files_to_process = []
        for root, dirs, files in os.walk(directory_path):
            # 过滤排除的目录
            dirs[:] = [d for d in dirs if d not in self.excluded_dirs]

            for file in fnmatch.filter(files, pattern):
                file_path = os.path.join(root, file)
                files_to_process.append(file_path)

        # 处理每个文件
        all_documents = []
        processed_files = 0
        failed_files = 0

        for file_path in files_to_process:
            try:
                documents = self.document_processor.process_file(file_path)
                all_documents.extend(documents)
                processed_files += 1
                print(f"已处理文件: {file_path}")
            except Exception as e:
                print(f"处理文件失败 {file_path}: {e}")
                failed_files += 1

        # 添加到向量存储
        if all_documents:
            success = self.vector_store.add_documents(all_documents)
        else:
            success = False

        # 返回统计信息
        return {
            "total_files": len(files_to_process),
            "processed_files": processed_files,
            "failed_files": failed_files,
            "total_documents": len(all_documents),
            "added_to_store": success
        }