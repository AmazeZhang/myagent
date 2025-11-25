import os
import dotenv
from langsmith import Client
from langchain_classic.callbacks.tracers.langchain import LangChainTracer

# 加载环境变量
dotenv.load_dotenv()

class LangSmithConfig:
    """LangSmith配置类"""
    
    def __init__(self):
        self.api_key = os.getenv("LANGSMITH_API_KEY")
        self.project_name = os.getenv("LANGSMITH_PROJECT", "openmanus-lc")
        self.endpoint = os.getenv("LANGSMITH_ENDPOINT", "https://api.smith.langchain.com")
        
    def is_configured(self):
        """检查LangSmith是否已配置"""
        return bool(self.api_key)
    
    def get_client(self):
        """获取LangSmith客户端"""
        if not self.is_configured():
            return None
        return Client(
            api_key=self.api_key,
            api_url=self.endpoint
        )
    
    def get_tracer(self):
        """获取LangSmith追踪器"""
        if not self.is_configured():
            return None
        return LangChainTracer(
            project_name=self.project_name,
            client=self.get_client()
        )
    
    def get_config_info(self):
        """获取配置信息"""
        return {
            "configured": self.is_configured(),
            "project_name": self.project_name,
            "endpoint": self.endpoint
        }

# 全局配置实例
langsmith_config = LangSmithConfig()