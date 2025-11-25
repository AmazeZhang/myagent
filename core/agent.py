# core/agent.py
import json, re
from typing import Any, Dict, List
from langchain_ollama import ChatOllama
from utils.logger import setup_logger, log_function_call, error_handler
from utils.exceptions import ToolExecutionError, LLMError, NetworkError

# 创建logger
logger = setup_logger(__name__)


class ManusAgent:
    """支持 Ollama 的改进 Agent：
       - plan() 要求返回 {need_tool: bool, plan: [...], thoughts: str}
       - execute() 会根据 need_tool 决定是否调用工具
       - 返回结构包含 final_answer、plan、tool_logs、llm_thoughts
    """

    def __init__(self, registry, model_name: str = "llama3", temperature: float = 0.2, langsmith_tracer=None):
        self.registry = registry
        try:
            self.llm = ChatOllama(model=model_name, temperature=temperature)
        except Exception as e:
            logger.error(f"初始化LLM失败: {e}")
            raise LLMError(f"无法初始化模型 {model_name}: {str(e)}", model_name=model_name)
        self.langsmith_tracer = langsmith_tracer  # 添加LangSmith追踪器

    @log_function_call
    def _extract_json(self, text: str) -> str:
        """从文本中提取JSON内容"""
        try:
            m = re.search(r"(\{.*\}|\[.*\])", text, re.S)
            return m.group(1) if m else text
        except Exception as e:
            logger.warning(f"提取JSON失败: {e}, 原始文本: {text[:100]}...")
            return text

    @log_function_call
    def _parse_tool_result(self, tool_output: str) -> Dict[str, Any]:
        """解析工具返回的结构化结果"""
        try:
            # 尝试解析JSON格式的结构化结果
            result = json.loads(tool_output)
            if isinstance(result, dict) and "status" in result:
                return result
        except json.JSONDecodeError as e:
            logger.debug(f"工具结果不是JSON格式: {e}")
        except Exception as e:
            logger.error(f"解析工具结果失败: {e}")
        
        # 如果不是结构化结果，返回默认格式
        return {
            "status": "unknown",
            "message": tool_output,
            "details": {}
        }

    def _is_tool_successful(self, tool_result: Dict[str, Any]) -> bool:
        """判断工具执行是否成功"""
        return tool_result.get("status") == "success"

    def _get_tool_suggestions(self, tool_result: Dict[str, Any]) -> str:
        """获取工具执行失败时的建议"""
        return tool_result.get("details", {}).get("suggestions", "")

    def _get_tool_descriptions(self) -> str:
        """从工具注册表中获取所有工具的描述信息"""
        try:
            tools = self.registry.get_tools()
            descriptions = []
            
            for tool in tools:
                desc = f"- {tool.name}: {tool.description}"
                descriptions.append(desc)
            
            return "\n".join(descriptions)
        except Exception as e:
            logger.error(f"获取工具描述失败: {e}")
            return "获取工具描述失败"

    @error_handler(max_retries=2, retry_delay=0.5, exceptions=(LLMError, Exception))
    @log_function_call
    def plan(self, user_input: str, memory_context: str = "", previous_results: List[Dict] = None) -> Dict[str, Any]:
        """请求 LLM 输出 plan（包含 need_tool 字段），基于之前的工具执行结果"""
        # 构建包含之前工具执行结果的上下文
        previous_context = ""
        if previous_results:
            previous_context = "\n\n【之前的工具执行结果】\n"
            for i, result in enumerate(previous_results, 1):
                parsed_result = self._parse_tool_result(result["output"])
                status = parsed_result.get("status", "unknown")
                message = parsed_result.get("message", "")[:200]  # 限制长度
                suggestions = self._get_tool_suggestions(parsed_result)
                
                previous_context += f"第{i}步 - {result['tool']}: 状态={status}, 结果={message}"
                if suggestions:
                    previous_context += f", 建议={suggestions}"
                previous_context += "\n"

        # 获取工具描述
        tool_descriptions = self._get_tool_descriptions()

        prompt = f"""
    你是一个人工智能助手。用户要求: {user_input}

    {memory_context}
    {previous_context}

    请判断是否需要调用外部工具来完成该请求，并基于之前的工具执行结果决定下一步行动。

    **重要指导原则**：
    1. **分析工具执行状态**：仔细检查之前工具的执行状态（success/failed/unknown）
    2. **基于失败原因调整策略**：如果工具失败，根据失败原因和提供的建议选择替代方案
    3. **多轮思考迭代**：每次思考→行动→观察后，基于观察结果决定下一步
    4. **工具失败处理**：如果某个工具失败，尝试使用功能相似的其他工具
    5. **网络问题处理**：如果网络连接失败，尝试不同的工具或调整参数

    **可用工具描述**：
    {tool_descriptions}

    **决策流程**：
    1. 首先分析用户需求，确定是否需要工具
    2. 如果有之前的工具执行结果，分析成功/失败状态
    3. 如果工具失败，根据失败原因和工具建议选择替代方案
    4. 如果所有工具都失败，考虑调整参数或使用不同的方法
    5. 如果可以直接回答，返回 need_tool=false

    **请严格以 JSON 输出**，格式如下：
    - 需要继续使用工具：
    {{"need_tool": true, "plan": [{{"tool": "tool_name", "input": "tool_input"}}], "thoughts":"基于之前结果的思考..."}}
    
    - 可以直接回答：
    {{"need_tool": false, "final_answer": "最终答案", "thoughts":"思考过程..."}}

    只返回 JSON，不要额外的文字说明。
    """
        
        try:
            resp = self.llm.invoke(prompt).content
            js = self._extract_json(resp)
            parsed = json.loads(js)
            return parsed
        except Exception as e:
            logger.error(f"LLM规划失败: {e}")
            # 回退：默认使用 web_search 单步
            return {"need_tool": True, "plan": [{"tool": "web_search", "input": user_input}],
                   "thoughts": "解析失败，使用默认工具搜索。"}

    @log_function_call
    def _extract_urls_from_search_results(self, search_output: str) -> List[str]:
        """从搜索结果中提取URL - 改进版本，支持JSON格式结果"""
        urls = []
        
        try:
            # 首先尝试解析为JSON格式（结构化结果）
            parsed_result = json.loads(search_output)
            if isinstance(parsed_result, dict) and parsed_result.get("status") == "success":
                # 从结构化结果的details中提取URL
                results = parsed_result.get("details", {}).get("results", [])
                if isinstance(results, list):
                    for result in results:
                        if isinstance(result, dict):
                            # 尝试从不同字段获取URL
                            if "url" in result:
                                urls.append(result["url"])
                            elif "link" in result:
                                urls.append(result["link"])
                            # 同时从snippet或description中提取URL
                            for field in ["snippet", "description", "content"]:
                                if field in result and isinstance(result[field], str):
                                    # 使用正则表达式从文本中提取URL
                                    for pattern in [r'https?://[^\s<>\"{}|\\^`\[\]]+']:
                                        matches = re.findall(pattern, result[field])
                                        urls.extend(matches)
        except json.JSONDecodeError:
            # 如果不是JSON格式，使用正则表达式提取URL
            url_patterns = [
                r'https?://[^\s<>\"{}|\\^`\[\]]+',  # 标准URL
                r'【[^】]+】\s*(https?://[^\s]+)',  # 百度搜索结果格式
            ]
            
            for pattern in url_patterns:
                matches = re.findall(pattern, search_output)
                for match in matches:
                    if isinstance(match, tuple):
                        url = match[0]  # 如果是分组匹配，取第一个分组
                    else:
                        url = match
                    urls.append(url)
        except Exception as e:
            logger.error(f"提取URL失败: {e}")
        
        # 过滤和去重
        filtered_urls = []
        seen = set()
        for url in urls:
            # 过滤掉示例URL和无效URL
            if (url and 
                isinstance(url, str) and
                not url.startswith('https://example.com') and
                not 'example.com' in url and
                len(url) > 10 and  # 基本URL长度检查
                url not in seen):
                seen.add(url)
                filtered_urls.append(url)
        
        logger.debug(f"从搜索结果中提取了 {len(filtered_urls)} 个有效URL")
        return filtered_urls

    @log_function_call
    def _extract_image_urls(self, urls: List[str]) -> List[str]:
        """从URL列表中提取图片URL"""
        image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.svg']
        image_urls = []
        
        try:
            for url in urls:
                # 检查URL是否包含图片扩展名
                if any(ext in url.lower() for ext in image_extensions):
                    image_urls.append(url)
                # 检查是否是常见的图片托管网站
                elif any(domain in url.lower() for domain in ['imgur.com', 'flickr.com', 'unsplash.com', 'pixabay.com', 'pexels.com', 'picsum.photos']):
                    image_urls.append(url)
        except Exception as e:
            logger.error(f"提取图片URL失败: {e}")
        
        return image_urls

    @error_handler(max_retries=1, retry_delay=1, exceptions=(Exception,))
    @log_function_call
    def execute(self, user_input: str, memory_context: str = "") -> Dict[str, Any]:
        """执行多轮思考和工具调用，基于工具返回的结构化结果进行决策"""
        # 简化的LangSmith追踪方式
        if self.langsmith_tracer:
            # 使用更简单的追踪方式
            self.langsmith_tracer.session_name = f"openmanus-query-{user_input[:50]}"
        
        tool_logs: List[Dict[str, str]] = []
        llm_thoughts = []
        plans = []
        final_answer = ""
        final_thoughts = ""  # 初始化final_thoughts变量
        max_rounds = 3  # 设置最大思考轮数
        round_num = 0
        intermediate_results = ""
        extracted_urls = []  # 存储从搜索结果中提取的URL
        failed_tools = set()  # 记录失败的工具
        tried_urls = set()  # 记录已经尝试过的URL

        # 进行多轮思考和执行
        while round_num < max_rounds:
            round_num += 1
            
            # LangSmith追踪：开始思考轮次
            if self.langsmith_tracer:
                self.langsmith_tracer.on_chain_start({
                    "round_num": round_num,
                    "current_tool_logs": tool_logs
                })
            
            try:
                # 生成当前轮的计划，传入之前的工具执行结果
                plan_obj = self.plan(user_input, memory_context=memory_context, previous_results=tool_logs)
                current_thought = plan_obj.get("thoughts", "")
                llm_thoughts.append(f"第{round_num}轮思考: {current_thought}")

                # 如果不需要工具，直接生成最终答案
                if not plan_obj.get("need_tool", False):
                    final_answer = plan_obj.get("final_answer", "")
                    final_thoughts = current_thought
                    # LangSmith追踪：记录直接回答
                    if self.langsmith_tracer:
                        self.langsmith_tracer.on_llm_start({
                            "prompt": "生成直接回答",
                            "thoughts": current_thought,
                            "final_answer": final_answer
                        })
                    break

                # 执行当前轮的计划
                current_plan = plan_obj.get("plan", [])
                plans.extend(current_plan)

                # 执行工具调用
                current_tool_logs = []
                tools_executed = set()
                round_success = True  # 标记本轮是否有工具成功执行

                for i, step in enumerate(current_plan):
                    tool_name = step.get("tool")
                    tool_input = step.get("input", "")
                    tools_executed.add(tool_name)

                    tool = self.registry.get_tool(tool_name)
                    if not tool:
                        log = {"step": len(tool_logs) + 1, "tool": tool_name, "input": tool_input,
                               "output": f"[Error] tool '{tool_name}' not found"}
                        current_tool_logs.append(log)
                        round_success = False
                        logger.error(f"工具 '{tool_name}' 不存在")
                        continue
                    
                    try:
                        # 如果是web_search工具，执行搜索并提取URL
                        if tool_name == "web_search":
                            out = tool.call(tool_input)
                            # 解析结构化结果
                            parsed_result = self._parse_tool_result(out)
                            # 从搜索结果中提取URL（如果成功）
                            if self._is_tool_successful(parsed_result):
                                new_urls = self._extract_urls_from_search_results(out)
                                # 过滤掉已经尝试过的URL
                                new_urls = [url for url in new_urls if url not in tried_urls]
                                extracted_urls.extend(new_urls)
                            log = {"step": len(tool_logs) + 1, "tool": tool_name, "input": tool_input, "output": out}
                            current_tool_logs.append(log)
                            if not self._is_tool_successful(parsed_result):
                                round_success = False
                                failed_tools.add(tool_name)
                                logger.warning(f"Web搜索工具执行失败: {parsed_result.get('message', '')}")
                            else:
                                logger.info(f"Web搜索成功，找到 {len(extracted_urls)} 个URL")
                        
                        # 如果是web_download工具，检查是否有可用的图片URL
                        elif tool_name == "web_download":
                            # 提取图片URL
                            image_urls = self._extract_image_urls(extracted_urls)
                            # 过滤掉已经尝试过的URL
                            image_urls = [url for url in image_urls if url not in tried_urls]
                            
                            if image_urls:
                                success = False
                                # 尝试多个图片URL
                                for img_url in image_urls[:3]:  # 最多尝试3个URL
                                    tried_urls.add(img_url)
                                    actual_input = f'url="{img_url}"'
                                    try:
                                        out = tool.call(actual_input)
                                        parsed_result = self._parse_tool_result(out)
                                        log = {"step": len(tool_logs) + 1, "tool": tool_name, "input": actual_input, "output": out}
                                        current_tool_logs.append(log)
                                        
                                        if self._is_tool_successful(parsed_result):
                                            success = True
                                            round_success = True
                                            logger.info(f"成功下载图片: {img_url}")
                                            break
                                        else:
                                            # 记录失败的工具和URL
                                            failed_tools.add(tool_name)
                                            logger.warning(f"下载图片失败: {img_url}，原因: {parsed_result.get('message', '')}")
                                    except Exception as e:
                                        logger.error(f"下载图片时发生异常: {e}")
                                        log = {"step": len(tool_logs) + 1, "tool": tool_name, "input": actual_input, 
                                               "output": f"[Exception] 下载图片失败: {str(e)}"}
                                        current_tool_logs.append(log)
                                
                                if not success and not round_success:
                                    round_success = False
                            else:
                                log = {"step": len(tool_logs) + 1, "tool": tool_name, "input": tool_input,
                                       "output": "[Info] 没有找到可用的图片URL，请先执行web_search获取图片链接"}
                                current_tool_logs.append(log)
                                round_success = False
                                failed_tools.add(tool_name)
                                
                                # 尝试替代工具web_screenshot
                                if "web_screenshot" not in failed_tools and extracted_urls:
                                    # 使用第一个提取的URL尝试截图
                                    screenshot_url = extracted_urls[0]
                                    screenshot_input = f'url="{screenshot_url}"'
                                    screenshot_tool = self.registry.get_tool("web_screenshot")
                                    if screenshot_tool:
                                        try:
                                            screenshot_out = screenshot_tool.call(screenshot_input)
                                            screenshot_log = {"step": len(tool_logs) + 2, "tool": "web_screenshot", "input": screenshot_input, "output": screenshot_out}
                                            current_tool_logs.append(screenshot_log)
                                            tools_executed.add("web_screenshot")
                                            
                                            # 检查截图是否成功
                                            if self._is_tool_successful(self._parse_tool_result(screenshot_out)):
                                                round_success = True
                                                failed_tools.discard(tool_name)
                                                logger.info(f"使用替代工具web_screenshot成功")
                                        except Exception as e:
                                            logger.error(f"使用替代工具失败: {e}")
                        
                        # 如果是web_screenshot工具，检查是否有可用的网页URL
                        elif tool_name == "web_screenshot" and extracted_urls:
                            # 过滤掉图片URL，使用网页URL
                            image_urls = self._extract_image_urls(extracted_urls)
                            webpage_urls = [url for url in extracted_urls if url not in image_urls]
                            webpage_urls = [url for url in webpage_urls if url not in tried_urls]
                            
                            if webpage_urls:
                                # 使用第一个网页URL进行截图
                                actual_url = webpage_urls[0]
                                tried_urls.add(actual_url)
                                actual_input = f'url="{actual_url}"'
                                try:
                                    out = tool.call(actual_input)
                                    log = {"step": len(tool_logs) + 1, "tool": tool_name, "input": actual_input, "output": out}
                                    current_tool_logs.append(log)
                                    
                                    if self._is_tool_successful(self._parse_tool_result(out)):
                                        round_success = True
                                        logger.info(f"成功截图: {actual_url}")
                                    else:
                                        round_success = False
                                        failed_tools.add(tool_name)
                                        logger.warning(f"截图失败: {actual_url}")
                                        # 尝试替代工具web_download
                                        if "web_download" not in failed_tools:
                                            download_tool = self.registry.get_tool("web_download")
                                            if download_tool:
                                                try:
                                                    download_out = download_tool.call(actual_input)
                                                    download_log = {"step": len(tool_logs) + 2, "tool": "web_download", "input": actual_input, "output": download_out}
                                                    current_tool_logs.append(download_log)
                                                    tools_executed.add("web_download")
                                                    
                                                    if self._is_tool_successful(self._parse_tool_result(download_out)):
                                                        round_success = True
                                                        failed_tools.discard(tool_name)
                                                        logger.info(f"使用替代工具web_download成功")
                                                except Exception as e:
                                                    logger.error(f"使用替代工具失败: {e}")
                                except Exception as e:
                                    logger.error(f"截图过程发生异常: {e}")
                                    log = {"step": len(tool_logs) + 1, "tool": tool_name, "input": actual_input, 
                                           "output": f"[Exception] 截图失败: {str(e)}"}
                                    current_tool_logs.append(log)
                                    round_success = False
                                    failed_tools.add(tool_name)
                            else:
                                log = {"step": len(tool_logs) + 1, "tool": tool_name, "input": tool_input,
                                       "output": "[Info] 没有找到可用的网页URL，请先执行web_search获取网页链接"}
                                current_tool_logs.append(log)
                                round_success = False
                                failed_tools.add(tool_name)
                                logger.warning("没有找到可用的网页URL进行截图")
                        
                        # 其他工具正常执行
                        else:
                            try:
                                out = tool.call(tool_input)
                                log = {"step": len(tool_logs) + 1, "tool": tool_name, "input": tool_input, "output": out}
                                current_tool_logs.append(log)
                                
                                if not self._is_tool_successful(self._parse_tool_result(out)):
                                    round_success = False
                                    failed_tools.add(tool_name)
                                    logger.warning(f"工具 {tool_name} 执行失败")
                                else:
                                    round_success = True
                                    logger.info(f"工具 {tool_name} 执行成功")
                            except Exception as e:
                                logger.error(f"执行工具 {tool_name} 时发生异常: {e}")
                                log = {"step": len(tool_logs) + 1, "tool": tool_name, "input": tool_input,
                                       "output": f"[Exception] {str(e)}"}
                                current_tool_logs.append(log)
                                round_success = False
                                failed_tools.add(tool_name)
                        
                        # LangSmith追踪：工具调用成功
                        if self.langsmith_tracer:
                            self.langsmith_tracer.on_tool_end({
                                "tool": tool_name,
                                "output": log["output"],
                                "success": self._is_tool_successful(self._parse_tool_result(log["output"]))
                            })
                        
                    except Exception as e:
                        error_msg = f"执行工具 {tool_name} 时发生未预期的异常: {str(e)}"
                        logger.exception(error_msg)
                        log = {"step": len(tool_logs) + 1, "tool": tool_name, "input": tool_input,
                               "output": f"[Exception] {str(e)}"}
                        current_tool_logs.append(log)
                        round_success = False
                        failed_tools.add(tool_name)
                        
                        # LangSmith追踪：工具调用异常
                        if self.langsmith_tracer:
                            self.langsmith_tracer.on_tool_end({
                                "tool": tool_name,
                                "output": log["output"],
                                "success": False,
                                "exception": str(e)
                            })

                tool_logs.extend(current_tool_logs)

                # 更新中间结果
                current_results = "\n\n".join(
                    [f"Step {l['step']} - {l['tool']}({l['input']}):\n{l['output']}" for l in current_tool_logs])
                intermediate_results += ("\n\n" if intermediate_results else "") + current_results

                # LangSmith追踪：结束思考轮次
                if self.langsmith_tracer:
                    self.langsmith_tracer.on_chain_end({
                        "tool_logs": current_tool_logs,
                        "round_success": round_success
                    })

                # 只有当本轮没有执行任何工具时才提前结束
                if not tools_executed:
                    break
                    
                # 如果当前轮执行成功，且任务已经完成，可以提前结束
                if round_success and self._is_task_completed(user_input, tool_logs):
                    logger.info(f"任务在第 {round_num} 轮成功完成，提前结束")
                    break
                    
            except Exception as e:
                logger.exception(f"第 {round_num} 轮执行过程中发生异常: {str(e)}")
                # 继续下一轮，尝试恢复执行
                continue

        # 生成最终答案
        if not final_answer:
            # 构建包含结构化结果分析的提示
            structured_results = "工具执行结果（结构化分析）：\n"
            for i, log in enumerate(tool_logs, 1):
                parsed_result = self._parse_tool_result(log["output"])
                status = parsed_result.get("status", "unknown")
                message = parsed_result.get("message", "")[:300]
                suggestions = self._get_tool_suggestions(parsed_result)
                
                structured_results += f"第{i}步 - {log['tool']}: 状态={status}, 结果={message}"
                if suggestions:
                    structured_results += f", 建议={suggestions}"
                structured_results += "\n"

            summary_prompt = f"""
    用户问题: {user_input}
    上下文记忆: {memory_context}

    {structured_results}

    请基于以上工具执行结果（包含成功/失败状态和建议）给出最终答案：
    1) 'final_answer'：面向用户的答案，基于实际获取到的信息，不要编造不存在的信息
    2) 'final_thoughts'：简短说明你的思路，包括工具执行情况和决策过程

    如果工具执行失败，请如实告知用户失败原因和可能的替代方案。

    请以 JSON 返回：{{"final_answer":"...","final_thoughts":"..."}}
    只返回 JSON。
    """
            resp2 = self.llm.invoke(summary_prompt).content
            try:
                js2 = self._extract_json(resp2)
                parsed2 = json.loads(js2)
                final_answer = parsed2.get("final_answer", "")
                final_thoughts = parsed2.get("final_thoughts", "")
            except Exception:
                final_answer = structured_results
                final_thoughts = "\n".join(llm_thoughts)

        logger.info(f"任务执行完成，共执行 {round_num} 轮，调用 {len(tool_logs)} 个工具")
        return {
            "final_answer": final_answer,
            "plan": plans,
            "tool_logs": tool_logs,
            "llm_thoughts": "\n".join(llm_thoughts),
            "final_thoughts": final_thoughts,
            "used_tools": len(tool_logs) > 0
        }

    def _is_task_completed(self, user_input: str, tool_logs: List[Dict]) -> bool:
        """判断任务是否已经完成"""
        # 简单的任务完成判断逻辑
        # 可以根据具体需求扩展这个逻辑
        user_input_lower = user_input.lower()
        
        # 如果是图片相关任务，检查是否有成功的下载或截图
        if any(keyword in user_input_lower for keyword in ['图片', 'image', '照片', 'picture']):
            for log in tool_logs:
                parsed_result = self._parse_tool_result(log["output"])
                if (log["tool"] in ["web_download", "web_screenshot"] and 
                    self._is_tool_successful(parsed_result)):
                    return True
        
        # 如果是搜索任务，检查是否有成功的搜索
        if any(keyword in user_input_lower for keyword in ['搜索', 'search', '查找', 'find']):
            for log in tool_logs:
                parsed_result = self._parse_tool_result(log["output"])
                if (log["tool"] == "web_search" and 
                    self._is_tool_successful(parsed_result)):
                    return True
        
        # 默认情况下，如果有成功的工具执行，认为任务可能完成
        for log in tool_logs:
            parsed_result = self._parse_tool_result(log["output"])
            if self._is_tool_successful(parsed_result):
                return True
                
        return False