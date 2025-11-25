import os
from typing import Optional, Dict, Any


class ConfigManager:
    """集中式配置管理器
    
    负责从环境变量加载配置，并提供统一的配置访问接口
    使用单例模式确保全局配置一致性
    """
    
    _instance: Optional['ConfigManager'] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        """初始化配置，从环境变量加载"""
        # 获取项目根目录
        PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        # 模型配置
        self.model_name = os.getenv("MODEL_NAME", "qwen3:14b")
        self.temperature = float(os.getenv("TEMPERATURE", "0.2"))
        
        # OpenAI 配置
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.openai_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        
        # OpenRouter 配置
        self.openrouter_api_key = os.getenv("OPENROUTER_API_KEY")
        self.openrouter_model = os.getenv("OPENROUTER_MODEL", "")  # 设置为空，从界面获取
        
        # Ollama 配置
        self.ollama_model = os.getenv("OLLAMA_MODEL", "qwen3:14b")
        
        # LangSmith 配置
        self.langchain_tracing = os.getenv("LANGCHAIN_TRACING_V2", "false").lower() == "true"
        self.langsmith_api_key = os.getenv("LANGSMITH_API_KEY")
        self.langsmith_project = os.getenv("LANGSMITH_PROJECT", "openmanus-lc")
        self.langsmith_endpoint = os.getenv("LANGSMITH_ENDPOINT", "https://api.smith.langchain.com")
        
        # 应用配置
        self.max_retries = int(os.getenv("MAX_RETRIES", "3"))
        self.max_conversation_history = int(os.getenv("MAX_CONVERSATION_HISTORY", "10"))
        self.max_tool_output_length = int(os.getenv("MAX_TOOL_OUTPUT_LENGTH", "2000"))
        
        # 日志配置（使用绝对路径）
        log_dir_from_env = os.getenv("LOG_DIR", "logs")
        self.LOG_DIR = os.path.join(PROJECT_ROOT, log_dir_from_env)
        self.LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
        
        # 文件路径配置
        self.upload_dir = os.path.join(PROJECT_ROOT, "assets", "uploads")
        self.screenshot_dir = os.path.join(PROJECT_ROOT, "assets", "screenshots")
        self.download_dir = os.path.join(PROJECT_ROOT, "assets", "downloads")
        
        # 创建必要的目录
        self._ensure_directories_exist()
    
    def _ensure_directories_exist(self):
        """确保必要的目录存在"""
        for directory in [self.upload_dir, self.screenshot_dir, self.download_dir, self.LOG_DIR]:
            if not os.path.exists(directory):
                os.makedirs(directory, exist_ok=True)
    
    def is_langsmith_configured(self) -> bool:
        """检查 LangSmith 是否配置正确"""
        return self.langchain_tracing and bool(self.langsmith_api_key)
    
    def is_openrouter_configured(self) -> bool:
        """检查 OpenRouter 是否配置正确"""
        return bool(self.openrouter_api_key)
    
    def get_config_dict(self) -> Dict[str, Any]:
        """获取所有配置的字典表示"""
        return {
            "model_name": self.model_name,
            "temperature": self.temperature,
            "openai_model": self.openai_model,
            "openrouter_model": self.openrouter_model,
            "ollama_model": self.ollama_model,
            "langchain_tracing": self.langchain_tracing,
            "langsmith_project": self.langsmith_project,
            "max_retries": self.max_retries,
            "max_conversation_history": self.max_conversation_history,
            "max_tool_output_length": self.max_tool_output_length,
            "LOG_DIR": self.LOG_DIR,
            "LOG_LEVEL": self.LOG_LEVEL
        }
    
    def update_config(self, **kwargs):
        """动态更新配置"""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取配置项，如果不存在则返回默认值
        
        Args:
            key: 配置项名称
            default: 默认值
            
        Returns:
            配置项的值或默认值
        """
        return getattr(self, key, default)


# 创建全局配置实例
config_manager = ConfigManager()