# tools/web_browser_tool.py
from core.tool_base import BaseManusTool
from typing import Optional, Dict, Any, List, ClassVar
import json
import asyncio
from datetime import datetime
import uuid
import os
import base64
from pathlib import Path


class WebBrowserTool(BaseManusTool):
    """增强版网页浏览器工具，支持多种网页操作类型，返回结构化结果"""

    name: str = "web_browser"
    description: str = '执行网页浏览器操作，支持导航、交互、内容提取、图片下载等功能。返回结构化结果包含status、message和details字段。使用方式: web_browser action="action_name" [url="网页URL"] [其他参数]。图片下载示例: web_browser action="download_image" params={"image_index": 0} 或 web_browser action="download_image" params={"selector": "[data-testid=\'download-button\']"}'
    memory: Optional[object] = None

    # 浏览器会话管理
    _browser_sessions: Dict[str, Any] = {}
    _session_timeout: int = 300  # 会话超时时间（秒）

    # 支持的操作类型 - 使用ClassVar声明为类变量
    SUPPORTED_ACTIONS: ClassVar[List[str]] = [
        "go_to_url", "click_element", "input_text", "scroll_down", "scroll_up",
        "scroll_to_text", "send_keys", "get_dropdown_options", "select_dropdown_option",
        "go_back", "refresh", "web_search", "wait", "extract_content", "switch_tab",
        "open_tab", "close_tab", "get_page_state", "take_screenshot", "download_image"
    ]

    def _format_result(self, status: str, message: str, details: Dict[str, Any] = None) -> str:
        """格式化返回结果，包含状态、消息和详细信息"""
        result = {
            "status": status,
            "message": message,
            "details": details or {}
        }

        # 根据状态添加建议
        if status == "failed":
            error_type = details.get("error_type", "unknown")
            suggestions = self._get_suggestions(error_type, details)
            if suggestions:
                result["details"]["suggestions"] = suggestions

        return json.dumps(result, ensure_ascii=False, indent=2)

    def _get_suggestions(self, error_type: str, details: Dict[str, Any]) -> List[str]:
        """根据错误类型提供建议"""
        suggestions = []

        if error_type == "playwright_not_installed":
            suggestions = [
                "请安装playwright库：pip install playwright",
                "安装浏览器：playwright install",
                "或者尝试使用其他工具如web_download或web_screenshot"
            ]
        elif error_type == "navigation_failed":
            suggestions = [
                "检查URL是否正确",
                "尝试使用http://或https://前缀",
                "检查网络连接",
                "尝试使用web_search工具搜索相关内容"
            ]
        elif error_type == "element_not_found":
            suggestions = [
                "检查选择器是否正确",
                "等待页面完全加载后再操作",
                "尝试使用不同的选择器",
                "使用get_page_state操作查看可用元素"
            ]
        elif error_type == "download_failed":
            suggestions = [
                "尝试使用web_download工具直接下载",
                "使用web_screenshot工具截图替代",
                "检查网络连接和权限",
                "尝试不同的下载方法"
            ]
        elif error_type == "screenshot_failed":
            suggestions = [
                "尝试使用web_screenshot工具",
                "检查浏览器是否正常运行",
                "尝试不同的截图区域",
                "使用web_download工具下载图片"
            ]
        elif "timeout" in error_type.lower():
            suggestions = [
                "增加等待时间",
                "检查网络连接",
                "尝试重新操作",
                "使用更简单的操作"
            ]

        return suggestions

    def _parse_query(self, query: str) -> Dict[str, Any]:
        """解析查询参数，支持多种参数格式"""
        params = {
            "action": "",
            "url": "",
            "session_id": "",
            "selector": "",
            "text": "",
            "wait_time": 5,
            "params": {}
        }

        try:
            # 尝试解析JSON格式
            if query.strip().startswith('{'):
                json_params = json.loads(query)
                params.update(json_params)
            else:
                # 解析键值对格式
                parts = [p.strip() for p in query.split(",")]
                for part in parts:
                    if '=' in part:
                        key, value = part.split('=', 1)
                        key = key.strip()
                        value = value.strip().strip('"\'')

                        if key == "action":
                            params["action"] = value
                        elif key == "url":
                            params["url"] = value
                        elif key == "session_id":
                            params["session_id"] = value
                        elif key == "selector":
                            params["selector"] = value
                        elif key == "text":
                            params["text"] = value
                        elif key == "wait_time":
                            params["wait_time"] = int(value) if value.isdigit() else 5
                        elif key == "params":
                            try:
                                params["params"] = json.loads(value)
                            except:
                                params["params"] = {}

        except Exception as e:
            # 如果解析失败，尝试简单解析
            parts = query.split()
            if parts:
                params["action"] = parts[0]
                if len(parts) > 1:
                    params["url"] = parts[1]

        return params

    async def _ensure_browser_initialized(self, session_id: str = None) -> Dict[str, Any]:
        """确保浏览器和会话正确初始化"""
        if not session_id:
            session_id = str(uuid.uuid4())[:8]

        if session_id not in self._browser_sessions:
            # 创建新的浏览器会话
            try:
                from playwright.async_api import async_playwright

                playwright = await async_playwright().start()
                browser = await playwright.chromium.launch(
                    headless=True,
                    args=['--disable-web-security', '--disable-features=VizDisplayCompositor']
                )

                context = await browser.new_context(
                    viewport={'width': 1280, 'height': 720},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                )

                page = await context.new_page()

                self._browser_sessions[session_id] = {
                    "playwright": playwright,
                    "browser": browser,
                    "context": context,
                    "page": page,
                    "tabs": [page],
                    "current_tab_index": 0,
                    "created_at": datetime.now(),
                    "last_activity": datetime.now()
                }

            except ImportError:
                return {"error": "未安装playwright库。请运行 'pip install playwright && playwright install' 来安装。",
                        "error_type": "playwright_not_installed"}
            except Exception as e:
                return {"error": f"浏览器初始化失败: {str(e)}", "error_type": "browser_init_failed"}

        # 更新最后活动时间
        self._browser_sessions[session_id]["last_activity"] = datetime.now()
        return self._browser_sessions[session_id]

    async def _get_current_page(self, session_id: str) -> Any:
        """获取当前活动的页面"""
        session = await self._ensure_browser_initialized(session_id)
        if "error" in session:
            return session

        tabs = session["tabs"]
        current_index = session["current_tab_index"]
        return tabs[current_index] if current_index < len(tabs) else tabs[0]

    async def _go_to_url(self, session_id: str, url: str) -> Dict[str, Any]:
        """导航到指定URL"""
        page = await self._get_current_page(session_id)
        if "error" in page:
            return page

        try:
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url

            await page.goto(url, wait_until='networkidle', timeout=30000)

            # 获取页面信息
            title = await page.title()
            current_url = page.url

            return {
                "success": True,
                "message": f"已导航到: {current_url}",
                "title": title,
                "url": current_url
            }
        except Exception as e:
            error_type = "navigation_failed"
            if "timeout" in str(e).lower():
                error_type = "navigation_timeout"
            return {"error": f"导航失败: {str(e)}", "error_type": error_type}

    async def _click_element(self, session_id: str, selector: str) -> Dict[str, Any]:
        """点击指定元素"""
        page = await self._get_current_page(session_id)
        if "error" in page:
            return page

        try:
            await page.wait_for_selector(selector, timeout=10000)
            await page.click(selector)
            await page.wait_for_load_state('networkidle')

            return {"success": True, "message": f"已点击元素: {selector}"}
        except Exception as e:
            error_type = "element_not_found"
            if "timeout" in str(e).lower():
                error_type = "element_timeout"
            return {"error": f"点击元素失败: {str(e)}", "error_type": error_type}

    async def _input_text(self, session_id: str, selector: str, text: str) -> Dict[str, Any]:
        """向指定元素输入文本"""
        page = await self._get_current_page(session_id)
        if "error" in page:
            return page

        try:
            await page.wait_for_selector(selector, timeout=10000)
            await page.fill(selector, text)

            return {"success": True, "message": f"已向元素 {selector} 输入文本: {text}"}
        except Exception as e:
            error_type = "element_not_found"
            if "timeout" in str(e).lower():
                error_type = "element_timeout"
            return {"error": f"输入文本失败: {str(e)}", "error_type": error_type}

    async def _extract_content(self, session_id: str, target: str = "main") -> Dict[str, Any]:
        """提取页面内容"""
        page = await self._get_current_page(session_id)
        if "error" in page:
            return page

        try:
            # 根据目标类型提取内容
            if target == "main":
                content = await page.evaluate('''() => {
                    const main = document.querySelector('main') || document.querySelector('article') || document.body;
                    return main.innerText;
                }''')
            elif target == "all_text":
                content = await page.evaluate('() => document.body.innerText')
            elif target == "links":
                content = await page.evaluate('''() => {
                    const links = Array.from(document.querySelectorAll('a'));
                    return links.map(link => ({
                        text: link.innerText,
                        href: link.href
                    }));
                }''')
            else:
                # 使用选择器提取特定内容
                content = await page.evaluate(f'''() => {{
                    const element = document.querySelector('{target}');
                    return element ? element.innerText : '未找到指定元素';
                }}''')

            return {
                "success": True,
                "content": content,
                "target": target
            }
        except Exception as e:
            return {"error": f"内容提取失败: {str(e)}", "error_type": "content_extraction_failed"}

    async def _get_page_state(self, session_id: str) -> Dict[str, Any]:
        """获取当前页面状态信息"""
        page = await self._get_current_page(session_id)
        if "error" in page:
            return page

        try:
            # 获取页面基本信息
            title = await page.title()
            url = page.url

            # 获取可交互元素
            interactive_elements = await page.evaluate('''() => {
                const elements = Array.from(document.querySelectorAll('a, button, input, select, textarea'));
                return elements.map((el, index) => ({
                    index: index,
                    tag: el.tagName.toLowerCase(),
                    text: el.innerText || el.value || el.placeholder || '',
                    type: el.type || '',
                    id: el.id || '',
                    class: el.className || ''
                }));
            }''')

            # 获取滚动信息
            scroll_info = await page.evaluate('''() => {
                return {
                    scrollY: window.scrollY,
                    scrollX: window.scrollX,
                    innerHeight: window.innerHeight,
                    innerWidth: window.innerWidth,
                    documentHeight: document.documentElement.scrollHeight,
                    documentWidth: document.documentElement.scrollWidth
                };
            }''')

            # 生成截图
            screenshot = await page.screenshot(full_page=False, type='jpeg', quality=80)
            screenshot_b64 = screenshot.decode('base64') if hasattr(screenshot, 'decode') else screenshot

            return {
                "success": True,
                "url": url,
                "title": title,
                "interactive_elements": interactive_elements,
                "scroll_info": scroll_info,
                "screenshot": screenshot_b64,
                "help": "[0], [1], [2] 等代表可点击元素的索引，使用 click_element 操作时指定索引"
            }
        except Exception as e:
            return {"error": f"获取页面状态失败: {str(e)}", "error_type": "page_state_failed"}

    async def _extract_images(self, session_id: str) -> Dict[str, Any]:
        """提取页面中的所有图片信息"""
        page = await self._get_current_page(session_id)
        if "error" in page:
            return page

        try:
            images = await page.evaluate('''() => {
                const images = Array.from(document.querySelectorAll('img'));
                return images.map((img, index) => ({
                    index: index,
                    src: img.src,
                    alt: img.alt || '',
                    width: img.naturalWidth,
                    height: img.naturalHeight,
                    title: img.title || '',
                    className: img.className || ''
                })).filter(img => img.src && img.src.startsWith('http'));
            }''')

            return {
                "success": True,
                "images": images,
                "count": len(images)
            }
        except Exception as e:
            return {"error": f"提取图片信息失败: {str(e)}", "error_type": "image_extraction_failed"}

    async def _download_image(self, session_id: str, image_index: int = None, image_url: str = None) -> Dict[str, Any]:
        """下载指定图片"""
        page = await self._get_current_page(session_id)
        if "error" in page:
            return page

        try:
            # 确保下载目录存在
            download_dir = Path("assets/downloads")
            download_dir.mkdir(parents=True, exist_ok=True)

            if image_url:
                # 直接下载指定URL的图片
                image_src = image_url
            else:
                # 通过索引获取图片URL
                images_result = await self._extract_images(session_id)
                if "error" in images_result:
                    return images_result

                images = images_result["images"]
                if image_index >= len(images):
                    return {"error": f"图片索引 {image_index} 超出范围，共 {len(images)} 张图片",
                            "error_type": "image_index_out_of_range"}

                image_src = images[image_index]["src"]

            # 使用playwright下载图片
            async with page.expect_download() as download_info:
                # 模拟右键点击图片并选择"另存为"
                if image_url:
                    # 对于直接URL，导航到图片页面
                    await page.goto(image_src, wait_until='networkidle')
                else:
                    # 对于页面中的图片，点击触发下载
                    await page.click(f'img:nth-child({image_index + 1})', button='right')
                    # 这里需要模拟右键菜单操作，但playwright不支持直接模拟右键菜单
                    # 改为使用更简单的方法：直接获取图片数据

            # 更简单的方法：直接获取图片数据并保存
            try:
                # 获取图片数据
                image_data = await page.evaluate(f'''async () => {{
                    const response = await fetch('{image_src}');
                    const blob = await response.blob();
                    return await new Promise((resolve) => {{
                        const reader = new FileReader();
                        reader.onloadend = () => resolve(reader.result);
                        reader.readAsDataURL(blob);
                    }});
                }}''')

                # 解析base64数据
                if image_data.startswith('data:'):
                    image_data = image_data.split(',')[1]

                # 解码并保存
                image_bytes = base64.b64decode(image_data)

                # 生成文件名
                filename = f"cat_image_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                filepath = download_dir / filename

                # 保存文件
                with open(filepath, 'wb') as f:
                    f.write(image_bytes)

                return {
                    "success": True,
                    "message": f"图片下载成功",
                    "filename": filename,
                    "filepath": str(filepath),
                    "size": len(image_bytes)
                }

            except Exception as e:
                return {"error": f"图片下载失败: {str(e)}", "error_type": "download_failed"}

        except Exception as e:
            return {"error": f"下载图片失败: {str(e)}", "error_type": "download_failed"}

    async def _download_image_by_click(self, session_id: str, selector: str) -> Dict[str, Any]:
        """通过点击下载按钮下载图片（适用于Pexels等网站）"""
        page = await self._get_current_page(session_id)
        if "error" in page:
            return page

        try:
            # 确保下载目录存在
            download_dir = Path("assets/downloads")
            download_dir.mkdir(parents=True, exist_ok=True)

            # 等待下载按钮出现
            await page.wait_for_selector(selector, timeout=10000)

            # 监听下载事件
            async with page.expect_download() as download_info:
                await page.click(selector)

            download = await download_info.value
            filename = download.suggested_filename

            # 保存文件
            filepath = download_dir / filename
            await download.save_as(filepath)

            return {
                "success": True,
                "message": f"图片下载成功",
                "filename": filename,
                "filepath": str(filepath)
            }

        except Exception as e:
            return {"error": f"通过点击下载图片失败: {str(e)}", "error_type": "download_failed"}

    async def _take_screenshot(self, session_id: str, area: str = "full_page", selector: str = None) -> Dict[str, Any]:
        """截取网页截图，支持全屏截图和指定区域截图"""
        page = await self._get_current_page(session_id)
        if "error" in page:
            return page

        try:
            # 确保截图目录存在
            screenshot_dir = Path("assets/screenshots")
            screenshot_dir.mkdir(parents=True, exist_ok=True)

            # 生成文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"screenshot_{timestamp}.png"
            filepath = screenshot_dir / filename

            if area == "full_page":
                # 全屏截图
                screenshot_data = await page.screenshot(full_page=True, path=filepath)
            elif area == "viewport":
                # 可视区域截图
                screenshot_data = await page.screenshot(path=filepath)
            elif area == "element" and selector:
                # 指定元素截图
                await page.wait_for_selector(selector, timeout=10000)
                element = await page.query_selector(selector)
                if element:
                    screenshot_data = await element.screenshot(path=filepath)
                else:
                    return {"error": f"未找到选择器为 {selector} 的元素", "error_type": "element_not_found"}
            else:
                return {"error": "不支持的截图区域类型或缺少选择器", "error_type": "invalid_screenshot_area"}

            # 转换为base64编码
            with open(filepath, 'rb') as f:
                image_bytes = f.read()
            base64_image = base64.b64encode(image_bytes).decode('utf-8')

            return {
                "success": True,
                "message": f"截图成功: {filename}",
                "filename": filename,
                "filepath": str(filepath),
                "base64_image": base64_image,
                "size": len(image_bytes)
            }

        except Exception as e:
            return {"error": f"截图失败: {str(e)}", "error_type": "screenshot_failed"}

    async def _download_image_with_fallback(self, session_id: str, image_index: int = None, image_url: str = None,
                                            fallback_to_screenshot: bool = True) -> Dict[str, Any]:
        """下载图片，失败时自动回退到截图功能"""
        # 首先尝试正常下载
        download_result = await self._download_image(session_id, image_index, image_url)

        # 如果下载成功，直接返回结果
        if "success" in download_result and download_result["success"]:
            return download_result

        # 如果下载失败且启用了回退机制，尝试截图
        if fallback_to_screenshot and "error" in download_result:
            page = await self._get_current_page(session_id)
            if "error" in page:
                return download_result  # 返回原始错误

            try:
                # 获取当前页面信息用于截图
                current_url = page.url
                page_title = await page.title()

                # 尝试不同的截图策略
                screenshot_results = []

                # 策略1: 尝试截取全屏
                full_screenshot = await self._take_screenshot(session_id, "full_page")
                if "success" in full_screenshot:
                    screenshot_results.append({
                        "type": "full_page",
                        "result": full_screenshot
                    })

                # 策略2: 如果是指定图片，尝试截取图片元素
                if image_index is not None:
                    # 获取图片信息
                    images_result = await self._extract_images(session_id)
                    if "success" in images_result and image_index < len(images_result["images"]):
                        image_info = images_result["images"][image_index]
                        # 尝试点击图片放大后再截图
                        try:
                            await page.click(f'img:nth-child({image_index + 1})')
                            await asyncio.sleep(2)  # 等待图片加载/放大

                            # 截取可视区域
                            viewport_screenshot = await self._take_screenshot(session_id, "viewport")
                            if "success" in viewport_screenshot:
                                screenshot_results.append({
                                    "type": "viewport_after_click",
                                    "result": viewport_screenshot
                                })
                        except:
                            pass  # 点击失败不影响其他策略

                # 策略3: 截取可视区域
                viewport_screenshot = await self._take_screenshot(session_id, "viewport")
                if "success" in viewport_screenshot:
                    screenshot_results.append({
                        "type": "viewport",
                        "result": viewport_screenshot
                    })

                if screenshot_results:
                    # 选择最佳截图结果（优先全屏截图）
                    best_screenshot = None
                    for result in screenshot_results:
                        if result["type"] == "full_page":
                            best_screenshot = result["result"]
                            break
                    if not best_screenshot and screenshot_results:
                        best_screenshot = screenshot_results[0]["result"]

                    return {
                        "success": True,
                        "message": f"图片下载失败，已自动使用截图替代。原始错误: {download_result['error']}",
                        "fallback_used": True,
                        "original_error": download_result["error"],
                        "screenshot_result": best_screenshot,
                        "screenshot_strategies": [r["type"] for r in screenshot_results]
                    }
                else:
                    return download_result  # 所有截图策略都失败，返回原始错误

            except Exception as screenshot_error:
                # 截图也失败，返回组合错误信息
                return {
                    "error": f"图片下载失败且截图替代也失败。下载错误: {download_result['error']}, 截图错误: {str(screenshot_error)}",
                    "error_type": "download_and_screenshot_failed"
                }

        # 如果没有启用回退机制或不需要回退，返回原始错误
        return download_result

    async def _download_image_by_click_with_fallback(self, session_id: str, selector: str,
                                                     fallback_to_screenshot: bool = True) -> Dict[str, Any]:
        """通过点击下载按钮下载图片，失败时自动回退到截图功能"""
        # 首先尝试正常下载
        download_result = await self._download_image_by_click(session_id, selector)

        # 如果下载成功，直接返回结果
        if "success" in download_result and download_result["success"]:
            return download_result

        # 如果下载失败且启用了回退机制，尝试截图
        if fallback_to_screenshot and "error" in download_result:
            page = await self._get_current_page(session_id)
            if "error" in page:
                return download_result  # 返回原始错误

            try:
                # 尝试点击下载按钮后截图（可能按钮会打开图片预览）
                try:
                    await page.click(selector)
                    await asyncio.sleep(3)  # 等待可能的图片预览加载
                except:
                    pass  # 点击失败不影响截图

                # 截取全屏
                screenshot_result = await self._take_screenshot(session_id, "full_page")

                if "success" in screenshot_result:
                    return {
                        "success": True,
                        "message": f"通过点击下载失败，已自动使用截图替代。原始错误: {download_result['error']}",
                        "fallback_used": True,
                        "original_error": download_result["error"],
                        "screenshot_result": screenshot_result
                    }
                else:
                    return download_result  # 截图失败，返回原始错误

            except Exception as screenshot_error:
                return {
                    "error": f"点击下载失败且截图替代也失败。下载错误: {download_result['error']}, 截图错误: {str(screenshot_error)}",
                    "error_type": "click_download_and_screenshot_failed"
                }

        return download_result

    async def _run(self, query: str) -> str:
        """执行网页浏览器操作，返回结构化结果"""
        params = self._parse_query(query)
        action = params["action"]
        session_id = params.get("session_id") or "default"

        if not action:
            return self._format_result("failed", "请提供操作类型（action）", {"error_type": "missing_action"})

        if action not in self.SUPPORTED_ACTIONS:
            return self._format_result("failed", f"不支持的操作类型: {action}", {"error_type": "unsupported_action"})

        # 执行相应的操作
        result = {}

        if action == "go_to_url":
            if not params["url"]:
                return self._format_result("failed", "导航操作需要提供URL", {"error_type": "missing_url"})
            result = await self._go_to_url(session_id, params["url"])

        elif action == "click_element":
            if not params["selector"]:
                return self._format_result("failed", "点击操作需要提供元素选择器", {"error_type": "missing_selector"})
            result = await self._click_element(session_id, params["selector"])

        elif action == "input_text":
            if not params["selector"] or not params["text"]:
                return self._format_result("failed", "输入文本操作需要提供选择器和文本",
                                           {"error_type": "missing_parameters"})
            result = await self._input_text(session_id, params["selector"], params["text"])

        elif action == "extract_content":
            target = params.get("params", {}).get("target", "main")
            result = await self._extract_content(session_id, target)

        elif action == "get_page_state":
            result = await self._get_page_state(session_id)

        elif action == "take_screenshot":
            # 截图操作
            area = params.get("params", {}).get("area", "full_page")
            selector = params.get("params", {}).get("selector")
            result = await self._take_screenshot(session_id, area, selector)

        elif action == "download_image":
            # 支持多种下载方式，默认启用回退机制
            image_index = params.get("params", {}).get("image_index")
            image_url = params.get("params", {}).get("image_url")
            selector = params.get("params", {}).get("selector")
            fallback = params.get("params", {}).get("fallback_to_screenshot", True)

            if selector:
                result = await self._download_image_by_click_with_fallback(session_id, selector, fallback)
            elif image_url:
                result = await self._download_image_with_fallback(session_id, image_url=image_url,
                                                                  fallback_to_screenshot=fallback)
            elif image_index is not None:
                result = await self._download_image_with_fallback(session_id, image_index=image_index,
                                                                  fallback_to_screenshot=fallback)
            else:
                result = {"error": "请提供图片索引、URL或选择器", "error_type": "missing_image_parameters"}

        elif action == "scroll_down":
            page = await self._get_current_page(session_id)
            if "error" not in page:
                await page.evaluate('window.scrollBy(0, window.innerHeight)')
                result = {"success": True, "message": "已向下滚动"}
            else:
                result = page

        elif action == "scroll_up":
            page = await self._get_current_page(session_id)
            if "error" not in page:
                await page.evaluate('window.scrollBy(0, -window.innerHeight)')
                result = {"success": True, "message": "已向上滚动"}
            else:
                result = page

        elif action == "wait":
            wait_time = params.get("wait_time", 5)
            await asyncio.sleep(wait_time)
            result = {"success": True, "message": f"已等待 {wait_time} 秒"}

        else:
            result = {"error": f"操作 {action} 暂未实现", "error_type": "not_implemented"}

        # 格式化返回结果
        if "success" in result and result["success"]:
            return self._format_result("success", result["message"], result)
        elif "error" in result:
            error_type = result.get("error_type", "unknown")
            return self._format_result("failed", result["error"], {"error_type": error_type})
        else:
            return self._format_result("unknown", "操作执行完成，但结果状态未知", result)