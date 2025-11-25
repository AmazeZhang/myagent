"""错误恢复机制工具"""

from typing import Dict, List, Any, Optional
from utils.logger import setup_logger

logger = setup_logger(__name__)


class ErrorRecoveryManager:
    """错误恢复管理器"""
    
    def __init__(self):
        # 常见错误模式及其恢复策略
        self.error_patterns = {
            # 网络相关错误
            "网络超时": [
                "检查网络连接",
                "尝试使用其他网络工具",
                "调整请求超时参数"
            ],
            "连接拒绝": [
                "检查目标服务器是否在线",
                "验证API密钥是否正确",
                "尝试使用代理服务器"
            ],
            # API相关错误
            "API key": [
                "检查API密钥是否正确配置",
                "验证API密钥是否过期",
                "尝试使用备用API密钥"
            ],
            "rate limit": [
                "减少API调用频率",
                "实现请求节流",
                "等待一段时间后重试"
            ],
            # 解析错误
            "JSON": [
                "确保输入是有效的JSON格式",
                "使用try-except处理解析异常",
                "对输入进行预处理和验证"
            ],
            # 资源错误
            "内存不足": [
                "释放不必要的资源",
                "增加可用内存限制",
                "优化数据处理流程"
            ],
            "文件不存在": [
                "验证文件路径是否正确",
                "检查文件权限",
                "在操作前确认文件存在"
            ]
        }
        
    def get_recovery_suggestions(self, error_message: str) -> List[str]:
        """
        根据错误消息获取恢复建议
        
        Args:
            error_message: 错误消息文本
            
        Returns:
            恢复建议列表
        """
        suggestions = []
        error_lower = error_message.lower()
        
        # 查找匹配的错误模式
        for pattern, pattern_suggestions in self.error_patterns.items():
            if pattern.lower() in error_lower:
                suggestions.extend(pattern_suggestions)
        
        # 如果没有特定建议，提供通用建议
        if not suggestions:
            suggestions = [
                "检查错误消息并修复根本原因",
                "尝试重新执行操作",
                "检查相关资源是否可用"
            ]
        
        # 去重并返回
        return list(dict.fromkeys(suggestions))
    
    def analyze_error_trend(self, error_logs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        分析错误趋势，识别常见问题
        
        Args:
            error_logs: 错误日志列表
            
        Returns:
            错误分析结果
        """
        error_counts = {}
        tool_errors = {}
        
        for log in error_logs:
            # 统计错误类型
            error_msg = log.get("output", "").lower()
            if "[exception]" in error_msg or "[error]" in error_msg:
                tool_name = log.get("tool", "unknown")
                
                # 统计工具错误
                if tool_name not in tool_errors:
                    tool_errors[tool_name] = 0
                tool_errors[tool_name] += 1
                
                # 识别错误模式
                for pattern in self.error_patterns.keys():
                    if pattern.lower() in error_msg:
                        if pattern not in error_counts:
                            error_counts[pattern] = 0
                        error_counts[pattern] += 1
        
        # 找出最常见的错误
        most_common_error = max(error_counts.items(), key=lambda x: x[1]) if error_counts else None
        most_error_prone_tool = max(tool_errors.items(), key=lambda x: x[1]) if tool_errors else None
        
        analysis = {
            "total_errors": sum(error_counts.values()),
            "error_types": error_counts,
            "tool_errors": tool_errors,
            "most_common_error": most_common_error,
            "most_error_prone_tool": most_error_prone_tool
        }
        
        return analysis
    
    def generate_recovery_plan(self, error_message: str, tool_name: str = None) -> Dict[str, Any]:
        """
        生成错误恢复计划
        
        Args:
            error_message: 错误消息
            tool_name: 工具名称（可选）
            
        Returns:
            恢复计划
        """
        suggestions = self.get_recovery_suggestions(error_message)
        
        plan = {
            "error_message": error_message,
            "tool_name": tool_name,
            "suggestions": suggestions,
            "immediate_actions": suggestions[:2],  # 立即执行的操作
            "follow_up_actions": suggestions[2:] if len(suggestions) > 2 else []  # 后续操作
        }
        
        return plan


# 创建全局错误恢复管理器实例
error_recovery_manager = ErrorRecoveryManager()