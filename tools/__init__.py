# openmanus_lc/tools/__init__.py
"""OpenManus-LC 工具模块"""

# 从baidu_search.py导出百度搜索工具


# 从file_reader.py导出文件读取工具


# 从python_exec.py导出Python代码执行工具
from tools.python_exec import PythonExecTool

# 从web_search.py导出网页搜索工具
from tools.web_search import WebSearchTool

__all__ = [
    "PythonExecTool",
    "WebSearchTool"
]