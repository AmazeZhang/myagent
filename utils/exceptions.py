"""自定义异常类定义"""


class OpenManusBaseError(Exception):
    """OpenManus 项目的基础异常类"""
    def __init__(self, message: str, error_code: str = None, details: dict = None):
        self.message = message
        self.error_code = error_code or "GENERAL_ERROR"
        self.details = details or {}
        super().__init__(self.message)


class ToolExecutionError(OpenManusBaseError):
    """工具执行错误"""
    def __init__(self, message: str, tool_name: str = None, error_code: str = "TOOL_ERROR", details: dict = None):
        self.tool_name = tool_name
        super().__init__(message, error_code, details)


class LLMError(OpenManusBaseError):
    """LLM 调用错误"""
    def __init__(self, message: str, model_name: str = None, error_code: str = "LLM_ERROR", details: dict = None):
        self.model_name = model_name
        super().__init__(message, error_code, details)


class NetworkError(OpenManusBaseError):
    """网络相关错误"""
    def __init__(self, message: str, url: str = None, error_code: str = "NETWORK_ERROR", details: dict = None):
        self.url = url
        super().__init__(message, error_code, details)


class ResourceLimitError(OpenManusBaseError):
    """资源限制错误"""
    def __init__(self, message: str, resource_type: str = None, error_code: str = "RESOURCE_ERROR", details: dict = None):
        self.resource_type = resource_type
        super().__init__(message, error_code, details)


class ConfigurationError(OpenManusBaseError):
    """配置错误"""
    def __init__(self, message: str, config_key: str = None, error_code: str = "CONFIG_ERROR", details: dict = None):
        self.config_key = config_key
        super().__init__(message, error_code, details)