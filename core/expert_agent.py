# core/expert_agent.py
import json, re, asyncio
from typing import Dict, Any, List
from core.registry import ToolRegistry
from langchain_ollama import ChatOllama
from core.tool_base import BaseManusTool

class ExpertAgent:
    """专业Agent类，专注于特定领域，不知道自己是"某某专家" """

    def __init__(self, name: str, description: str, registry: ToolRegistry,
                 model_name: str = "llama3", temperature: float = 0.2, llm=None):
        self.name = name
        self.description = description
        self.registry = registry
        self.model_name = model_name
        self.temperature = temperature
        
        # 如果提供了llm参数，使用提供的llm，否则创建默认的ChatOllama
        if llm is not None:
            self.llm = llm
        else:
            self.llm = ChatOllama(model=model_name, temperature=temperature)



    def register_tool_to_all_experts(self, tool):
        """注册工具到所有专家"""
        self.registry.register(tool)  # 将self.tool_registry改为self.registry

    def _extract_json(self, text: str) -> str:
        """提取JSON内容"""
        m = re.search(r"(\{.*\}|\[.*\])", text, re.S)
        return m.group(1) if m else text

    def _get_expert_specific_prompt(self) -> str:
        """获取专家特定的prompt模板 - 专注于专业领域，不提及专家身份"""
        if self.name == "search_expert":
            return """
            你是一个专注于信息搜索和获取的专业助手。你的专长是：

            核心能力：
            - 使用搜索工具获取最新、最准确的信息
            - 处理图片搜索、下载和截图任务
            - 获取新闻、天气等实时数据
            - 网络资源的高效获取和整理

            处理原则：
            1. 优先考虑使用搜索工具获取最新信息
            2. 对于需要实时数据的问题，立即进行搜索
            3. 图片相关任务采用搜索+下载/截图的策略
            4. 确保信息的时效性和准确性

            工作方式：
            - 分析用户需求，制定合适的搜索策略
            - 使用合适的工具获取所需信息
            - 对获取的信息进行整理和验证
            - 提供准确、可靠的答案

            可用工具：{tools}
            """
        elif self.name == "document_expert":
            return """
            你是一个专注于文档处理和分析的专业助手。你的专长是：

            核心能力：
            - 文档内容的深度阅读和分析
            - 文件内容的提取、整理和转换
            - 文档格式的处理和优化
            - 文件上传下载的智能管理

            处理原则：
            1. 优先使用文档处理工具分析内容
            2. 仔细检查文档结构和信息完整性
            3. 确保文档处理的准确性和可靠性
            4. 提供清晰、有条理的文档分析结果

            工作方式：
            - 仔细分析文档相关需求
            - 使用合适的工具处理文档
            - 提取关键信息并进行整理
            - 提供专业的文档处理结果

            工具使用说明：
            - document_reader工具：用于读取已注册的文档，格式为：document_reader doc_id=<文档ID>
            - 文档ID是系统自动分配的标识符，不是文件名
            - 例如：读取ID为81056773的文档，应使用：document_reader doc_id=81056773

            可用工具：{tools}
            """
        elif self.name == "general_expert":
            return """
            你是一个处理综合性问题的专业助手。你的专长是：

            核心能力：
            - 处理各种类型的问题和任务
            - 综合分析多领域信息
            - 提供全面、系统的解决方案
            - 协调使用多种工具和资源

            处理原则：
            1. 根据问题性质选择最合适的处理方式
            2. 综合考虑各种可能的解决方案
            3. 确保问题得到全面、彻底的解决
            4. 提供实用、可行的建议和答案

            工作方式：
            - 全面分析用户需求
            - 制定综合性的处理方案
            - 协调使用多种工具和资源
            - 提供完整的解决方案

            可用工具：{tools}
            """
        else:
            return "你是一个专业AI助手，请根据你的专长处理用户请求。\n可用工具：{tools}"

    def plan(self, user_input: str, memory_context: str = "") -> Dict[str, Any]:
        """专家特定的计划生成方法 - 专注于专业领域"""
        expert_prompt = self._get_expert_specific_prompt().format(
            tools=self.registry.list_names()
        )
        
        # 增强工具使用格式说明，特别强调网页操作
        tool_format_guide = """
        重要工具使用格式说明：
        
        web_search工具：web_search query="搜索关键词" [, engine="baidu/google/bing"] [, num=5]
        示例：web_search query="日本旅游攻略" engine="baidu" num=5
        
        web_browser工具：web_browser action="go_to_url" url="网页URL" [, session_id="会话ID"]
        示例：web_browser action="go_to_url" url="https://www.japan.travel/en"
        
        web_browser工具支持多种操作类型：
        - go_to_url: 访问指定URL
        - click_element: 点击页面元素
        - take_screenshot: 截取网页截图
        - input_text: 在输入框中输入文本
        - scroll_page: 滚动页面
        - get_page_info: 获取页面信息
        
        web_decision工具：web_decision task="任务描述" [, current_state="当前状态"]
        示例：web_decision task="选择最适合历史景点、文化体验和求婚地点的城市"
        
        网页操作触发条件：
        - 当用户明确要求截图、点击、浏览网页时，优先使用web_browser
        - 对于需要交互的网页任务，使用web_browser的复杂操作
        - 对于需要决策的复杂任务，使用web_decision
        
        请严格按照上述格式调用工具，确保参数格式正确。
        """
        
        # 检测是否需要网页操作的关键词
        web_operation_keywords = ["截图", "截屏", "点击", "浏览", "访问网页", "网页操作", "交互", "填写", "输入", "滚动", "页面"]
        needs_web_operation = any(keyword in user_input for keyword in web_operation_keywords)
        
        # 根据需求调整提示
        operation_guidance = ""
        if needs_web_operation and self.name == "search_expert":
            operation_guidance = """
            重要提示：检测到用户请求涉及网页操作，请优先考虑使用web_browser工具进行：
            - 网页访问和浏览
            - 页面截图操作
            - 元素点击和交互
            - 表单填写和提交
            
            请制定包含网页操作的计划。
            """
        
        full_prompt = f"""
    {expert_prompt}
    
    {tool_format_guide}
    
    {operation_guidance}
    
    用户要求: {user_input}
    
    {memory_context}
    
    请根据你的专业领域制定处理计划：
    - 专注于你的核心能力范围
    - 使用最适合的工具组合
    - 确保处理方案的专业性和有效性
    - 严格按照工具使用格式调用工具
    
    请判断是否需要调用外部工具来完成该请求。
    - 如果可以直接回答，返回 need_tool=false，并用字段 'final_answer' 给出直接回答；'plan' 为空列表
    - 如果需要工具，返回 need_tool=true，并返回 plan（一个步骤列表），每一步是对象：{{"tool": "<tool_name>", "input": "<tool_input>"}}
    - 请输出一个简短的 'thoughts' 字段，说明你的专业思考过程。
    
    请严格以 JSON 输出，格式如下：
    {{"need_tool": true, "plan": [{{"tool": "web_search", "input": "query=\\"日本旅游攻略\\" engine=\\"baidu\\" num=5"}}], "thoughts":"基于我的专业能力，我需要搜索相关信息..."}}
    或者
    {{"need_tool": false, "final_answer": "直接回答内容", "thoughts":"基于我的专业判断，这个问题可以直接回答..."}}
    
    只返回 JSON，不要额外的文字说明。
    """
    
        resp = self.llm.invoke(full_prompt).content
        try:
            js = self._extract_json(resp)
            parsed = json.loads(js)
            
            # 验证和修复工具调用格式
            if parsed.get("need_tool", False):
                plan = parsed.get("plan", [])
                for step in plan:
                    tool_name = step.get("tool", "")
                    tool_input = step.get("input", "")
                    
                    # 修复web_browser工具调用格式
                    if tool_name == "web_browser" and tool_input.startswith("http"):
                        step["input"] = f'action="go_to_url" url="{tool_input}"'
                    elif tool_name == "web_browser" and not tool_input.startswith("action="):
                        # 自动添加默认操作
                        step["input"] = f'action="go_to_url" {tool_input}'
                    
                    # 修复web_decision工具调用格式
                    elif tool_name == "web_decision" and not tool_input.startswith("task="):
                        step["input"] = f'task="{tool_input}"'
                    
                    # 修复web_search工具调用格式
                    elif tool_name == "web_search" and not tool_input.startswith("query="):
                        step["input"] = f'query="{tool_input}"'
            
            return parsed
        except Exception:
            # 回退：根据专家类型使用默认策略
            if self.name == "search_expert":
                # 修复搜索专家的默认调用格式
                if needs_web_operation:
                    parsed = {
                        "need_tool": True, 
                        "plan": [
                            {"tool": "web_search", "input": f'query="{user_input}" engine="baidu" num=3'},
                            {"tool": "web_browser", "input": f'action="go_to_url" url="根据搜索结果选择最相关网站"'}
                        ],
                        "thoughts": f"基于搜索专业能力，我需要搜索并访问网页获取详细信息: {user_input}"
                    }
                else:
                    parsed = {
                        "need_tool": True, 
                        "plan": [{"tool": "web_search", "input": f'query="{user_input}" engine="baidu" num=5'}],
                        "thoughts": f"基于搜索专业能力，我需要搜索获取信息: {user_input}"
                    }
            elif self.name == "document_expert":
                # 修复文档专家的默认调用格式
                parsed = {
                    "need_tool": True, 
                    "plan": [{"tool": "document_reader", "input": f'doc_id={user_input}'}],
                    "thoughts": f"基于文档处理专业能力，我需要处理文档相关任务: {user_input}"
                }
            else:
                # 修复通用专家的默认调用格式
                parsed = {
                    "need_tool": True, 
                    "plan": [{"tool": "web_search", "input": f'query="{user_input}" engine="baidu" num=5'}],
                    "thoughts": f"基于综合处理能力，我需要处理这个任务: {user_input}"
                }
        return parsed

    async def _execute_tool_safely(self, tool, tool_input: str) -> str:
        """安全执行工具，处理异步和超时问题"""
        try:
            # 设置超时保护
            if hasattr(tool, 'call'):
                result = tool.call(tool_input)
                # 检查是否是协程对象
                if asyncio.iscoroutine(result):
                    # 异步执行协程，设置超时
                    try:
                        result = await asyncio.wait_for(result, timeout=30.0)
                    except asyncio.TimeoutError:
                        return "[Timeout] 工具执行超时（30秒）"
                return str(result) if result is not None else ""
            else:
                return f"[Error] 工具 {tool.__class__.__name__} 没有 call 方法"
        except Exception as e:
            return f"[Exception] {str(e)}"

    async def execute_async(self, user_input: str, memory_context: str = "") -> Dict[str, Any]:
        """异步执行方法，避免阻塞"""
        tool_logs: List[Dict[str, str]] = []
        llm_thoughts = []
        plans = []
        final_answer = ""
        final_thoughts = ""
        max_rounds = 5  # 增加最大轮次，支持复杂网页操作
        round_num = 0
        intermediate_results = ""

        # 检测是否需要复杂网页操作
        complex_web_keywords = ["截图", "截屏", "点击", "交互", "填写", "输入", "滚动", "多步骤"]
        needs_complex_web_operation = any(keyword in user_input for keyword in complex_web_keywords)

        # 专家特定的执行逻辑
        while round_num < max_rounds:
            round_num += 1
            
            # 构建包含专业领域的完整上下文
            expert_context = f"专业领域: {self.description}\n{memory_context}"
            if intermediate_results:
                expert_context += f"\n\n之前的执行结果:\n{intermediate_results}"

            # 生成当前轮的计划（使用专家特定的plan方法）
            plan_obj = self.plan(user_input, memory_context=expert_context)
            current_thought = plan_obj.get("thoughts", "")
            llm_thoughts.append(f"第{round_num}轮思考: {current_thought}")

            # 如果不需要工具，直接生成最终答案
            if not plan_obj.get("need_tool", False):
                final_answer = plan_obj.get("final_answer", "")
                final_thoughts = f"基于我的专业能力，我直接回答了这个问题"
                break

            # 只记录当前轮的计划，不重复添加
            current_plan = plan_obj.get("plan", [])
            if round_num == 1:
                plans.extend(current_plan)

            # 执行工具调用
            current_tool_logs = []
            for i, step in enumerate(current_plan):
                tool_name = step.get("tool")
                tool_input = step.get("input", "")

                # 检查是否已经执行过相同的工具调用（放宽重复检测）
                already_executed = False
                for existing_log in tool_logs:
                    if existing_log.get("tool") == tool_name and existing_log.get("input") == tool_input:
                        # 对于网页操作，允许重复执行（如多次点击、截图）
                        if tool_name == "web_browser" and "action=" in tool_input:
                            # 检查是否是相同的网页操作
                            if "action=go_to_url" in tool_input and "action=go_to_url" in existing_log.get("input", ""):
                                already_executed = True
                                break
                        else:
                            already_executed = True
                            break
                
                if already_executed:
                    # 跳过重复执行，但记录跳过信息
                    log = {"step": len(tool_logs) + 1, "tool": tool_name, "input": tool_input,
                           "output": f"[跳过] 已执行过相同的工具调用"}
                else:
                    tool = self.registry.get_tool(tool_name)
                    if not tool:
                        log = {"step": len(tool_logs) + 1, "tool": tool_name, "input": tool_input,
                               "output": f"[Error] tool '{tool_name}' not found"}
                    else:
                        # 使用安全的异步执行
                        output = await self._execute_tool_safely(tool, tool_input)
                        log = {"step": len(tool_logs) + 1, "tool": tool_name, "input": tool_input, "output": output}
                
                current_tool_logs.append(log)

            tool_logs.extend(current_tool_logs)

            # 更新中间结果
            current_results = "\n\n".join(
                [f"Step {l['step']} - {l['tool']}({l['input']}):\n{l['output']}" for l in current_tool_logs])
            intermediate_results += ("\n\n" if intermediate_results else "") + current_results

            # 检查是否已经获得足够信息可以生成最终答案
            # 对于复杂网页操作，放宽终止条件
            if needs_complex_web_operation:
                # 复杂网页操作需要更多轮次
                if len(tool_logs) >= 4 and round_num >= 3:  # 至少执行4个工具调用，3轮以上
                    break
            else:
                if len(tool_logs) >= 3:  # 普通任务至少执行3个工具调用
                    break

        # 如果需要，生成最终答案
        if not final_answer:
            # 过滤掉重复和跳过的日志
            valid_logs = [log for log in tool_logs if "[跳过]" not in log.get("output", "") and "[Error]" not in log.get("output", "")]
            
            if valid_logs:
                aggregate = "工具执行结果：\n" + "\n\n".join(
                    [f"Step {l['step']} - {l['tool']}({l['input']}):\n{l['output']}" for l in valid_logs])
                
                summary_prompt = f"""
请基于以下执行结果给出最终答案：

用户问题: {user_input}
专业领域: {self.description}
执行结果: {aggregate}

请给出：
1) 'final_answer'：面向用户的专业答案
2) 'final_thoughts'：说明你的专业思考过程

请以 JSON 返回：{{"final_answer":"...","final_thoughts":"..."}}
"""
                resp2 = self.llm.invoke(summary_prompt).content
                try:
                    js2 = self._extract_json(resp2)
                    parsed2 = json.loads(js2)
                    final_answer = parsed2.get("final_answer", "")
                    final_thoughts = parsed2.get("final_thoughts", f"基于我的专业能力完成了任务")
                except Exception:
                    final_answer = aggregate
                    final_thoughts = f"基于专业能力的执行结果"
            else:
                final_answer = "未能获取有效的文档内容，请检查文档ID是否正确或重新上传文档。"
                final_thoughts = "工具执行过程中出现错误或重复调用"

        return {
            "final_answer": final_answer,
            "final_thoughts": final_thoughts,
            "llm_thoughts": llm_thoughts,
            "plan": plans,  # 只包含第一轮的计划
            "tool_logs": tool_logs,
            "expert_name": self.name,
            "expert_description": self.description
        }

    def execute(self, user_input: str, memory_context: str = "") -> Dict[str, Any]:
        """同步执行方法，包装异步执行"""
        try:
            # 创建新的事件循环来运行异步代码
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(self.execute_async(user_input, memory_context))
            loop.close()
            return result
        except Exception as e:
            return {
                "final_answer": f"执行过程中出现错误: {str(e)}",
                "final_thoughts": "执行过程中出现异常",
                "llm_thoughts": [],
                "plan": [],
                "tool_logs": [],
                "expert_name": self.name,
                "expert_description": self.description
            }

    def process(self, query: str, memory_context: str = "") -> Dict[str, Any]:
        """处理查询的入口方法"""
        return self.execute(query, memory_context)


