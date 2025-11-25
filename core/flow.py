# core/flow.py
from .agent import ManusAgent
from .registry import ToolRegistry

class BaseFlow:
    def __init__(self, agent: ManusAgent, registry: ToolRegistry):
        self.agent = agent
        self.registry = registry

    def run(self, user_input: str) -> str:
        # 这里可以在执行前注入 memory/context，也可以做输入 sanitize
        print("[Flow] Running plan+execute...")
        result = self.agent.execute(user_input)
        return result
