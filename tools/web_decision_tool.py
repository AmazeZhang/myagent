# tools/web_decision_tool.py
from core.tool_base import BaseManusTool
from typing import Optional, Dict, Any, List, ClassVar
import json

class WebDecisionTool(BaseManusTool):
    """智能网页操作决策工具，帮助决定执行哪种网页操作。支持结构化返回格式，包含状态、消息和详细信息。"""
    
    name: str = "web_decision"
    description: str = '分析当前网页状态和任务需求，推荐最适合的网页操作。支持结构化返回格式，包含状态、消息和详细信息。使用方式: web_decision task="任务描述" [current_state="当前状态"]'
    memory: Optional[object] = None
    
    # 操作决策规则 - 使用ClassVar声明为类变量
    DECISION_RULES: ClassVar[Dict[str, Dict[str, Any]]] = {
        "navigation": {
            "patterns": ["访问", "打开", "导航", "转到", "go to", "visit", "navigate"],
            "actions": ["go_to_url", "web_search"]
        },
        "interaction": {
            "patterns": ["点击", "选择", "按钮", "链接", "click", "select", "button", "link"],
            "actions": ["click_element", "get_page_state"]
        },
        "input": {
            "patterns": ["输入", "填写", "搜索", "input", "fill", "search", "type"],
            "actions": ["input_text", "send_keys"]
        },
        "extraction": {
            "patterns": ["提取", "获取", "读取", "内容", "信息", "extract", "get", "read"],
            "actions": ["extract_content", "get_page_state"]
        },
        "scrolling": {
            "patterns": ["滚动", "翻页", "向下", "向上", "scroll", "page down", "page up"],
            "actions": ["scroll_down", "scroll_up", "scroll_to_text"]
        },
        "browser_control": {
            "patterns": ["返回", "刷新", "标签", "后退", "back", "refresh", "tab"],
            "actions": ["go_back", "refresh", "switch_tab", "open_tab"]
        }
    }

    def _format_result(self, status: str, message: str, details: dict = None) -> str:
        """格式化返回结果"""
        result = {
            "status": status,
            "message": message,
            "details": details or {}
        }
        return json.dumps(result, ensure_ascii=False)

    def _analyze_task(self, task: str) -> List[str]:
        """分析任务描述，识别操作需求"""
        task_lower = task.lower()
        recommended_actions = []
        
        for category, rule in self.DECISION_RULES.items():
            for pattern in rule["patterns"]:
                if pattern.lower() in task_lower:
                    recommended_actions.extend(rule["actions"])
                    break
        
        # 去重并排序
        return list(dict.fromkeys(recommended_actions))

    def _get_action_parameters(self, action: str, task: str, current_state: Dict[str, Any] = None) -> Dict[str, Any]:
        """为特定操作生成参数建议"""
        params_suggestions = {
            "go_to_url": {
                "description": "导航到指定URL",
                "required": ["url"],
                "suggestion": "请提供要访问的网页URL"
            },
            "click_element": {
                "description": "点击页面元素",
                "required": ["selector"],
                "suggestion": "使用元素索引或选择器，可从get_page_state获取元素列表"
            },
            "input_text": {
                "description": "输入文本",
                "required": ["selector", "text"],
                "suggestion": "指定输入框选择器和要输入的文本"
            },
            "extract_content": {
                "description": "提取页面内容",
                "optional": ["target"],
                "suggestion": "可指定目标区域（main, all_text, links或具体选择器）"
            },
            "get_page_state": {
                "description": "获取当前页面状态",
                "suggestion": "无需额外参数，返回页面信息和可交互元素列表"
            }
        }
        
        return params_suggestions.get(action, {
            "description": "未知操作",
            "suggestion": "请参考工具文档"
        })

    def _generate_decision_tree(self, task: str, current_state: Dict[str, Any] = None) -> Dict[str, Any]:
        """生成操作决策树"""
        recommended_actions = self._analyze_task(task)
        
        decision_tree = {
            "task_analysis": task,
            "recommended_actions": [],
            "decision_logic": [],
            "step_by_step_plan": []
        }
        
        # 为每个推荐操作生成详细信息
        for action in recommended_actions:
            action_info = self._get_action_parameters(action, task, current_state)
            decision_tree["recommended_actions"].append({
                "action": action,
                "description": action_info["description"],
                "suggestion": action_info["suggestion"]
            })
        
        # 生成决策逻辑
        if "go_to_url" in recommended_actions and "访问" in task:
            decision_tree["decision_logic"].append("检测到导航需求，建议先使用go_to_url访问目标网页")
        
        if "get_page_state" in recommended_actions:
            decision_tree["decision_logic"].append("建议先使用get_page_state了解页面当前状态")
            
        if "click_element" in recommended_actions and "输入" not in task:
            decision_tree["decision_logic"].append("检测到交互需求，建议在了解页面状态后使用click_element")
            
        if "input_text" in recommended_actions:
            decision_tree["decision_logic"].append("检测到输入需求，建议使用input_text填写表单")
        
        # 生成分步计划
        if recommended_actions:
            decision_tree["step_by_step_plan"].append("1. 使用get_page_state获取当前页面状态")
            
            if "go_to_url" in recommended_actions:
                decision_tree["step_by_step_plan"].append("2. 使用go_to_url导航到目标网页")
                decision_tree["step_by_step_plan"].append("3. 再次使用get_page_state获取新页面状态")
            
            if "input_text" in recommended_actions:
                decision_tree["step_by_step_plan"].append("4. 使用input_text填写必要信息")
                
            if "click_element" in recommended_actions:
                decision_tree["step_by_step_plan"].append("5. 使用click_element进行交互操作")
                
            if "extract_content" in recommended_actions:
                decision_tree["step_by_step_plan"].append("6. 使用extract_content获取所需信息")
        
        return decision_tree

    def _run(self, query: str) -> str:
        """执行智能决策分析"""
        try:
            # 解析查询参数
            params = {}
            if query.strip().startswith('{'):
                params = json.loads(query)
            else:
                # 简单解析
                parts = query.split('"')
                if len(parts) >= 3:
                    params["task"] = parts[1]
                if len(parts) >= 5:
                    try:
                        params["current_state"] = json.loads(parts[3])
                    except:
                        pass
            
            task = params.get("task", "")
            if not task:
                return self._format_result(
                    status="failed",
                    message="缺少任务描述",
                    details={
                        "error_type": "missing_task",
                        "suggestions": [
                            "请提供任务描述",
                            "检查参数格式是否正确"
                        ]
                    }
                )
            
            current_state = params.get("current_state", {})
            
            # 生成决策分析
            decision_tree = self._generate_decision_tree(task, current_state)
            
            return self._format_result(
                status="success",
                message="智能决策分析完成",
                details={
                    "decision_analysis": decision_tree,
                    "task_complexity": len(decision_tree["recommended_actions"]),
                    "recommended_action_count": len(decision_tree["recommended_actions"]),
                    "plan_steps": len(decision_tree["step_by_step_plan"])
                }
            )
            
        except json.JSONDecodeError as e:
            return self._format_result(
                status="failed",
                message="JSON解析错误",
                details={
                    "error_type": "json_parse_error",
                    "error_message": str(e),
                    "suggestions": [
                        "检查JSON格式是否正确",
                        "确认参数使用双引号",
                        "尝试简化参数格式"
                    ]
                }
            )
        except Exception as e:
            return self._format_result(
                status="failed",
                message="决策分析失败",
                details={
                    "error_type": "analysis_error",
                    "error_message": str(e),
                    "suggestions": [
                        "检查任务描述是否清晰",
                        "确认当前状态格式正确",
                        "尝试简化任务描述"
                    ]
                }
            )