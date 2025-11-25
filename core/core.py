# core/core.py
from langchain_classic.agents import initialize_agent
from langchain_classic.llms import Ollama
from core.memory import MemoryManager, ConversationMemoryManager
from core.agent import ManusAgent  # 导入自定义 Agent
from core.registry import ToolRegistry  # 导入工具注册表
from core.multi_agent import MultiAgentOrchestrator  # 导入多Agent协调器
from utils.langsmith_config import langsmith_config  # 导入LangSmith配置
from utils.config_manager import config_manager  # 导入配置管理器

class ManusCore:
    def __init__(self, model_name: str = None):
        self.doc_memory = MemoryManager()  # 文档记忆
        self.chat_memory = ConversationMemoryManager()  # 对话记忆
        self.tools = []
        self.agent = None
        self.tool_registry = ToolRegistry()  # 创建工具注册表
        
        # 使用配置管理器中的模型名称或参数提供的模型名称
        self.model_name = model_name or config_manager.model_name
        self.multi_agent = MultiAgentOrchestrator(model_name=self.model_name)  # 创建多Agent协调器
        
        # LangSmith配置
        self.langsmith_config = langsmith_config
        self.langsmith_client = self.langsmith_config.get_client()
        self.langsmith_tracer = self.langsmith_config.get_tracer()
        
        # 打印LangSmith配置状态
        if self.langsmith_config.is_configured():
            print(f"🔍 LangSmith监控已启用 - 项目: {config_manager.langsmith_project}")
        else:
            print("⚠️  LangSmith监控未配置，请设置LANGSMITH_API_KEY环境变量")

    def register_tool(self, tool):
        self.tools.append(tool)
        self.tool_registry.register(tool)  # 同时注册到工具注册表
        self.multi_agent.register_tool(tool)  # 注册到多Agent系统

    def build_agent(self):
        # 使用自定义的 ManusAgent
        self.agent = ManusAgent(
            registry=self.tool_registry,
            model_name=self.multi_agent.model_name,
            temperature=config_manager.temperature,
            langsmith_tracer=self.langsmith_tracer  # 传递LangSmith追踪器
        )

    def run(self, query: str):
        if not self.agent:
            raise RuntimeError("Agent not built yet")

        # 构建包含文档信息的上下文
        documents = self.doc_memory.get_all()
        doc_context = ""
        if documents:
            doc_context = "【可用文档】\n" + "\n".join(
                [f"- ID: {doc_id}, 名称: {doc['name']}" for doc_id, doc in self.doc_memory.documents.items()]) + "\n\n"

        # 构建包含对话历史的上下文
        chat_history = self.chat_memory.load()
        chat_context = ""
        if chat_history:
            chat_context = "【对话历史】\n"
            # 使用配置管理器中的最大对话历史设置
            recent_history = chat_history[-config_manager.max_conversation_history*2:]  # 保存N轮对话（每轮包含用户和AI消息）
            for message in recent_history:
                role = "用户" if message.type == "human" else "助手"
                chat_context += f"{role}: {message.content}\n"
            chat_context += "\n"

        # 合并文档上下文和对话上下文
        full_context = doc_context + chat_context

        # 使用多Agent系统处理查询
        result = self.multi_agent.run(query, memory_context=full_context)
        final_answer = result["final_answer"]

        # 保存对话历史
        self.chat_memory.save(query, final_answer)

        # 返回完整结果，包括思考过程
        return result