class ExpertAgentFactory:
    """专家Agent工厂 - 支持多种模型类型"""

    def __init__(self, model_name: str = "llama3", model_type: str = "ollama", registry: ToolRegistry = None):
        self.model_name = model_name
        self.model_type = model_type  # 添加模型类型
        self.registry = registry or ToolRegistry()  # 初始化registry
        self.tools = []

    def register_tool_to_all_experts(self, tool: BaseManusTool):
        """注册工具到所有专家"""
        self.tools.append(tool)

    def _create_llm(self):
        """根据模型类型创建LLM实例"""
        if self.model_type == "openrouter":
            from langchain_openai import ChatOpenAI
            from utils.config_manager import config_manager
            
            api_key = config_manager.openrouter_api_key
            if not api_key:
                raise Exception("OpenRouter API密钥未配置")
            
            # 清理模型名称
            clean_model_name = self.model_name
            if ":" in self.model_name:
                clean_model_name = self.model_name.split(":")[0]
            
            return ChatOpenAI(
                model=clean_model_name,
                temperature=0.2,
                openai_api_base="https://openrouter.ai/api/v1",
                openai_api_key=api_key,
                max_retries=2,
                timeout=30,
                default_headers={
                    "HTTP-Referer": "https://openmanus-lc", 
                    "X-Title": "OpenManus-LC"
                }
            )
        else:
            # 默认使用Ollama
            return ChatOllama(model=self.model_name, temperature=0.2)

    def create_search_expert(self) -> ExpertAgent:
        """创建搜索专家"""
        llm = self._create_llm()
        return ExpertAgent(
            name="search_expert",
            description="擅长网页搜索、实时信息获取、图片处理、网络交互等任务",
            registry=self.registry,  # 添加registry参数
            llm=llm
            # 移除tools参数
        )

    def create_document_expert(self) -> ExpertAgent:
        """创建文档专家"""
        llm = self._create_llm()
        return ExpertAgent(
            name="document_expert",
            description="擅长文档处理、文件操作、内容分析等任务",
            registry=self.registry,  # 添加registry参数
            llm=llm
            # 移除tools参数
        )

    def create_general_expert(self) -> ExpertAgent:
        """创建通用专家"""
        llm = self._create_llm()
        return ExpertAgent(
            name="general_expert",
            description="擅长一般性问题解答、综合处理、推理分析等任务",
            registry=self.registry,  # 添加registry参数
            llm=llm
            # 移除tools参数
        )

    def get_available_experts(self) -> Dict[str, str]:
        """获取可用专家列表"""
        return {
            "search_expert": "擅长网页搜索、实时信息获取、图片处理、网络交互等任务",
            "document_expert": "擅长文档处理、文件操作、内容分析等任务",
            "general_expert": "擅长一般性问题解答、综合处理、推理分析等任务"
        }

    def create_expert_by_name(self, expert_name: str) -> ExpertAgent:
        """根据名称创建专家"""
        creators = {
            "search_expert": self.create_search_expert,
            "document_expert": self.create_document_expert,
            "general_expert": self.create_general_expert
        }

        if expert_name in creators:
            return creators[expert_name]()
        else:
            return self.create_general_expert()

    def register_tool_to_all_experts(self, tool):
        """注册工具到所有专家"""
        self.tools.append(tool)
        self.registry.register(tool)  # 添加这一行，确保工具也注册到registry

    def get_available_experts(self) -> Dict[str, str]:
        """获取可用的专家列表及其描述"""
        return {
            "search_expert": "搜索专家 - 实时信息、网络数据、图片处理",
            "document_expert": "文档专家 - 文档处理、文件分析、内容阅读", 
            "general_expert": "通用专家 - 一般问题、综合任务、多领域协调"
        }