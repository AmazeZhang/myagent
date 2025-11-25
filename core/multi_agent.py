# core/multi_agent.py
import json
from typing import Dict, List, Any
import asyncio
from core.expert_agent import ExpertAgentFactory, ExpertAgent
from core.registry import ToolRegistry
from core.tool_base import BaseManusTool
from langchain_ollama import ChatOllama


class MultiAgentOrchestrator:
    """多Agent协调器 - 改进版本，专注于专家选择"""

    def __init__(self, model_name: str = "llama3", model_type: str = "ollama"):
        self.model_name = model_name
        self.model_type = model_type  # 添加模型类型
        
        # 根据模型类型初始化LLM
        if model_type == "openrouter":
            from langchain_openai import ChatOpenAI
            from utils.config_manager import config_manager
            
            api_key = config_manager.openrouter_api_key
            if not api_key:
                raise Exception("OpenRouter API密钥未配置")
            
            # 清理模型名称
            clean_model_name = model_name
            if ":" in model_name:
                clean_model_name = model_name.split(":")[0]
            
            self.llm = ChatOpenAI(
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
            self.llm = ChatOllama(model=model_name, temperature=0.2)

        # 使用专家工厂创建专家
        self.expert_factory = ExpertAgentFactory(
            model_name=model_name, 
            model_type=model_type,
            registry=ToolRegistry()  # 添加registry参数
        )
        self.experts = self._initialize_experts()

        # 专家表现跟踪
        self.expert_performance = {name: {"success": 0, "total": 0} for name in self.experts}
        self.selection_history = []

    def _initialize_experts(self) -> Dict[str, ExpertAgent]:
        """初始化所有专家Agent"""
        return {
            "search_expert": self.expert_factory.create_search_expert(),
            "document_expert": self.expert_factory.create_document_expert(),
            "general_expert": self.expert_factory.create_general_expert()
        }

    def register_tool(self, tool: BaseManusTool):
        """注册工具到所有专家"""
        self.expert_factory.register_tool_to_all_experts(tool)

    def select_expert_llm(self, query: str) -> str:
        """使用LLM智能选择专家 - 针对日本行程规划优化"""
        available_experts = self.expert_factory.get_available_experts()
        experts_description = "\n".join([f"- {name}: {desc}" for name, desc in available_experts.items()])
    
        # 针对日本行程规划的特殊提示
        japan_travel_keywords = ["itinerary", "travel", "trip", "Japan", "Kyoto", "Tokyo", "Osaka", "Nara", "budget", "proposal", "itinerary", "行程", "旅游", "日本", "京都", "东京", "大阪", "奈良", "预算", "求婚"]
        
        if any(keyword.lower() in query.lower() for keyword in japan_travel_keywords):
            # 对于日本行程规划，优先选择搜索专家
            return "search_expert"
    
        prompt = f"""
        根据用户查询内容，智能选择最合适的专家Agent来处理。
    
        用户查询：{query}
    
        可用的专家Agent及其专长：
        {experts_description}
    
        请仔细分析查询的意图、领域和具体需求，选择最匹配的专家。
        考虑以下因素：
        1. 查询是否涉及实时信息、网络搜索、图片处理
        2. 查询是否涉及文档处理、文件操作
        3. 查询是否是一般性问题或需要综合处理
    
        特别说明：对于旅游行程规划、实时信息查询、网页搜索等任务，优先选择search_expert。
    
        只返回专家名称（search_expert/document_expert/general_expert），不要其他内容。
        """
    
        try:
            resp = self.llm.invoke(prompt).content.strip()
            # 验证返回的专家名称是否有效
            if resp in self.experts:
                return resp
            else:
                # 如果LLM返回了无效名称，使用回退策略
                return self._select_expert_fallback(query)
        except Exception as e:
            print(f"LLM专家选择失败: {e}")
            return self._select_expert_fallback(query)
    
    def _select_expert_fallback(self, query: str) -> str:
        """回退的专家选择策略 - 针对日本行程规划优化"""
        # 关键词匹配作为回退
        search_keywords = ['天气', '新闻', '搜索', '网页', '网络', '图片', '截图', '最新', '实时', 'itinerary', 'travel', 'trip', 'Japan', 'Kyoto', 'Tokyo', 'Osaka', 'Nara', 'budget', 'proposal', '行程', '旅游', '日本', '京都', '东京', '大阪', '奈良', '预算', '求婚']
        doc_keywords = ['文档', '文件', '阅读', '内容', '上传', '下载', '分析', '处理']
    
        if any(kw in query for kw in search_keywords):
            return "search_expert"
        elif any(kw in query for kw in doc_keywords):
            return "document_expert"
        else:
            return "general_expert"

    def select_expert_with_performance(self, query: str) -> str:
        """考虑历史表现的专家选择"""
        # 先用LLM选择候选专家
        llm_choice = self.select_expert_llm(query)

        # 如果该专家有足够的历史数据且表现不佳，考虑选择表现更好的专家
        if self.expert_performance[llm_choice]["total"] > 5:
            success_rate = self.expert_performance[llm_choice]["success"] / self.expert_performance[llm_choice]["total"]
            if success_rate < 0.3:
                # 选择表现最好的专家
                best_expert = self._get_best_performing_expert()
                if best_expert != llm_choice:
                    print(f"专家选择优化: {llm_choice}(成功率{success_rate:.2f}) -> {best_expert}")
                    return best_expert

        return llm_choice

    def _get_best_performing_expert(self) -> str:
        """获取表现最好的专家"""
        scores = []
        for expert, perf in self.expert_performance.items():
            if perf["total"] > 0:
                score = perf["success"] / perf["total"]
            else:
                score = 0.5  # 默认得分
            scores.append((expert, score))

        return max(scores, key=lambda x: x[1])[0]

    def update_expert_performance(self, expert_name: str, success: bool):
        """更新专家表现记录"""
        if expert_name in self.expert_performance:
            self.expert_performance[expert_name]["total"] += 1
            if success:
                self.expert_performance[expert_name]["success"] += 1

            # 记录选择历史
            self.selection_history.append({
                "expert": expert_name,
                "success": success,
                "timestamp": "当前时间"  # 可以添加实际时间戳
            })

    def _evaluate_result_quality(self, answer: str, query: str) -> bool:
        """评估回答质量"""
        if not answer or len(answer.strip()) < 10:
            return False

        negative_indicators = ["无法获取", "没有找到", "不知道", "不清楚", "抱歉", "错误"]
        if any(indicator in answer for indicator in negative_indicators):
            return False

        # 简单的质量检查：回答是否包含有用的信息
        useful_indicators = ["是", "可以", "建议", "方法", "步骤", "结果"]
        if any(indicator in answer for indicator in useful_indicators):
            return True

        return len(answer.strip()) > 30  # 如果回答较长，认为质量尚可

    def select_expert(self, query: str) -> str:
        """主专家选择方法（对外接口）"""
        return self.select_expert_with_performance(query)

    def run(self, query: str, memory_context: str = "") -> dict:
        """运行多Agent系统，包含性能跟踪和超时保护"""
        try:
            # 选择专家
            expert_name = self.select_expert(query)
            expert = self.experts[expert_name]

            print(f"选择专家: {expert_name} - {expert.description}")

            # 处理查询，设置超时保护
            try:
                # 使用异步执行，设置超时
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                result = loop.run_until_complete(
                    asyncio.wait_for(
                        self._run_expert_async(expert, query, memory_context),
                        timeout=300.0  # 5分钟超时
                    )
                )
                loop.close()
            except asyncio.TimeoutError:
                return {
                    "final_answer": "处理超时（5分钟），请简化问题或稍后重试",
                    "expert_name": expert_name,
                    "expert_description": expert.description,
                    "llm_thoughts": "处理超时",
                    "tool_logs": [],
                    "plan": [],
                    "success_evaluation": False,
                    "performance_stats": self.expert_performance[expert_name],
                    "timeout": True
                }

            final_answer = result.get("final_answer", "")

            # 评估结果质量
            success = self._evaluate_result_quality(final_answer, query)
            self.update_expert_performance(expert_name, success)

            # 返回完整结果
            full_result = {
                "final_answer": final_answer,
                "expert_name": expert_name,
                "expert_description": expert.description,
                "llm_thoughts": result.get("llm_thoughts", ""),
                "tool_logs": result.get("tool_logs", []),
                "plan": result.get("plan", []),
                "success_evaluation": success,
                "performance_stats": self.expert_performance[expert_name]
            }

            # 如果结果不理想且不是搜索专家，尝试搜索专家作为后备
            if not success and expert_name != "search_expert":
                print("尝试搜索专家作为后备...")
                try:
                    backup_result = self.experts["search_expert"].process(query, memory_context)
                    backup_answer = backup_result.get("final_answer", "")
                    backup_success = self._evaluate_result_quality(backup_answer, query)

                    if backup_success:
                        full_result = {
                            "final_answer": backup_answer,
                            "expert_name": "search_expert",
                            "expert_description": self.experts["search_expert"].description,
                            "llm_thoughts": backup_result.get("llm_thoughts", ""),
                            "tool_logs": backup_result.get("tool_logs", []),
                            "plan": backup_result.get("plan", []),
                            "success_evaluation": backup_success,
                            "performance_stats": self.expert_performance["search_expert"],
                            "backup_used": True
                        }
                except Exception as e:
                    print(f"后备专家执行失败: {e}")

            return full_result

        except Exception as e:
            print(f"多Agent系统执行异常: {e}")
            return {
                "final_answer": f"系统执行异常: {str(e)}",
                "expert_name": "unknown",
                "expert_description": "未知专家",
                "llm_thoughts": f"执行异常: {str(e)}",
                "tool_logs": [],
                "plan": [],
                "success_evaluation": False,
                "performance_stats": {"success": 0, "total": 0},
                "error": True
            }

    async def _run_expert_async(self, expert: ExpertAgent, query: str, memory_context: str) -> dict:
        """异步运行专家处理"""
        # 如果专家有异步执行方法，使用异步版本
        if hasattr(expert, 'execute_async'):
            return await expert.execute_async(query, memory_context)
        else:
            # 回退到同步执行
            return expert.process(query, memory_context)

    def get_expert_statistics(self) -> Dict[str, Any]:
        """获取专家统计信息"""
        return {
            "performance": self.expert_performance,
            "selection_history": self.selection_history[-10:],  # 最近10次选择
            "total_selections": len(self.selection_history)
        }