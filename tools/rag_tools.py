# tools/rag_tools.py
from typing import List, Dict, Any, Optional
from core.tool_base import BaseManusTool
import json

class RAGQueryTool(BaseManusTool):
    """RAG查询工具"""
    
    name: str = "rag_query"
    description: str = "使用RAG知识库检索相关信息。支持结构化返回格式，包含状态、消息和详细信息。用法: rag_query query=检索查询语句[, k=返回结果数量][, source_type=源类型过滤]"
    memory: Optional[Any] = None
    
    def __init__(self, rag_manager, **kwargs):
        self.rag_manager = rag_manager
        super().__init__(**kwargs)
    
    def _format_result(self, status: str, message: str, details: dict = None) -> str:
        """格式化返回结果"""
        result = {
            "status": status,
            "message": message,
            "details": details or {}
        }
        return json.dumps(result, ensure_ascii=False)
    
    def _parse_q(self, q: str) -> dict:
        """解析查询参数"""
        params = {}
        for part in [p.strip() for p in q.split(",") if p.strip()]:
            if "=" in part:
                k, v = part.split("=", 1)
                params[k.strip()] = v.strip()
        return params
    
    def _run(self, query: str) -> str:
        """执行RAG查询"""
        params = self._parse_q(query)
        search_query = params.get("query")
        
        if not search_query:
            return self._format_result(
                status="failed",
                message="缺少必要的查询参数",
                details={
                    "error_type": "missing_parameters",
                    "suggestions": [
                        "请提供query参数",
                        "使用格式: rag_query query=您的查询语句"
                    ]
                }
            )
        
        try:
            k = int(params.get("k", 5))
            source_type = params.get("source_type")
            
            documents = self.rag_manager.retrieve(query=search_query, k=k, source_type=source_type)
            
            results = []
            for doc in documents:
                results.append({
                    "source": doc.metadata.get("source", "未知源"),
                    "title": doc.metadata.get("title", ""),
                    "content": doc.page_content,
                    "metadata": doc.metadata
                })
            
            return self._format_result(
                status="success",
                message=f"成功检索到 {len(results)} 条相关文档",
                details={
                    "query": search_query,
                    "results_count": len(results),
                    "results": results,
                    "params_used": {
                        "k": k,
                        "source_type": source_type
                    }
                }
            )
        except Exception as e:
            return self._format_result(
                status="failed",
                message=f"RAG查询失败: {str(e)}",
                details={
                    "error_type": "query_error",
                    "error_message": str(e),
                    "suggestions": [
                        "检查查询参数格式",
                        "确认RAG知识库已正确初始化",
                        "尝试简化查询语句"
                    ]
                }
            )

class RAGAddDocumentTool(BaseManusTool):
    """添加文档到RAG知识库工具"""
    
    name: str = "rag_add_document"
    description: str = "添加文档到RAG知识库。支持结构化返回格式，包含状态、消息和详细信息。用法: rag_add_document file_path=文档文件路径"
    memory: Optional[Any] = None
    
    def __init__(self, rag_manager, **kwargs):
        self.rag_manager = rag_manager
        super().__init__(**kwargs)
    
    def _format_result(self, status: str, message: str, details: dict = None) -> str:
        """格式化返回结果"""
        result = {
            "status": status,
            "message": message,
            "details": details or {}
        }
        return json.dumps(result, ensure_ascii=False)
    
    def _parse_q(self, q: str) -> dict:
        """解析查询参数"""
        params = {}
        for part in [p.strip() for p in q.split(",") if p.strip()]:
            if "=" in part:
                k, v = part.split("=", 1)
                params[k.strip()] = v.strip()
        return params
    
    def _run(self, query: str) -> str:
        """添加文档到RAG知识库"""
        params = self._parse_q(query)
        file_path = params.get("file_path")
        
        if not file_path:
            return self._format_result(
                status="failed",
                message="缺少必要的文件路径参数",
                details={
                    "error_type": "missing_parameters",
                    "suggestions": [
                        "请提供file_path参数",
                        "使用格式: rag_add_document file_path=您的文件路径"
                    ]
                }
            )
        
        try:
            result = self.rag_manager.add_document(file_path)
            
            # 假设rag_manager.add_document返回的是一个字典，我们将其整合到标准格式中
            if isinstance(result, dict) and "status" in result:
                return self._format_result(
                    status=result["status"],
                    message=result.get("message", "文档添加操作完成"),
                    details=result.get("details", {})
                )
            else:
                return self._format_result(
                    status="success",
                    message=f"文档添加成功: {file_path}",
                    details={
                        "file_path": file_path,
                        "result": result
                    }
                )
        except FileNotFoundError:
            return self._format_result(
                status="failed",
                message=f"文件未找到: {file_path}",
                details={
                    "error_type": "file_not_found",
                    "suggestions": [
                        "检查文件路径是否正确",
                        "确认文件是否存在",
                        "使用绝对路径而不是相对路径"
                    ]
                }
            )
        except Exception as e:
            return self._format_result(
                status="failed",
                message=f"添加文档失败: {str(e)}",
                details={
                    "error_type": "add_document_error",
                    "error_message": str(e),
                    "suggestions": [
                        "检查文件格式是否支持",
                        "确认文件内容是否正常",
                        "检查RAG知识库权限"
                    ]
                }
            )