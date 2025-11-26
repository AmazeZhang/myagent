# tools/web_browser_tool.py
# Synchronous, Playwright-based advanced WebBrowserTool (Mode C)
# Compatible with a BaseManusTool that expects .call(query: str) -> str

from core.tool_base import BaseManusTool
from typing import Optional, Dict, Any, List, ClassVar
import json
import os
import base64
from pathlib import Path
from datetime import datetime, timedelta
import threading
import traceback

# Playwright sync API
try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError, Error as PlaywrightError
except Exception:
    sync_playwright = None
    PlaywrightTimeoutError = Exception
    PlaywrightError = Exception

LOCK = threading.RLock()


class WebBrowserTool(BaseManusTool):
    name: str = "web_browser"
    description: str = (
        "增强版网页浏览器工具（同步，Playwright sync API）。"
        "用法示例: web_browser action=\"go_to_url\" url=\"https://example.com\" [session_id=\"sess1\"] "
        "支持actions: go_to_url, click_element, input_text, scroll_down, scroll_up, scroll_to_text, "
        "open_tab, switch_tab, close_tab, get_page_state, take_screenshot, extract_content, extract_images, download_image, wait"
    )

    # Class-level Playwright and browser handles (single browser process reused)
    _playwright = None
    _browser = None
    _browser_launched = False
    _headless = os.environ.get("WEBBROWSER_HEADLESS", "true").lower() not in ("0", "false", "no")

    # Sessions: session_id -> dict with context, pages (tabs), current_tab_index, created_at, last_activity
    _sessions: Dict[str, Dict[str, Any]] = {}
    _session_timeout_seconds: int = int(os.environ.get("WEBBROWSER_SESSION_TIMEOUT", "300"))

    SUPPORTED_ACTIONS: ClassVar[List[str]] = [
        "go_to_url", "click_element", "input_text", "scroll_down", "scroll_up",
        "scroll_to_text", "send_keys", "get_dropdown_options", "select_dropdown_option",
        "go_back", "refresh", "web_search", "wait", "extract_content", "switch_tab",
        "open_tab", "close_tab", "get_page_state", "take_screenshot", "download_image", "extract_images"
    ]

    def _format_result(self, status: str, message: str, details: Dict[str, Any] = None) -> str:
        result = {"status": status, "message": message, "details": details or {}}
        if status == "failed":
            error_type = result["details"].get("error_type", "unknown")
            suggestions = self._get_suggestions(error_type, result["details"])
            if suggestions:
                result["details"]["suggestions"] = suggestions
        return json.dumps(result, ensure_ascii=False, indent=2)

    def _get_suggestions(self, error_type: str, details: Dict[str, Any]) -> List[str]:
        s = []
        if error_type == "playwright_not_installed":
            s = ["请安装 playwright: pip install playwright", "然后运行 playwright install"]
        elif error_type in ("navigation_failed", "navigation_timeout"):
            s = ["检查 URL 是否正确、加上 http(s) 前缀", "检查网络连接或目标站点是否有反爬策略"]
        elif error_type == "element_not_found":
            s = ["检查 selector 是否正确", "尝试先用 get_page_state 查看可用元素"]
        elif "timeout" in error_type:
            s = ["增加等待时间（参数 wait_time）", "使用更可靠的 selector 或等待页面加载"]
        return s

    def _parse_query(self, query: str) -> Dict[str, Any]:
        # 支持 JSON 格式或 key=value 空格/逗号分割
        params = {
            "action": "",
            "url": "",
            "session_id": "",
            "selector": "",
            "text": "",
            "wait_time": 5,
            "params": {}
        }
        if not query:
            return params
        q = query.strip()
        try:
            if q.startswith("{") or q.startswith("["):
                parsed = json.loads(q)
                if isinstance(parsed, dict):
                    params.update(parsed)
            else:
                # split by spaces but keep quoted strings
                parts = []
                cur = ""
                in_q = False
                quote_char = None
                for ch in q:
                    if ch in ('"', "'"):
                        if not in_q:
                            in_q = True
                            quote_char = ch
                            cur += ch
                        elif in_q and ch == quote_char:
                            in_q = False
                            cur += ch
                        else:
                            cur += ch
                    elif ch == " " and not in_q:
                        if cur:
                            parts.append(cur)
                            cur = ""
                    else:
                        cur += ch
                if cur:
                    parts.append(cur)
                # parse key=value
                for p in parts:
                    if "=" in p:
                        k, v = p.split("=", 1)
                        v = v.strip()
                        if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
                            v = v[1:-1]
                        params[k.strip()] = v
                    else:
                        # first token without '=' is action
                        if not params["action"]:
                            params["action"] = p.strip().strip('"').strip("'")
        except Exception:
            # fallback: minimal
            arr = q.split()
            if arr:
                params["action"] = arr[0]
                if len(arr) > 1:
                    params["url"] = arr[1]
        return params

    # ---------------- Playwright lifecycle ----------------
    def _ensure_playwright_started(self) -> Optional[Dict[str, Any]]:
        with LOCK:
            if sync_playwright is None:
                return {"error": "未安装 playwright（或导入失败）", "error_type": "playwright_not_installed"}
            if not self._browser_launched:
                try:
                    self._playwright = sync_playwright().start()
                    # chromium by default
                    self._browser = self._playwright.chromium.launch(headless=self._headless,
                                                                     args=['--disable-dev-shm-usage'])
                    self._browser_launched = True
                except Exception as e:
                    return {"error": f"Playwright 启动失败: {str(e)}", "error_type": "playwright_start_failed",
                            "trace": traceback.format_exc()}
        return None

    def _ensure_session(self, session_id: Optional[str]) -> Dict[str, Any]:
        """确保会话存在并返回 session dict 或 error dict"""
        if not session_id:
            session_id = "default"
        # cleanup expired sessions
        self._cleanup_sessions()

        if session_id not in self._sessions:
            err = self._ensure_playwright_started()
            if err:
                return err
            try:
                context = self._browser.new_context(viewport={"width": 1280, "height": 720}, user_agent="Mozilla/5.0")
                page = context.new_page()
                self._sessions[session_id] = {
                    "context": context,
                    "pages": [page],
                    "current_tab_index": 0,
                    "created_at": datetime.now(),
                    "last_activity": datetime.now()
                }
            except Exception as e:
                return {"error": f"创建浏览会话失败: {str(e)}", "error_type": "session_create_failed",
                        "trace": traceback.format_exc()}

        self._sessions[session_id]["last_activity"] = datetime.now()
        return self._sessions[session_id]

    def _get_current_page(self, session_id: str):
        sess = self._sessions.get(session_id)
        if not sess:
            return {"error": "session_not_initialized", "error_type": "session_not_initialized"}
        idx = sess.get("current_tab_index", 0)
        pages = sess.get("pages", [])
        if idx < 0 or idx >= len(pages):
            return {"error": "invalid_tab_index", "error_type": "invalid_tab_index"}
        return pages[idx]

    def _cleanup_sessions(self):
        now = datetime.now()
        expired = []
        for sid, s in list(self._sessions.items()):
            last = s.get("last_activity", s.get("created_at", now))
            if (now - last).total_seconds() > self._session_timeout_seconds:
                expired.append(sid)
        for sid in expired:
            try:
                sess = self._sessions.pop(sid, None)
                if sess:
                    try:
                        for p in sess.get("pages", []):
                            try:
                                p.close()
                            except:
                                pass
                        try:
                            sess.get("context").close()
                        except:
                            pass
                    except:
                        pass
            except:
                pass

    # ---------------- Basic operations ----------------
    def _go_to_url(self, session_id: str, url: str, wait_until: str = "load", timeout: int = 30000):
        try:
            if not url.startswith(("http://", "https://")):
                url = "https://" + url
            sess_or_err = self._ensure_session(session_id)
            if "error" in sess_or_err:
                return sess_or_err
            page = self._get_current_page(session_id)
            if isinstance(page, dict) and "error" in page:
                return page
            page.goto(url, wait_until=wait_until, timeout=timeout)
            title = page.title()
            current = page.url
            return {"success": True, "message": f"已导航到: {current}", "title": title, "url": current}
        except PlaywrightTimeoutError as te:
            return {"error": f"导航超时: {str(te)}", "error_type": "navigation_timeout",
                    "trace": traceback.format_exc()}
        except PlaywrightError as pe:
            return {"error": f"导航失败: {str(pe)}", "error_type": "navigation_failed", "trace": traceback.format_exc()}
        except Exception as e:
            return {"error": f"导航异常: {str(e)}", "error_type": "navigation_failed", "trace": traceback.format_exc()}

    def _click_element(self, session_id: str, selector: str, timeout: int = 10000):
        try:
            sess_or_err = self._ensure_session(session_id)
            if "error" in sess_or_err:
                return sess_or_err
            page = self._get_current_page(session_id)
            if isinstance(page, dict) and "error" in page:
                return page
            page.wait_for_selector(selector, timeout=timeout)
            page.click(selector, timeout=timeout)
            return {"success": True, "message": f"已点击元素: {selector}"}
        except PlaywrightTimeoutError as te:
            return {"error": f"元素等待超时: {str(te)}", "error_type": "element_timeout",
                    "trace": traceback.format_exc()}
        except Exception as e:
            return {"error": f"点击元素失败: {str(e)}", "error_type": "element_not_found",
                    "trace": traceback.format_exc()}

    def _input_text(self, session_id: str, selector: str, text: str, timeout: int = 10000):
        try:
            sess_or_err = self._ensure_session(session_id)
            if "error" in sess_or_err:
                return sess_or_err
            page = self._get_current_page(session_id)
            page.wait_for_selector(selector, timeout=timeout)
            page.fill(selector, text, timeout=timeout)
            return {"success": True, "message": f"已向元素 {selector} 输入文本。"}
        except Exception as e:
            return {"error": f"输入文本失败: {str(e)}", "error_type": "element_not_found",
                    "trace": traceback.format_exc()}

    def _extract_content(self, session_id: str, target: str = "main"):
        try:
            sess_or_err = self._ensure_session(session_id)
            if "error" in sess_or_err:
                return sess_or_err
            page = self._get_current_page(session_id)
            if target == "main":
                content = page.evaluate(
                    "() => { const main = document.querySelector('main') || document.querySelector('article') || document.body; return main.innerText; }")
            elif target == "all_text":
                content = page.evaluate("() => document.body.innerText")
            elif target == "links":
                content = page.evaluate("""() => {
                    const links = Array.from(document.querySelectorAll('a'));
                    return links.map(link => ({text: link.innerText, href: link.href}));
                }""")
            else:
                # selector as target
                content = page.evaluate(f"""() => {{
                    const el = document.querySelector('{target}');
                    return el ? el.innerText : '';
                }}""")
            return {"success": True, "content": content, "target": target}
        except Exception as e:
            return {"error": f"内容提取失败: {str(e)}", "error_type": "content_extraction_failed",
                    "trace": traceback.format_exc()}

    def _get_page_state(self, session_id: str):
        try:
            sess_or_err = self._ensure_session(session_id)
            if "error" in sess_or_err:
                return sess_or_err
            page = self._get_current_page(session_id)
            title = page.title()
            url = page.url
            interactive_elements = page.evaluate("""() => {
                const els = Array.from(document.querySelectorAll('a, button, input, select, textarea'));
                return els.map((el, i) => ({index: i, tag: el.tagName.toLowerCase(), text: el.innerText||el.value||el.placeholder||'', id: el.id||'', class: el.className||''}));
            }""")
            scroll_info = page.evaluate("""() => ({
                scrollY: window.scrollY, scrollX: window.scrollX, innerHeight: window.innerHeight,
                innerWidth: window.innerWidth, documentHeight: document.documentElement.scrollHeight
            })""")
            # screenshot as base64 small size
            screenshot_bytes = page.screenshot(full_page=False, type="jpeg", quality=60)
            screenshot_b64 = base64.b64encode(screenshot_bytes).decode("utf-8") if screenshot_bytes else ""
            return {
                "success": True,
                "title": title, "url": url,
                "interactive_elements": interactive_elements,
                "scroll_info": scroll_info,
                "screenshot": screenshot_b64
            }
        except Exception as e:
            return {"error": f"获取页面状态失败: {str(e)}", "error_type": "page_state_failed",
                    "trace": traceback.format_exc()}

    def _extract_images(self, session_id: str):
        try:
            sess_or_err = self._ensure_session(session_id)
            if "error" in sess_or_err:
                return sess_or_err
            page = self._get_current_page(session_id)
            images = page.evaluate("""() => {
                const imgs = Array.from(document.querySelectorAll('img'));
                return imgs.map((img, idx) => ({index: idx, src: img.src, alt: img.alt||'', width: img.naturalWidth, height: img.naturalHeight, class: img.className||''})).filter(i=>i.src);
            }""")
            return {"success": True, "images": images, "count": len(images)}
        except Exception as e:
            return {"error": f"提取图片失败: {str(e)}", "error_type": "image_extraction_failed",
                    "trace": traceback.format_exc()}

    def _download_image(self, session_id: str, image_url: str = None, image_index: int = None, selector: str = None,
                        fallback_to_screenshot: bool = True):
        """下载图片。优先直接获取 URL 数据，如失败则尝试页面 fetch 或截图回退。"""
        try:
            sess_or_err = self._ensure_session(session_id)
            if "error" in sess_or_err:
                return sess_or_err
            page = self._get_current_page(session_id)
            img_src = image_url
            if not img_src and image_index is not None:
                res = self._extract_images(session_id)
                if "error" in res:
                    return res
                imgs = res.get("images", [])
                if image_index < 0 or image_index >= len(imgs):
                    return {"error": "图片索引越界", "error_type": "image_index_out_of_range"}
                img_src = imgs[image_index]["src"]
            if selector and not img_src:
                # try get src from selector
                try:
                    img_src = page.evaluate(f"() => document.querySelector('{selector}')?.src || ''")
                except:
                    img_src = None

            if not img_src:
                return {"error": "未找到图片 URL", "error_type": "missing_image_parameters"}

            # try fetch via page context to preserve cookies
            try:
                data_url = page.evaluate(f"""async () => {{
                    const resp = await fetch("{img_src}");
                    const blob = await resp.blob();
                    return await new Promise(resolve => {{
                        const reader = new FileReader();
                        reader.onloadend = () => resolve(reader.result);
                        reader.readAsDataURL(blob);
                    }});
                }}""")
                if data_url and data_url.startswith("data:"):
                    b64 = data_url.split(",", 1)[1]
                    image_bytes = base64.b64decode(b64)
                    download_dir = Path("assets/downloads")
                    download_dir.mkdir(parents=True, exist_ok=True)
                    fname = f"image_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                    path = download_dir / fname
                    with open(path, "wb") as f:
                        f.write(image_bytes)
                    return {"success": True, "message": "图片下载成功", "filename": fname, "filepath": str(path),
                            "size": len(image_bytes)}
            except Exception:
                # fallback to plain requests (may fail for sites requiring cookies)
                import requests
                try:
                    r = requests.get(img_src, timeout=15)
                    if r.status_code == 200:
                        download_dir = Path("assets/downloads")
                        download_dir.mkdir(parents=True, exist_ok=True)
                        fname = f"image_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                        path = download_dir / fname
                        with open(path, "wb") as f:
                            f.write(r.content)
                        return {"success": True, "message": "图片下载成功_via_requests", "filename": fname,
                                "filepath": str(path), "size": len(r.content)}
                except Exception:
                    pass

            # fallback to screenshot
            if fallback_to_screenshot:
                ss = self._take_screenshot(session_id, area="viewport")
                if "success" in ss:
                    return {"success": True, "message": "下载失败，已用截图替代", "screenshot": ss}
            return {"error": "图片下载失败", "error_type": "download_failed"}
        except Exception as e:
            return {"error": f"图片下载异常: {str(e)}", "error_type": "download_failed",
                    "trace": traceback.format_exc()}

    def _take_screenshot(self, session_id: str, area: str = "full_page", selector: str = None):
        try:
            sess_or_err = self._ensure_session(session_id)
            if "error" in sess_or_err:
                return sess_or_err
            page = self._get_current_page(session_id)
            screenshot_dir = Path("assets/screenshots")
            screenshot_dir.mkdir(parents=True, exist_ok=True)
            fname = f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            path = screenshot_dir / fname
            if area == "full_page":
                b = page.screenshot(path=str(path), full_page=True)
            elif area == "viewport":
                b = page.screenshot(path=str(path), full_page=False)
            elif area == "element" and selector:
                el = page.query_selector(selector)
                if not el:
                    return {"error": "未找到元素用于截图", "error_type": "element_not_found"}
                b = el.screenshot(path=str(path))
            else:
                return {"error": "不支持的截图 area", "error_type": "invalid_screenshot_area"}
            with open(path, "rb") as f:
                img_b = f.read()
            b64 = base64.b64encode(img_b).decode("utf-8")
            return {"success": True, "message": f"截图成功: {fname}", "filename": fname, "filepath": str(path),
                    "base64_image": b64, "size": len(img_b)}
        except Exception as e:
            return {"error": f"截图失败: {str(e)}", "error_type": "screenshot_failed", "trace": traceback.format_exc()}

    # ---------------- Tab management ----------------
    def _open_tab(self, session_id: str, url: Optional[str] = None):
        try:
            sess_or_err = self._ensure_session(session_id)
            if "error" in sess_or_err:
                return sess_or_err
            sess = self._sessions[session_id]
            ctx = sess["context"]
            p = ctx.new_page()
            sess["pages"].append(p)
            sess["current_tab_index"] = len(sess["pages"]) - 1
            if url:
                p.goto(url)
            return {"success": True, "message": f"已打开新标签: index {sess['current_tab_index']}",
                    "index": sess["current_tab_index"], "url": p.url}
        except Exception as e:
            return {"error": f"打开新标签失败: {str(e)}", "error_type": "open_tab_failed",
                    "trace": traceback.format_exc()}

    def _switch_tab(self, session_id: str, index: int):
        try:
            sess = self._sessions.get(session_id)
            if not sess:
                return {"error": "session_not_initialized", "error_type": "session_not_initialized"}
            if index < 0 or index >= len(sess["pages"]):
                return {"error": "tab_index_out_of_range", "error_type": "invalid_tab_index"}
            sess["current_tab_index"] = index
            return {"success": True, "message": f"已切换到 tab {index}"}
        except Exception as e:
            return {"error": f"切换 tab 失败: {str(e)}", "error_type": "switch_tab_failed",
                    "trace": traceback.format_exc()}

    def _close_tab(self, session_id: str, index: int):
        try:
            sess = self._sessions.get(session_id)
            if not sess:
                return {"error": "session_not_initialized", "error_type": "session_not_initialized"}
            if index < 0 or index >= len(sess["pages"]):
                return {"error": "tab_index_out_of_range", "error_type": "invalid_tab_index"}
            page = sess["pages"].pop(index)
            try:
                page.close()
            except:
                pass
            # adjust current index
            sess["current_tab_index"] = max(0, min(sess["current_tab_index"], len(sess["pages"]) - 1))
            return {"success": True, "message": f"已关闭 tab {index}"}
        except Exception as e:
            return {"error": f"关闭 tab 失败: {str(e)}", "error_type": "close_tab_failed",
                    "trace": traceback.format_exc()}

    # ---------------- Main runner ----------------
    def _run(self, query: str) -> Dict[str, Any]:
        params = self._parse_query(query)
        action = params.get("action", "")
        if action.startswith('"') and action.endswith('"'):
            action = action[1:-1]
        session_id = params.get("session_id") or "default"

        if not action:
            return {"error": "missing_action", "error_type": "missing_action"}

        if action not in self.SUPPORTED_ACTIONS:
            return {"error": f"unsupported_action: {action}", "error_type": "unsupported_action"}

        # dispatch
        try:
            if action == "go_to_url":
                url = params.get("url") or params.get("params", {}).get("url", "")
                if not url:
                    return {"error": "missing_url", "error_type": "missing_url"}
                return self._go_to_url(session_id, url)

            if action == "click_element":
                selector = params.get("selector") or params.get("params", {}).get("selector", "")
                if not selector:
                    return {"error": "missing_selector", "error_type": "missing_selector"}
                return self._click_element(session_id, selector)

            if action == "input_text":
                selector = params.get("selector") or params.get("params", {}).get("selector", "")
                text = params.get("text") or params.get("params", {}).get("text", "")
                if not selector or text is None:
                    return {"error": "missing_parameters", "error_type": "missing_parameters"}
                return self._input_text(session_id, selector, text)

            if action == "extract_content":
                targ = params.get("params", {}).get("target") or params.get("target") or "main"
                return self._extract_content(session_id, targ)

            if action == "get_page_state":
                return self._get_page_state(session_id)

            if action == "take_screenshot":
                area = params.get("params", {}).get("area") or params.get("area") or "full_page"
                selector = params.get("params", {}).get("selector") or params.get("selector")
                return self._take_screenshot(session_id, area, selector)

            if action == "download_image":
                p = params.get("params", {})
                image_index = p.get("image_index")
                image_url = p.get("image_url") or params.get("image_url")
                selector = p.get("selector") or params.get("selector")
                return self._download_image(session_id, image_url=image_url,
                                            image_index=int(image_index) if image_index is not None else None,
                                            selector=selector)

            if action == "extract_images":
                return self._extract_images(session_id)

            if action == "open_tab":
                url = params.get("url") or params.get("params", {}).get("url")
                return self._open_tab(session_id, url)

            if action == "switch_tab":
                idx = params.get("index") or params.get("params", {}).get("index")
                if idx is None:
                    return {"error": "missing_index", "error_type": "missing_parameters"}
                return self._switch_tab(session_id, int(idx))

            if action == "close_tab":
                idx = params.get("index") or params.get("params", {}).get("index")
                if idx is None:
                    return {"error": "missing_index", "error_type": "missing_parameters"}
                return self._close_tab(session_id, int(idx))

            if action == "scroll_down":
                sess = self._ensure_session(session_id)
                if "error" in sess: return sess
                page = self._get_current_page(session_id)
                page.evaluate("() => window.scrollBy(0, window.innerHeight)")
                return {"success": True, "message": "已向下滚动"}

            if action == "scroll_up":
                sess = self._ensure_session(session_id)
                if "error" in sess: return sess
                page = self._get_current_page(session_id)
                page.evaluate("() => window.scrollBy(0, -window.innerHeight)")
                return {"success": True, "message": "已向上滚动"}

            if action == "wait":
                wt = params.get("wait_time") or params.get("params", {}).get("wait_time", 1)
                try:
                    wt = float(wt)
                except:
                    wt = 1.0
                import time
                time.sleep(wt)
                return {"success": True, "message": f"已等待 {wt} 秒"}

            # default
            return {"error": f"not_implemented:{action}", "error_type": "not_implemented"}
        except Exception as e:
            return {"error": f"运行异常: {str(e)}", "error_type": "tool_execution_failed",
                    "trace": traceback.format_exc()}

    # ---------------- Base tool call ----------------
    def call(self, query: str) -> str:
        """同步的 call 接口，返回 JSON 字符串（status/message/details）"""
        try:
            res = self._run(query)
            if "success" in res and res["success"]:
                return self._format_result("success", res.get("message", ""), res)
            elif "error" in res:
                # include trace in details for easier debugging
                details = res.copy()
                return self._format_result("failed", details.get("error", "工具调用失败"), details)
            else:
                return self._format_result("unknown", "操作完成但状态未知", res)
        except Exception as e:
            return self._format_result("failed", f"工具调用失败: {str(e)}",
                                       {"error_type": "tool_execution_failed", "trace": traceback.format_exc()})

    # ---------------- Cleanup at module exit (optional) ----------------
    @classmethod
    def shutdown_browser(cls):
        with LOCK:
            try:
                for sid, sess in list(cls._sessions.items()):
                    try:
                        for p in sess.get("pages", []):
                            try:
                                p.close()
                            except:
                                pass
                        try:
                            sess.get("context").close()
                        except:
                            pass
                    except:
                        pass
                cls._sessions.clear()
            except:
                pass
            try:
                if cls._browser_launched and cls._browser:
                    try:
                        cls._browser.close()
                    except:
                        pass
                if cls._playwright:
                    try:
                        cls._playwright.stop()
                    except:
                        pass
            except:
                pass
            cls._browser_launched = False


# register shutdown on interpreter exit (best-effort)
import atexit

atexit.register(WebBrowserTool.shutdown_browser)
