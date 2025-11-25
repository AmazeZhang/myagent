# core/tool_base.py
from langchain.tools import BaseTool
from typing import Optional, Any
import asyncio

class BaseManusTool(BaseTool):
    """基础工具抽象：对 langchain.BaseTool 做小包装，所有工具继承本类。"""
    name: str = "base_tool"
    description: str = "Base class for Manus tools."
    memory: Optional[Any] = None

    def _run(self, query: str) -> str:
        raise NotImplementedError()

    async def _arun(self, query: str) -> str:
        # 实现真正的异步逻辑，使用asyncio.to_thread避免阻塞事件循环
        return await asyncio.to_thread(self._run, query)

    # 为了更明确的 typing / 外部调用，暴露一个同步的 call 方法
    def call(self, query: str) -> Any:
        return self._run(query)
        
    # 添加异步调用方法
    async def acall(self, query: str) -> Any:
        return await self._arun(query)