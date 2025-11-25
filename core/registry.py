# core/registry.py
from typing import Dict, List
from .tool_base import BaseManusTool

class ToolRegistry:
    """工具注册中心，管理所有工具的注册/查询。"""
    def __init__(self):
        self.tools: Dict[str, BaseManusTool] = {}

    def register(self, tool: BaseManusTool):
        if tool.name in self.tools:
            raise ValueError(f"Tool '{tool.name}' already registered")
        self.tools[tool.name] = tool

    def get_tools(self) -> List[BaseManusTool]:
        return list(self.tools.values())

    def get_tool(self, name: str) -> BaseManusTool:
        return self.tools.get(name)

    def list_names(self):
        return list(self.tools.keys())
