# tools/vlm_analysis.py
from core.tool_base import BaseManusTool
from typing import Optional
import base64
import requests
import json
from datetime import datetime

class VLMAnalysisTool(BaseManusTool):
    name: str = "vlm_analysis"
    description: str = '使用gemma3:12b VLM模型分析图像内容。支持结构化返回格式，包含状态、消息和详细信息。使用方式: vlm_analysis image_base64="base64编码的图像数据" [, prompt="分析提示"] [, model="gemma3:12b"]'
    memory: Optional[object] = None

    def _format_result(self, status: str, message: str, details: dict = None) -> str:
        """格式化返回结果"""
        result = {
            "status": status,
            "message": message,
            "details": details or {}
        }
        return json.dumps(result, ensure_ascii=False)

    def _parse_query(self, query: str) -> dict:
        """解析查询参数"""
        params = {
            "image_base64": "",
            "prompt": "请详细描述这张图片的内容",
            "model": "gemma3:12b"
        }

        # 解析格式：image_base64="base64数据", prompt="分析提示", model="gemma3:12b"
        parts = [p.strip() for p in query.split(",")]
        for part in parts:
            if part.startswith('image_base64='):
                # 提取引号内的base64数据
                if '"' in part:
                    params["image_base64"] = part.split('"')[1]
                else:
                    params["image_base64"] = part.split("=", 1)[1].strip()
            elif part.startswith('prompt='):
                if '"' in part:
                    params["prompt"] = part.split('"')[1]
                else:
                    params["prompt"] = part.split("=", 1)[1].strip()
            elif part.startswith('model='):
                if '"' in part:
                    params["model"] = part.split('"')[1]
                else:
                    params["model"] = part.split("=", 1)[1].strip()

        return params

    def _call_gemma_vlm(self, image_base64: str, prompt: str, model: str) -> str:
        """调用gemma3:12b VLM模型进行图像分析"""
        try:
            # 配置Ollama API端点
            ollama_url = "http://localhost:11434/api/generate"
            
            # 构建请求数据
            request_data = {
                "model": model,
                "prompt": prompt,
                "images": [image_base64],
                "stream": False
            }

            # 发送请求到Ollama
            response = requests.post(
                ollama_url,
                json=request_data,
                timeout=120  # 2分钟超时
            )

            if response.status_code == 200:
                result = response.json()
                return result.get("response", "VLM分析完成，但未返回有效结果")
            else:
                return f"[VLM Error] API调用失败，状态码: {response.status_code}, 错误: {response.text}"

        except requests.exceptions.ConnectionError:
            return "[VLM Error] 无法连接到Ollama服务。请确保Ollama正在运行且gemma3:12b模型已安装。"
        except requests.exceptions.Timeout:
            return "[VLM Error] VLM分析超时，请稍后重试。"
        except Exception as e:
            return f"[VLM Error] VLM分析失败: {str(e)}"

    def _run(self, query: str) -> str:
        """执行VLM图像分析"""
        params = self._parse_query(query)
        image_base64 = params["image_base64"]
        prompt = params["prompt"]
        model = params["model"]

        if not image_base64:
            return self._format_result(
                status="failed",
                message="缺少图像数据",
                details={
                    "error_type": "missing_image_data",
                    "suggestions": [
                        "请提供base64编码的图像数据",
                        "检查参数格式是否正确"
                    ]
                }
            )

        # 验证base64数据格式
        try:
            # 尝试解码base64数据以验证格式
            decoded_data = base64.b64decode(image_base64)
            image_size = len(decoded_data)
        except Exception:
            return self._format_result(
                status="failed",
                message="base64图像数据格式不正确",
                details={
                    "error_type": "invalid_base64",
                    "suggestions": [
                        "检查base64编码是否正确",
                        "确认图像数据没有损坏"
                    ]
                }
            )

        # 调用VLM模型进行分析
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        analysis_result = self._call_gemma_vlm(image_base64, prompt, model)

        # 检查分析结果是否包含错误信息
        if "[VLM Error]" in analysis_result:
            return self._format_result(
                status="failed",
                message="VLM分析失败",
                details={
                    "error_type": "vlm_analysis_error",
                    "error_message": analysis_result,
                    "suggestions": [
                        "检查Ollama服务是否运行",
                        "确认gemma3:12b模型已安装",
                        "尝试使用不同的模型",
                        "检查网络连接"
                    ]
                }
            )

        return self._format_result(
            status="success",
            message="VLM图像分析完成",
            details={
                "analysis_result": analysis_result,
                "analysis_info": {
                    "timestamp": timestamp,
                    "model_used": model,
                    "prompt_used": prompt,
                    "image_size_bytes": image_size
                },
                "formatted_output": f"""
[VLM Analysis] 图像分析完成 (使用模型: {model}):
- 分析时间: {timestamp}
- 分析提示: {prompt}
- 模型: {model}

分析结果:
{analysis_result}

此分析结果可用于理解图像内容、识别对象、描述场景等。
"""
            }
        )