# tools/web_tools_collection.py
from tools.web_search import WebSearchTool
from tools.web_browser_tool import WebBrowserTool
from tools.web_decision_tool import WebDecisionTool

# 核心网页工具集合
class WebToolsCollection:
    def __init__(self):
        self.tools = {
            "web_search": WebSearchTool(),
            "web_browser": WebBrowserTool(),
            "web_decide": WebDecisionTool()
        }
    
    def get_all_tools(self):
        """返回所有网页工具的列表"""
        return list(self.tools.values())
    
    def get_tool_by_name(self, name):
        """通过名称获取特定工具"""
        if name in self.tools:
            return self.tools[name]
        return None