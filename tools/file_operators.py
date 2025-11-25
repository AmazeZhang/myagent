# tools/file_operators.py
from core.tool_base import BaseManusTool
import os
import json

class FileOperatorsTool(BaseManusTool):
    name: str = "file_operators"
    description: str = '''文件操作工具，用于创建、读取、写入和管理文件与目录。用法:
    - 读取文件: file_operators action=read_file path=/path/to/file.txt max_chars=4000
    - 写入文件: file_operators action=write_file path=/path/to/file.txt content=文件内容
    - 创建目录: file_operators action=create_directory path=/path/to/dir
    - 列出目录: file_operators action=list_directory path=/path/to/di'''
    
    def _format_result(self, success: bool, message: str, details: dict = None) -> str:
        """格式化返回结果"""
        result = {
            "status": "success" if success else "failed",
            "message": message,
            "details": details or {}
        }
        return json.dumps(result, ensure_ascii=False)
    
    def _parse_query(self, query: str) -> dict:
        """解析查询参数"""
        params = {}
        # 解析格式：action=write_file, path=/path/to/file.txt, content=文件内容
        parts = [p.strip() for p in query.split(",")]
        for part in parts:
            if "=" in part:
                key, value = part.split("=", 1)
                params[key.strip()] = value.strip()
        return params
    
    def _write_file(self, path: str, content: str) -> dict:
        """写入文件内容"""
        try:
            # 确保目录存在
            directory = os.path.dirname(path)
            if directory and not os.path.exists(directory):
                os.makedirs(directory, exist_ok=True)
            
            # 写入文件
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            return {
                "file_path": path,
                "file_size": len(content),
                "status": "file_written"
            }
        except Exception as e:
            raise Exception(f"写入文件失败: {str(e)}")
    
    def _create_directory(self, path: str) -> dict:
        """创建目录"""
        try:
            os.makedirs(path, exist_ok=True)
            return {
                "directory_path": path,
                "status": "directory_created"
            }
        except Exception as e:
            raise Exception(f"创建目录失败: {str(e)}")
    
    def _read_file(self, path: str, max_chars: int = 4000) -> dict:
        """读取文件内容"""
        if not os.path.exists(path):
            raise Exception(f"文件不存在: {path}")
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read(max_chars)
            
            return {
                "file_path": path,
                "content": content,
                "file_size": os.path.getsize(path),
                "status": "file_read"
            }
        except UnicodeDecodeError:
            raise Exception(f"无法解码文件: {path}，可能是二进制文件")
        except PermissionError:
            raise Exception(f"没有权限读取文件: {path}")
        except Exception as e:
            raise Exception(f"读取文件失败: {str(e)}")
    
    def _list_directory(self, path: str) -> dict:
        """列出目录内容"""
        if not os.path.exists(path):
            raise Exception(f"目录不存在: {path}")
        
        if not os.path.isdir(path):
            raise Exception(f"指定路径不是目录: {path}")
        
        try:
            items = os.listdir(path)
            files = []
            directories = []
            
            for item in items:
                item_path = os.path.join(path, item)
                if os.path.isfile(item_path):
                    files.append({
                        "name": item,
                        "size": os.path.getsize(item_path),
                        "path": item_path
                    })
                elif os.path.isdir(item_path):
                    directories.append({
                        "name": item,
                        "path": item_path
                    })
            
            return {
                "directory_path": path,
                "files": files,
                "directories": directories,
                "total_files": len(files),
                "total_directories": len(directories),
                "status": "directory_listed"
            }
        except PermissionError:
            raise Exception(f"没有权限访问目录: {path}")
        except Exception as e:
            raise Exception(f"列出目录失败: {str(e)}")
    
    def _run(self, query: str) -> str:
        try:
            params = self._parse_query(query)
            action = params.get("action")
            
            if action == "write_file":
                path = params.get("path")
                content = params.get("content", "")
                if not path:
                    return self._format_result(False, "缺少文件路径参数")
                result = self._write_file(path, content)
                return self._format_result(True, f"成功写入文件: {path}", result)
            
            elif action == "create_directory":
                path = params.get("path")
                if not path:
                    return self._format_result(False, "缺少目录路径参数")
                result = self._create_directory(path)
                return self._format_result(True, f"成功创建目录: {path}", result)
            
            elif action == "read_file":
                path = params.get("path")
                if not path:
                    return self._format_result(False, "缺少文件路径参数")
                max_chars = int(params.get("max_chars", 4000))
                result = self._read_file(path, max_chars)
                return self._format_result(True, f"成功读取文件: {path}", result)
            
            elif action == "list_directory":
                path = params.get("path")
                if not path:
                    return self._format_result(False, "缺少目录路径参数")
                result = self._list_directory(path)
                return self._format_result(True, f"成功列出目录: {path}", result)
            
            else:
                return self._format_result(False, f"未知操作: {action}")
        
        except Exception as e:
            return self._format_result(False, str(e), {"error": str(e)})