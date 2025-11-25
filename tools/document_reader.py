# tools/document_reader.py
from typing import Optional
from core.tool_base import BaseManusTool
from utils.parser_utils import parse_file, get_preview
import os
import json

class DocumentReaderTool(BaseManusTool):
    name: str = "document_reader"
    description: str = "读取已注册的上传文档（通过doc_id或路径）。支持结构化返回格式，包含状态、消息和详细信息。用法: document_reader doc_id=<id> 或 path=/完整路径, max_pages=2"
    memory: Optional[object] = None  # 允许注入 MemoryManager（与 BaseManusTool 声明重复，但明确)

    def __init__(self, memory: Optional[object] = None, **kwargs):
        # 首先调用父类的初始化方法，确保 Pydantic 模型正确初始化
        super().__init__(**kwargs)
        # 然后设置 memory 属性
        if memory is not None:
            self.memory = memory

    def _format_result(self, status: str, message: str, details: dict = None) -> str:
        """格式化返回结果"""
        result = {
            "status": status,
            "message": message,
            "details": details or {}
        }
        return json.dumps(result, ensure_ascii=False)

    def _parse_q(self, q: str):
        params = {}
        for part in [p.strip() for p in q.split(",") if p.strip()]:
            if "=" in part:
                k, v = part.split("=", 1)
                params[k.strip()] = v.strip()
            else:
                params["doc_id"] = part
        return params

    def _read_path(self, path: str, max_pages: int = 0) -> str:
        if not os.path.exists(path):
            return self._format_result(
                status="failed",
                message=f"文件路径不存在: {path}",
                details={
                    "error_type": "file_not_found",
                    "suggestions": [
                        "检查文件路径是否正确",
                        "确认文件是否存在于指定位置",
                        "使用绝对路径而不是相对路径"
                    ]
                }
            )
        try:
            text = parse_file(path, max_pages=max_pages)
            file_name = os.path.basename(path)
            file_size = os.path.getsize(path)
            
            return self._format_result(
                status="success",
                message=f"成功读取文档: {file_name}",
                details={
                    "content": text,
                    "file_info": {
                        "name": file_name,
                        "size": file_size,
                        "path": path,
                        "pages_processed": max_pages if max_pages > 0 else "all"
                    }
                }
            )
        except Exception as e:
            return self._format_result(
                status="failed",
                message=f"文档读取错误: {path}",
                details={
                    "error_type": "parse_error",
                    "error_message": str(e),
                    "suggestions": [
                        "检查文档格式是否支持",
                        "确认文档没有损坏",
                        "尝试使用不同的解析参数"
                    ]
                }
            )

    def _run(self, query: str) -> str:
        params = self._parse_q(query)
        doc_id = params.get("doc_id")
        path = params.get("path")
        max_pages = int(params.get("max_pages", 0))

        if doc_id:
            # memory 存储的是 metadata 包括 path 和 snippet
            if not self.memory:
                return self._format_result(
                    status="failed",
                    message="内存管理器不可用",
                    details={
                        "error_type": "memory_unavailable",
                        "suggestions": [
                            "检查内存管理器是否正确初始化",
                            "确认文档已正确注册到内存中"
                        ]
                    }
                )
            doc = self.memory.get_document(doc_id)
            if not doc:
                # 兼容：若 doc_id 实际是路径
                if os.path.exists(doc_id):
                    return self._read_path(doc_id, max_pages)
                return self._format_result(
                    status="failed",
                    message=f"文档ID未找到: {doc_id}",
                    details={
                        "error_type": "doc_id_not_found",
                        "suggestions": [
                            "检查文档ID是否正确",
                            "确认文档已正确注册",
                            "尝试使用文件路径而不是文档ID"
                        ]
                    }
                )
            # 返回更大片段或全文片段
            content = doc.get("full_text_snippet", doc.get("preview", ""))
            return self._format_result(
                status="success",
                message=f"成功读取文档: {doc_id}",
                details={
                    "content": content,
                    "doc_info": {
                        "doc_id": doc_id,
                        "preview_available": bool(doc.get("preview")),
                        "full_text_available": bool(doc.get("full_text_snippet"))
                    }
                }
            )
        elif path:
            return self._read_path(path, max_pages)
        else:
            return self._format_result(
                status="failed",
                message="缺少必要参数",
                details={
                    "error_type": "missing_parameters",
                    "suggestions": [
                        "请提供doc_id=<id>或path=/完整路径",
                        "检查参数格式是否正确"
                    ]
                }
            )