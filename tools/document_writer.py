# tools/document_writer.py
from core.tool_base import BaseManusTool
from utils.file_utils import make_path_for_output
from docx import Document
import os
import json

class DocumentWriterTool(BaseManusTool):
    name:str = "document_writer"
    description:str = "将内容写入文件。支持结构化返回格式，包含状态、消息和详细信息。用法: document_writer path=./out.txt, format=txt|docx, content=... (content可能很长)"

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
                k,v = part.split("=",1)
                params[k.strip()] = v.strip()
        return params

    def _run(self, query: str) -> str:
        params = self._parse_q(query)
        path = params.get("path") or make_path_for_output(params.get("filename","output.txt"))
        fmt = params.get("format", "txt").lower()
        content = params.get("content", "")
        
        if not content:
            return self._format_result(
                status="failed",
                message="缺少内容参数",
                details={
                    "error_type": "missing_content",
                    "suggestions": [
                        "请提供要写入的内容",
                        "检查content参数是否正确设置"
                    ]
                }
            )
        
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(path), exist_ok=True)
            
            if fmt == "txt":
                with open(path, "w", encoding="utf-8") as f:
                    f.write(content)
                file_info = {
                    "format": "txt",
                    "size_bytes": len(content.encode('utf-8')),
                    "lines": len(content.splitlines())
                }
            elif fmt == "docx":
                doc = Document()
                # naive split into paragraphs
                for line in content.splitlines():
                    doc.add_paragraph(line)
                doc.save(path)
                file_info = {
                    "format": "docx",
                    "size_bytes": os.path.getsize(path),
                    "paragraphs": len(content.splitlines())
                }
            else:
                return self._format_result(
                    status="failed",
                    message=f"不支持的格式: {fmt}",
                    details={
                        "error_type": "unsupported_format",
                        "supported_formats": ["txt", "docx"],
                        "suggestions": [
                            "使用txt格式保存文本文件",
                            "使用docx格式保存Word文档"
                        ]
                    }
                )
            
            return self._format_result(
                status="success",
                message=f"文件写入成功: {path}",
                details={
                    "file_path": path,
                    "file_info": file_info,
                    "content_length": len(content),
                    "format_used": fmt
                }
            )
        except PermissionError as e:
            return self._format_result(
                status="failed",
                message=f"文件写入权限错误: {path}",
                details={
                    "error_type": "permission_error",
                    "error_message": str(e),
                    "suggestions": [
                        "检查文件路径权限",
                        "确认有写入权限",
                        "尝试使用不同的路径"
                    ]
                }
            )
        except Exception as e:
            return self._format_result(
                status="failed",
                message=f"文件写入错误: {str(e)}",
                details={
                    "error_type": "write_error",
                    "error_message": str(e),
                    "suggestions": [
                        "检查磁盘空间是否充足",
                        "确认文件路径有效",
                        "尝试使用不同的格式"
                    ]
                }
            )