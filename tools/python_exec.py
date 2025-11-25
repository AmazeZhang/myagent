# tools/python_exec.py
from core.tool_base import BaseManusTool
import ast
import json

class PythonExecTool(BaseManusTool):
    name:str = "python_exec"
    description:str = "安全地执行简单的Python表达式。支持结构化返回格式，包含状态、消息和详细信息。示例: python_exec 2+3*5 或 python_exec {'a':1}"

    def _format_result(self, status: str, message: str, details: dict = None) -> str:
        """格式化返回结果"""
        result = {
            "status": status,
            "message": message,
            "details": details or {}
        }
        return json.dumps(result, ensure_ascii=False)

    def _run(self, code: str) -> str:
        code = code.strip()
        if not code:
            return self._format_result(
                status="failed",
                message="未提供Python代码",
                details={
                    "error_type": "no_code_provided",
                    "suggestions": [
                        "请提供要执行的Python表达式",
                        "检查参数是否为空"
                    ]
                }
            )

        # 首先尝试用 ast.literal_eval（安全）解析
        try:
            val = ast.literal_eval(code)
            return self._format_result(
                status="success",
                message="Python表达式执行成功",
                details={
                    "result": val,
                    "result_type": type(val).__name__,
                    "evaluation_method": "literal_eval",
                    "code_snippet": code
                }
            )
        except Exception as e:
            # 如果不是简单 literal，则限制为单表达式 eval（禁止 names）
            try:
                parsed = ast.parse(code, mode="eval")
                # Walk AST to ensure no Name, Attribute, Call etc exist (only allow literals, BinOp, UnaryOp, BoolOp, Compare, Tuple/List/Dict)
                for node in ast.walk(parsed):
                    from ast import (Expression, BinOp, UnaryOp, Num, Constant, BoolOp,
                                     Compare, NameConstant, List, Tuple, Dict, Load,
                                     Subscript, Index, Slice)
                    # allow certain safe nodes
                    allowed = (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Num, ast.Constant,
                               ast.BoolOp, ast.Compare, ast.List, ast.Tuple, ast.Dict,
                               ast.Load, ast.Subscript, ast.Index, ast.Slice)
                    if not isinstance(node, allowed):
                        # Disallow function calls, names, attributes, imports, lambdas, etc.
                        return self._format_result(
                            status="failed",
                            message="不安全的Python表达式或不受支持的结构",
                            details={
                                "error_type": "unsafe_expression",
                                "error_message": "检测到不安全的Python结构",
                                "suggestions": [
                                    "仅支持简单的数学表达式和数据结构",
                                    "避免使用函数调用、变量名、属性访问等",
                                    "尝试使用更简单的表达式"
                                ]
                            }
                        )
                # safe eval with empty globals/locals
                result = eval(compile(parsed, "<string>", "eval"), {"__builtins__": {}}, {})
                return self._format_result(
                    status="success",
                    message="Python表达式执行成功",
                    details={
                        "result": result,
                        "result_type": type(result).__name__,
                        "evaluation_method": "safe_eval",
                        "code_snippet": code
                    }
                )
            except SyntaxError as e:
                return self._format_result(
                    status="failed",
                    message="Python语法错误",
                    details={
                        "error_type": "syntax_error",
                        "error_message": str(e),
                        "suggestions": [
                            "检查Python语法是否正确",
                            "确认表达式格式正确",
                            "尝试简化表达式"
                        ]
                    }
                )
            except Exception as e:
                return self._format_result(
                    status="failed",
                    message="Python表达式执行错误",
                    details={
                        "error_type": "evaluation_error",
                        "error_message": str(e),
                        "suggestions": [
                            "检查表达式逻辑是否正确",
                            "确认操作数类型兼容",
                            "尝试使用更简单的表达式"
                        ]
                    }
                )