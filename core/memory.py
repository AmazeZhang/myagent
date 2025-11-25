# core/memory.py
from langchain_classic.memory import ConversationBufferMemory
import uuid
from typing import List, Dict, Any, Optional

class MemoryManager:
    """文档记忆管理"""
    def __init__(self):
        self.documents = {}

    def add_document(self, path, name=None, preview=None, full_text_snippet=None):
        # 检查是否已经存在相同路径的文档
        for existing_doc_id, doc_info in self.documents.items():
            if doc_info.get("path") == path:
                # 如果文档已存在，返回现有的doc_id
                return existing_doc_id
        
        # 生成新的doc_id（使用路径的哈希值作为基础，确保唯一性）
        import hashlib
        path_hash = hashlib.md5(path.encode()).hexdigest()[:8]
        doc_id = path_hash
        
        # 如果doc_id已存在，添加后缀确保唯一性
        counter = 1
        original_doc_id = doc_id
        while doc_id in self.documents:
            doc_id = f"{original_doc_id}_{counter}"
            counter += 1
        
        self.documents[doc_id] = {
            "path": path,
            "name": name or path.split("/")[-1],
            "preview": preview or "",
            "full_text_snippet": full_text_snippet or "",
        }
        return doc_id

    def get_document(self, doc_id):
        return self.documents.get(doc_id, None)

    def get_all(self):
        return self.documents.values()

    def clear(self):
        self.documents = {}

    def get_relevant_documents(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """根据查询获取相关文档
        
        Args:
            query: 查询字符串
            max_results: 返回的最大结果数量
            
        Returns:
            相关文档列表，按相关性排序
        """
        # 简单的相关性计算：检查查询词是否在文档内容中出现
        # 生产环境中可替换为更复杂的向量相似度计算
        results = []
        query_lower = query.lower()
        
        for doc_id, doc_info in self.documents.items():
            # 计算相关性得分
            score = 0
            # 检查文档名称
            if query_lower in doc_info["name"].lower():
                score += 2
            # 检查文档预览
            if query_lower in doc_info["preview"].lower():
                score += 1
            # 检查全文片段
            if query_lower in doc_info["full_text_snippet"].lower():
                score += 3
            
            if score > 0:
                results.append((score, doc_info))
        
        # 按相关性得分降序排序
        results.sort(key=lambda x: x[0], reverse=True)
        
        # 返回排序后的文档信息
        return [doc for _, doc in results[:max_results]]


class ConversationMemoryManager:
    """对话记忆管理"""
    def __init__(self):
        self.memory = ConversationBufferMemory(return_messages=True)

    def save(self, user_input: str, ai_output: str):
        self.memory.save_context(
            {"input": user_input},
            {"output": ai_output}
        )

    def load(self):
        return self.memory.load_memory_variables({})["history"]

    def clear(self):
        self.memory.clear()
        
    def load_relevant_memory(self, query: str, max_length: int = 2000) -> List[Dict[str, Any]]:
        """根据相关性加载对话历史，而不是简单取最近的
        
        Args:
            query: 查询字符串
            max_length: 最大返回内容长度
            
        Returns:
            相关性排序后的对话历史
        """
        history = self.load()
        if not history:
            return []
        
        # 将历史消息转换为可处理的格式
        conversation_items = []
        for i in range(0, len(history), 2):
            # 假设历史消息是用户输入和AI回复成对出现
            user_msg = history[i].content if i < len(history) else ""
            ai_msg = history[i+1].content if i+1 < len(history) else ""
            
            # 计算相关性得分
            query_lower = query.lower()
            score = 0
            
            # 检查用户消息
            if query_lower in user_msg.lower():
                score += 2
            # 检查AI消息
            if query_lower in ai_msg.lower():
                score += 1
            
            conversation_items.append({
                "user": user_msg,
                "ai": ai_msg,
                "score": score,
                "length": len(user_msg) + len(ai_msg)
            })
        
        # 按相关性得分降序排序
        conversation_items.sort(key=lambda x: x["score"], reverse=True)
        
        # 选择最相关的对话，同时控制总长度
        selected_items = []
        total_length = 0
        
        for item in conversation_items:
            if total_length + item["length"] <= max_length:
                selected_items.append(item)
                total_length += item["length"]
            elif item["score"] > 0:
                # 如果是相关的但会超出长度限制，尝试截断
                remaining_space = max_length - total_length
                if remaining_space > 10:  # 确保有足够空间显示部分内容
                    # 截断用户和AI消息
                    user_truncated = item["user"][:remaining_space//2] + "..."
                    ai_truncated = item["ai"][:remaining_space//2] + "..."
                    
                    selected_items.append({
                        "user": user_truncated,
                        "ai": ai_truncated,
                        "score": item["score"],
                        "length": len(user_truncated) + len(ai_truncated)
                    })
                    break
        
        # 按时间顺序（原始顺序）返回
        selected_items.sort(key=lambda x: conversation_items.index(x))
        
        return selected_items