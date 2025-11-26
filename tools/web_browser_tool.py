# tools/web_browser_tool.py
from core.tool_base import BaseManusTool
from typing import Optional, Dict, Any, List, ClassVar
import json
import time
from datetime import datetime
import uuid
import os
import base64
import sys
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager
# 首先修复导入部分
from selenium.webdriver.edge.service import Service as EdgeService
from webdriver_manager.microsoft import EdgeChromiumDriverManager
# 在文件开头添加logger导入
from utils.logger import setup_logger
# 移除错误的__init__方法，恢复原来的类定义
# 在文件顶部添加模块级别的logger
import logging

# 创建模块级别的logger
logger = setup_logger('WebBrowserTool')

class WebBrowserTool(BaseManusTool):
    """基于Selenium的网页浏览器工具，支持多种网页操作类型，返回结构化结果"""
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

    # 移除__init__方法，让基类处理初始化
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # 不要在这里初始化logger，使用模块级别的logger

    def _find_browser_binary(self) -> Optional[str]:
        """自动查找浏览器二进制文件路径（支持Chrome和Edge）"""
        # Windows常见浏览器安装路径
        if sys.platform == 'win32':
# Edge浏览器路径
            edge_paths = [
                os.path.join(os.environ.get('PROGRAMFILES', 'C:\\Program Files'), 'Microsoft', 'Edge', 'Application',
                             'msedge.exe'),
                os.path.join(os.environ.get('PROGRAMFILES(X86)', 'C:\\Program Files (x86)'), 'Microsoft', 'Edge',
                             'Application', 'msedge.exe'),
                os.path.join(os.environ.get('LOCALAPPDATA', 'C:\\Users\\%USERNAME%\\AppData\\Local'), 'Microsoft', 'Edge',
                             'Application', 'msedge.exe'),
            ]

            # Chrome浏览器路径
            chrome_paths = [
                os.path.join(os.environ.get('PROGRAMFILES', 'C:\\Program Files'), 'Google', 'Chrome', 'Application',
                             'chrome.exe'),
                os.path.join(os.environ.get('PROGRAMFILES(X86)', 'C:\\Program Files (x86)'), 'Google', 'Chrome',
                             'Application', 'chrome.exe'),
                os.path.join(os.environ.get('LOCALAPPDATA', 'C:\\Users\\%USERNAME%\\AppData\\Local'), 'Google', 'Chrome',
                             'Application', 'chrome.exe'),
            ]

            # 扩展用户特定路径
            if 'USERNAME' in os.environ:
                username = os.environ['USERNAME']
                edge_paths.append(f'C:\\Users\\{username}\\AppData\\Local\\Microsoft\\Edge\\Application\\msedge.exe')
                chrome_paths.append(f'C:\\Users\\{username}\\AppData\\Local\\Google\\Chrome\\Application\\chrome.exe')

            # 首先尝试Edge浏览器
            for path in edge_paths:
                if os.path.exists(path):
                    return path

            # 如果Edge不存在，尝试Chrome
            for path in chrome_paths:
                if os.path.exists(path):
                    return path

        # macOS常见浏览器安装路径
        elif sys.platform == 'darwin':
            edge_paths = [
                '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge',
                '~/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge'
            ]

            chrome_paths = [
                '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
                '~/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
            ]

            # 首先尝试Edge浏览器
            for path in edge_paths:
                expanded_path = os.path.expanduser(path)
                if os.path.exists(expanded_path):
                    return expanded_path

            # 如果Edge不存在，尝试Chrome
            for path in chrome_paths:
                expanded_path = os.path.expanduser(path)
                if os.path.exists(expanded_path):
                    return expanded_path

        # Linux常见浏览器安装路径
        elif sys.platform.startswith('linux'):
            edge_paths = [
                '/usr/bin/microsoft-edge',
                '/usr/bin/microsoft-edge-stable'
            ]

            chrome_paths = [
                '/usr/bin/google-chrome',
                '/usr/bin/google-chrome-stable'
            ]

            # 首先尝试Edge浏览器
            for path in edge_paths:
                if os.path.exists(path):
                    return path

            # 如果Edge不存在，尝试Chrome
            for path in chrome_paths:
                if os.path.exists(path):
                    return path

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

        if error_type == "selenium_not_installed":
            suggestions = [
                "请安装selenium库：pip install selenium webdriver-manager",
                "确保Chrome浏览器已安装",
                "或者尝试使用其他工具如web_download或web_screenshot"
            ]
        elif error_type == "chrome_not_found":
            suggestions = [
                "请确保Chrome浏览器已安装",
                "或者在环境变量中设置CHROME_BINARY_PATH指向Chrome可执行文件路径",
                "或者修改代码中的_ensure_browser_initialized方法，手动指定Chrome路径"
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
                # 修复：同时支持逗号分隔和空格分隔的参数格式
                # 首先尝试用空格分割
                parts = []
                if '=' in query:
                    # 处理带引号的值
                    in_quotes = False
                    current_part = ""
                    for char in query:
                        if char == '"':
                            in_quotes = not in_quotes
                            current_part += char
                        elif char == ' ' and not in_quotes:
                            if current_part.strip():
                                parts.append(current_part.strip())
                                current_part = ""
                        else:
                            current_part += char
                    if current_part.strip():
                        parts.append(current_part.strip())
                else:
                    parts = query.split()

                # 解析键值对
                for part in parts:
                    if '=' in part:
                        key, value = part.split('=', 1)
                        key = key.strip()
                        # 移除引号
                        if value.startswith('"') and value.endswith('"'):
                            value = value[1:-1]
                        elif value.startswith("'") and value.endswith("'"):
                            value = value[1:-1]

                        params[key] = value

        except Exception as e:
            # 如果解析失败，尝试简单解析
            parts = query.split()
            if parts:
                params["action"] = parts[0]
                if len(parts) > 1:
                    params["url"] = parts[1]

        return params

    def _ensure_browser_initialized(self, session_id: str = None) -> Dict[str, Any]:
        """确保浏览器和会话正确初始化"""
        if not session_id:
            session_id = str(uuid.uuid4())[:8]

        if session_id not in self._browser_sessions:
            # 创建新的浏览器会话
            try:
                # 配置Chrome选项
                chrome_options = Options()
                chrome_options.add_argument("--disable-web-security")
                chrome_options.add_argument("--disable-features=VizDisplayCompositor")
                chrome_options.add_argument("--window-size=1280,720")
                chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")

                # 尝试设置浏览器二进制文件路径
                # 1. 首先检查环境变量
                browser_binary_path = os.environ.get('BROWSER_BINARY_PATH') or os.environ.get('CHROME_BINARY_PATH')

                # 2. 如果环境变量没有设置，尝试自动查找（支持Edge和Chrome）
                if not browser_binary_path:
                    browser_binary_path = self._find_browser_binary()

                # 3. 如果找到浏览器路径，设置它
                if browser_binary_path:
                    chrome_options.binary_location = browser_binary_path
                    # 根据浏览器类型选择合适的驱动
                    if 'msedge.exe' in browser_binary_path.lower() or 'Microsoft Edge' in browser_binary_path:
                        # 使用Edge驱动
                        service = EdgeService(EdgeChromiumDriverManager().install())
                        browser = webdriver.Edge(service=service, options=chrome_options)
                    else:
                        # 使用Chrome驱动
                        service = Service(ChromeDriverManager().install())
                        browser = webdriver.Chrome(service=service, options=chrome_options)
                else:
                    # 如果找不到浏览器路径，提供更友好的错误信息
                    error_msg = "未找到Chrome或Edge浏览器。请确保已安装浏览器或在环境变量中设置BROWSER_BINARY_PATH。"
                    logger.error(error_msg)
                    return {
                        "error": error_msg,
                        "error_type": "browser_not_found"
                    }

                # 使用无头模式
                chrome_options.add_argument("--headless")
                chrome_options.add_argument("--disable-gpu")

                # 设置默认超时
                browser.set_page_load_timeout(30)
                browser.set_script_timeout(30)

                self._browser_sessions[session_id] = {
                    "browser": browser,
                    "tabs": [browser.current_window_handle],
                    "current_tab_index": 0,
                    "created_at": datetime.now(),
                    "last_activity": datetime.now()
                }

            except Exception as e:
                error_msg = f"浏览器初始化失败: {str(e)}"
                # 使用模块级别的logger
                logger.error(error_msg)
                return {"error": error_msg, "error_type": "browser_init_failed"}

        # 更新最后活动时间
        self._browser_sessions[session_id]["last_activity"] = datetime.now()
        return {"session_id": session_id}
    def _get_current_page(self, session_id: str) -> Any:
        """获取当前活动的页面"""
        session = self._ensure_browser_initialized(session_id)
        if "error" in session:
            return session

        return session["browser"]

    def _go_to_url(self, session_id: str, url: str) -> Dict[str, Any]:
        """导航到指定URL"""
        browser = self._get_current_page(session_id)
        if "error" in browser:
            return browser

        try:
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url

            browser.get(url)
            # 等待页面加载完成
            time.sleep(3)

            # 获取页面信息
            title = browser.title
            current_url = browser.current_url

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

    def _click_element(self, session_id: str, selector: str) -> Dict[str, Any]:
        """点击指定元素"""
        browser = self._get_current_page(session_id)
        if "error" in browser:
            return browser

        try:
            # 等待元素出现
            element = WebDriverWait(browser, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
            )
            element.click()
            # 等待页面加载
            time.sleep(2)

            return {"success": True, "message": f"已点击元素: {selector}"}
        except TimeoutException:
            return {"error": f"元素未找到或不可点击: {selector}", "error_type": "element_not_found"}
        except Exception as e:
            error_type = "element_not_found"
            if "timeout" in str(e).lower():
                error_type = "element_timeout"
            return {"error": f"点击元素失败: {str(e)}", "error_type": error_type}

    def _input_text(self, session_id: str, selector: str, text: str) -> Dict[str, Any]:
        """向指定元素输入文本"""
        browser = self._get_current_page(session_id)
        if "error" in browser:
            return browser

        try:
            # 等待元素出现
            element = WebDriverWait(browser, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, selector))
            )
            element.clear()
            element.send_keys(text)

            return {"success": True, "message": f"已向元素 {selector} 输入文本: {text}"}
        except TimeoutException:
            return {"error": f"元素未找到: {selector}", "error_type": "element_not_found"}
        except Exception as e:
            error_type = "element_not_found"
            if "timeout" in str(e).lower():
                error_type = "element_timeout"
            return {"error": f"输入文本失败: {str(e)}", "error_type": error_type}

    def _extract_content(self, session_id: str, target: str = "main") -> Dict[str, Any]:
        """提取页面内容"""
        browser = self._get_current_page(session_id)
        if "error" in browser:
            return browser

        try:
            # 根据目标类型提取内容
            if target == "main":
                # 尝试获取main或article或body元素的文本
                try:
                    main_element = browser.find_element(By.TAG_NAME, 'main')
                    content = main_element.text
                except NoSuchElementException:
                    try:
                        article_element = browser.find_element(By.TAG_NAME, 'article')
                        content = article_element.text
                    except NoSuchElementException:
                        content = browser.find_element(By.TAG_NAME, 'body').text
            elif target == "all_text":
                content = browser.find_element(By.TAG_NAME, 'body').text
            elif target == "links":
                links = browser.find_elements(By.TAG_NAME, 'a')
                content = [{
                    "text": link.text,
                    "href": link.get_attribute('href')
                } for link in links]
            else:
                content = browser.find_element(By.TAG_NAME, 'body').text

            return {
                "success": True,
                "message": f"已提取页面{target}内容",
                "content": content
            }
        except Exception as e:
            return {"error": f"提取内容失败: {str(e)}", "error_type": "content_extraction_failed"}

    def _get_page_state(self, session_id: str) -> Dict[str, Any]:
        """获取页面状态信息"""
        browser = self._get_current_page(session_id)
        if "error" in browser:
            return browser

        try:
            # 获取基本页面信息
            title = browser.title
            url = browser.current_url

            # 获取可见文本
            visible_text = browser.find_element(By.TAG_NAME, 'body').text[:500] + "..." if len(
                browser.find_element(By.TAG_NAME, 'body').text) > 500 else browser.find_element(By.TAG_NAME,
                                                                                                'body').text

            # 获取一些关键元素
            headings = browser.find_elements(By.XPATH, '//h1 | //h2 | //h3')
            heading_texts = [h.text for h in headings if h.text.strip()]

            # 获取链接数量
            links = browser.find_elements(By.TAG_NAME, 'a')
            link_count = len(links)

            # 获取图片数量
            images = browser.find_elements(By.TAG_NAME, 'img')
            image_count = len(images)

            return {
                "success": True,
                "message": "已获取页面状态信息",
                "title": title,
                "url": url,
                "visible_text_preview": visible_text,
                "heading_count": len(heading_texts),
                "headings": heading_texts,
                "link_count": link_count,
                "image_count": image_count
            }
        except Exception as e:
            return {"error": f"获取页面状态失败: {str(e)}", "error_type": "page_state_failed"}

    def _take_screenshot(self, session_id: str, area: str = "full_page", selector: str = None) -> Dict[str, Any]:
        """截取页面截图"""
        browser = self._get_current_page(session_id)
        if "error" in browser:
            return browser

        try:
            # 确保截图目录存在
            screenshots_dir = os.path.join(os.getcwd(), "screenshots")
            os.makedirs(screenshots_dir, exist_ok=True)

            # 生成唯一文件名
            filename = f"screenshot_{session_id}_{int(time.time())}.png"
            filepath = os.path.join(screenshots_dir, filename)

            if area == "full_page":
                # 截取全屏
                browser.save_screenshot(filepath)
            elif area == "viewport":
                # 截取可视区域
                browser.save_screenshot(filepath)
            elif selector:
                # 根据选择器截图
                try:
                    element = WebDriverWait(browser, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    element.screenshot(filepath)
                except Exception as e:
                    # 如果元素截图失败，回退到全屏截图
                    browser.save_screenshot(filepath)
                    return {
                        "success": True,
                        "message": f"元素截图失败，已截取全屏。错误: {str(e)}",
                        "fallback_to_full_page": True,
                        "filepath": filepath
                    }

            # 读取截图并转换为base64（如果需要）
            with open(filepath, "rb") as f:
                base64_data = base64.b64encode(f.read()).decode('utf-8')

            return {
                "success": True,
                "message": "已成功截取截图",
                "filepath": filepath,
                "base64": base64_data
            }
        except Exception as e:
            return {"error": f"截图失败: {str(e)}", "error_type": "screenshot_failed"}

    def _download_image_with_fallback(self, session_id: str, image_index: int = None,
                                      image_url: str = None, fallback_to_screenshot: bool = True) -> Dict[str, Any]:
        """下载图片，失败时自动回退到截图功能"""
        browser = self._get_current_page(session_id)
        if "error" in browser:
            return browser

        try:
            # 确保下载目录存在
            download_dir = os.path.join(os.getcwd(), "downloads")
            os.makedirs(download_dir, exist_ok=True)

            if image_url:
                # 通过URL下载图片
                import requests
                try:
                    response = requests.get(image_url)
                    response.raise_for_status()

                    # 生成文件名
                    filename = f"image_{session_id}_{int(time.time())}.png"
                    filepath = os.path.join(download_dir, filename)

                    with open(filepath, 'wb') as f:
                        f.write(response.content)

                    return {
                        "success": True,
                        "message": f"已成功下载图片: {filename}",
                        "filepath": filepath
                    }
                except Exception as e:
                    if fallback_to_screenshot:
                        # 回退到截图
                        screenshot_result = self._take_screenshot(session_id)
                        if "success" in screenshot_result:
                            return {
                                "success": True,
                                "message": f"图片下载失败，已自动使用截图替代。原始错误: {str(e)}",
                                "fallback_used": True,
                                "screenshot_result": screenshot_result
                            }
                    return {"error": f"图片下载失败: {str(e)}", "error_type": "download_failed"}

            elif image_index is not None:
                # 通过索引下载图片
                images = browser.find_elements(By.TAG_NAME, 'img')
                if 0 <= image_index < len(images):
                    image_url = images[image_index].get_attribute('src')
                    if image_url:
                        return self._download_image_with_fallback(session_id, image_url=image_url,
                                                                  fallback_to_screenshot=fallback_to_screenshot)
                return {"error": f"无效的图片索引: {image_index}", "error_type": "invalid_image_index"}

            return {"error": "请提供图片URL或索引", "error_type": "missing_parameters"}
        except Exception as e:
            return {"error": f"下载图片失败: {str(e)}", "error_type": "download_failed"}

    def _download_image_by_click_with_fallback(self, session_id: str, selector: str,
                                               fallback_to_screenshot: bool = True) -> Dict[str, Any]:
        """通过点击下载按钮下载图片，失败时自动回退到截图功能"""
        browser = self._get_current_page(session_id)
        if "error" in browser:
            return browser

        try:
            # 尝试点击下载按钮
            try:
                element = WebDriverWait(browser, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                )
                element.click()
                time.sleep(3)  # 等待下载完成

                # 注意：Selenium不直接支持监控下载完成，这里只是模拟
                return {"success": True, "message": f"已点击下载按钮: {selector}"}
            except Exception as e:
                if fallback_to_screenshot:
                    # 回退到截图
                    screenshot_result = self._take_screenshot(session_id)
                    if "success" in screenshot_result:
                        return {
                            "success": True,
                            "message": f"点击下载失败，已自动使用截图替代。原始错误: {str(e)}",
                            "fallback_used": True,
                            "screenshot_result": screenshot_result
                        }
                return {"error": f"点击下载失败: {str(e)}", "error_type": "click_download_failed"}
        except Exception as e:
            return {"error": f"下载图片失败: {str(e)}", "error_type": "download_failed"}

    def _run(self, query: str) -> str:
        """执行网页浏览器操作，返回结构化结果"""
        params = self._parse_query(query)
        action = params["action"]
        session_id = params.get("session_id") or "default"

        if not action:
            return self._format_result("failed", "请提供操作类型（action）", {"error_type": "missing_action"})
        # 修复：添加额外的参数解析逻辑，确保action被正确识别
        if action.startswith('"') and action.endswith('"'):
            action = action[1:-1]  # 移除可能的引号

        if action not in self.SUPPORTED_ACTIONS:
            return self._format_result("failed", f"不支持的操作类型: {action}", {"error_type": "unsupported_action"})

        # 执行相应的操作
        result = {}

        if action == "go_to_url":
            url = params["url"]
            # 修复：确保URL被正确解析，移除可能的引号
            if url.startswith('"') and url.endswith('"'):
                url = url[1:-1]
            if not url:
                return self._format_result("failed", "导航操作需要提供URL", {"error_type": "missing_url"})
            result = self._go_to_url(session_id, url)

        elif action == "click_element":
            # 修复：添加类似的参数清理
            selector = params["selector"]
            if selector.startswith('"') and selector.endswith('"'):
                selector = selector[1:-1]
            if not selector:
                return self._format_result("failed", "点击操作需要提供元素选择器", {"error_type": "missing_selector"})
            result = self._click_element(session_id, selector)

        elif action == "input_text":
            if not params["selector"] or not params["text"]:
                return self._format_result("failed", "输入文本操作需要提供选择器和文本",
                                           {"error_type": "missing_parameters"})
            result = self._input_text(session_id, params["selector"], params["text"])

        elif action == "extract_content":
            target = params.get("params", {}).get("target", "main")
            # 支持直接通过参数传递target
            if not target and "target" in params:
                target = params["target"]
            result = self._extract_content(session_id, target)

        elif action == "get_page_state":
            result = self._get_page_state(session_id)

        elif action == "take_screenshot":
            # 截图操作修复
            area = params.get("params", {}).get("area", "full_page")
            selector = params.get("params", {}).get("selector")
            # 支持直接通过参数传递area和selector
            if not area and "area" in params:
                area = params["area"]
            if not selector and "selector" in params:
                selector = params["selector"]
            result = self._take_screenshot(session_id, area, selector)

        elif action == "download_image":
            # 支持多种下载方式，默认启用回退机制
            image_index = params.get("params", {}).get("image_index")
            image_url = params.get("params", {}).get("image_url")
            selector = params.get("params", {}).get("selector")
            fallback = params.get("params", {}).get("fallback_to_screenshot", True)

            # 支持直接通过参数传递
            if not selector and "selector" in params:
                selector = params["selector"]
            if not image_url and "image_url" in params:
                image_url = params["image_url"]
            if image_index is None and "image_index" in params:
                try:
                    image_index = int(params["image_index"])
                except:
                    pass

            if selector:
                result = self._download_image_by_click_with_fallback(session_id, selector, fallback)
            elif image_url:
                result = self._download_image_with_fallback(session_id, image_url=image_url,
                                                            fallback_to_screenshot=fallback)
            elif image_index is not None:
                result = self._download_image_with_fallback(session_id, image_index=image_index,
                                                            fallback_to_screenshot=fallback)
            else:
                result = {"error": "请提供图片索引、URL或选择器", "error_type": "missing_image_parameters"}

        elif action == "scroll_down":
            browser = self._get_current_page(session_id)
            if "error" not in browser:
                browser.execute_script('window.scrollBy(0, window.innerHeight)')
                result = {"success": True, "message": "已向下滚动"}
            else:
                result = browser

        elif action == "scroll_up":
            browser = self._get_current_page(session_id)
            if "error" not in browser:
                browser.execute_script('window.scrollBy(0, -window.innerHeight)')
                result = {"success": True, "message": "已向上滚动"}
            else:
                result = browser

        elif action == "wait":
            wait_time = params.get("wait_time", 5)
            # 尝试转换为数字
            try:
                wait_time = float(wait_time)
            except:
                wait_time = 5
            time.sleep(wait_time)
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