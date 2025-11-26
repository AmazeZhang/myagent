# rag/vector_store.py
import os
from typing import List, Dict, Any, Optional
from langchain_classic.vectorstores import FAISS
from langchain_classic.embeddings import HuggingFaceEmbeddings
from langchain_classic.schema import Document as LangchainDocument
import pickle


class VectorStore:
    """向量存储管理器，用于文档索引和检索"""

    def __init__(self, embedding_model_name: str = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models", "BAAI_bge-small-en-v1.5"),
                 vector_store_path: str = "./rag/vector_store"):
        # 初始化嵌入模型
        self.embeddings = HuggingFaceEmbeddings(
            model_name=embedding_model_name,
            model_kwargs={'device': 'cpu'},
            encode_kwargs={'normalize_embeddings': True}
        )

        self.vector_store_path = vector_store_path
        self.vector_store = None

        # 尝试加载现有向量存储
        self._load_vector_store()

    def _load_vector_store(self):
        """加载现有向量存储"""
        if os.path.exists(os.path.join(self.vector_store_path, "index.faiss")):
            try:
                self.vector_store = FAISS.load_local(
                    self.vector_store_path,
                    self.embeddings,
                    allow_dangerous_deserialization=True
                )
                print(f"已加载现有向量存储，包含 {self.vector_store.index.ntotal} 个文档")
            except Exception as e:
                print(f"加载向量存储失败: {e}")
                self.vector_store = None

    def add_documents(self, documents: List[LangchainDocument]) -> bool:
        """添加文档到向量存储"""
        try:
            if self.vector_store is None:
                # 创建新的向量存储
                self.vector_store = FAISS.from_documents(documents, self.embeddings)
            else:
                # 添加到现有向量存储
                self.vector_store.add_documents(documents)

            # 保存向量存储
            self._save_vector_store()
            print(f"成功添加 {len(documents)} 个文档到向量存储")
            return True
        except Exception as e:
            print(f"添加文档失败: {e}")
            return False

    def _save_vector_store(self):
        """保存向量存储到磁盘"""
        if self.vector_store is not None:
            try:
                os.makedirs(self.vector_store_path, exist_ok=True)
                self.vector_store.save_local(self.vector_store_path)
            except Exception as e:
                print(f"保存向量存储失败: {e}")

    def search(self, query: str, k: int = 5,
               filter_metadata: Dict[str, Any] = None) -> List[LangchainDocument]:
        """搜索相关文档"""
        if self.vector_store is None:
            return []

        try:
            # 如果需要过滤，使用带过滤的搜索
            if filter_metadata:
                # FAISS不直接支持元数据过滤，这里可以扩展为自定义过滤
                results = self.vector_store.similarity_search(query, k=k * 2)  # 获取更多结果用于过滤
                filtered_results = []
                for doc in results:
                    match = True
                    for key, value in filter_metadata.items():
                        if key not in doc.metadata or doc.metadata[key] != value:
                            match = False
                            break
                    if match:
                        filtered_results.append(doc)
                        if len(filtered_results) >= k:
                            break
                return filtered_results
            else:
                # 普通相似度搜索
                return self.vector_store.similarity_search(query, k=k)
        except Exception as e:
            print(f"搜索失败: {e}")
            return []

    def get_document_count(self) -> int:
        """获取向量存储中的文档数量"""
        if self.vector_store is None:
            return 0
        return self.vector_store.index.ntotal

    def clear(self):
        """清空向量存储"""
        self.vector_store = None
        # 删除存储文件
        if os.path.exists(self.vector_store_path):
            try:
                for file in os.listdir(self.vector_store_path):
                    os.remove(os.path.join(self.vector_store_path, file))
                print("向量存储已清空")
            except Exception as e:
                print(f"清空向量存储失败: {e}")