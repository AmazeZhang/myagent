# tools/web_search.py
from core.tool_base import BaseManusTool
from typing import Optional, List, Dict, Any
import sys
import requests
from bs4 import BeautifulSoup
import time
import random
import json

class SearchResult:
    """搜索结果的数据类"""
    def __init__(self, title: str, url: str, snippet: str):
        self.title = title
        self.url = url
        self.snippet = snippet

    def __str__(self):
        return f"【{self.title}】\n{self.url}\n{self.snippet}"

class WebSearchTool(BaseManusTool):
    name: str = "web_search"
    description: str = '用于获取实时信息、最新数据或查找你不知道的内容。当用户询问天气、新闻、体育赛事、科技进展等需要实时更新的信息时必须使用此工具。使用方式: web_search query="搜索关键词" [, engine="baidu/google/bing"] [, num=5]。工具会返回结构化结果，包含执行状态和详细信息。'
    memory: Optional[object] = None

    def _parse_query(self, query: str) -> dict:
        """解析查询参数"""
        params = {
            "query": "",
            "engine": "baidu",
            "num": 5
        }
        
        # 解析格式：query="关键词", engine="baidu", num=5
        parts = [p.strip() for p in query.split(",")]
        for part in parts:
            if part.startswith('query='):
                # 提取引号内的查询内容
                if '"' in part:
                    params["query"] = part.split('"')[1]
                else:
                    params["query"] = part.split("=", 1)[1].strip()
            elif part.startswith('engine='):
                params["engine"] = part.split("=", 1)[1].strip().lower()
            elif part.startswith('num='):
                try:
                    params["num"] = int(part.split("=", 1)[1].strip())
                except ValueError:
                    pass
        
        # 如果没有使用query=格式，默认第一个参数为查询内容
        if not params["query"] and parts:
            if '"' in parts[0]:
                params["query"] = parts[0].split('"')[1]
            else:
                params["query"] = parts[0]
                
        return params

    def _format_result(self, success: bool, message: str, details: Dict[str, Any] = None) -> str:
        """格式化结构化返回结果"""
        result = {
            "status": "success" if success else "failed",
            "message": message,
            "details": details or {}
        }
        return json.dumps(result, ensure_ascii=False, indent=2)

    def _search_baidu(self, query: str, num_results: int) -> List[SearchResult]:
        """使用baidusearch库进行百度搜索"""
        search_results = []
        try:
            # 检查baidusearch库是否正确安装
            import baidusearch
            print(f"成功导入baidusearch库")
            
            from baidusearch.baidusearch import search
            print(f"正在使用baidusearch搜索: {query}")
            
            # 添加try-except捕获search方法可能抛出的异常
            try:
                results = search(query, num_results=num_results)
                # 调试代码 输出原始搜索结果
                #print(f"搜索结果原始数据: {results}")
            except Exception as inner_e:
                print(f"搜索执行失败: {str(inner_e)}")
                # 如果baidusearch库执行失败，尝试使用requests备选方案
                return self._search_baidu_with_requests(query, num_results)
            
            # 只有当获取到实际结果时才处理
            if results:
                print(f"获取到{len(results)}条结果")
                for r in results:
                    print(f"单条结果: {r}")
                    # 添加字段验证，确保字段存在
                    # 注意：根据日志，返回的结果字段可能是'title', 'abstract', 'url'
                    title = r.get('title', '')
                    # 尝试从'link'或'url'字段获取链接
                    link = r.get('link', r.get('url', ''))
                    # 尝试从'snippet'或'abstract'字段获取摘要
                    snippet = r.get('snippet', r.get('abstract', ''))
                    
                    # 只添加有效的结果（标题和链接都存在）
                    if title and link:
                        search_results.append(SearchResult(title, link, snippet))
                        if len(search_results) >= num_results:
                            break
            else:
                print("搜索结果为空，尝试使用requests备选方案")
                # 如果搜索结果为空，尝试使用requests备选方案
                return self._search_baidu_with_requests(query, num_results)
            
            return search_results
        except ImportError as e:
            # 如果没有安装baidusearch库
            print(f"未安装baidusearch库或导入错误: {str(e)}")
            print(f"Python路径: {sys.path}")
            # 使用requests备选方案
            return self._search_baidu_with_requests(query, num_results)
        except KeyError as e:
            # 捕获KeyError
            print(f"百度搜索出错: {str(e)}")
            # 使用requests备选方案
            return self._search_baidu_with_requests(query, num_results)
        except Exception as e:
            # 捕获其他异常
            print(f"百度搜索出错: {str(e)}")
            import traceback
            traceback.print_exc()
            # 使用requests备选方案
            return self._search_baidu_with_requests(query, num_results)

    def _search_baidu_with_requests(self, query: str, num_results: int) -> List[SearchResult]:
        """使用requests和BeautifulSoup进行百度搜索（备选方案）"""
        search_results = []
        try:
            print(f"使用requests备选方案搜索: {query}")
            
            # 如果是图片搜索，使用百度图片搜索
            if "图片" in query or "image" in query.lower():
                return self._search_baidu_images(query, num_results)
            
            # 设置请求头，模拟浏览器
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Referer': 'https://www.baidu.com/',
                'Connection': 'keep-alive'
            }
            
            # 构建搜索URL
            url = f"https://www.baidu.com/s?wd={requests.utils.quote(query)}"
            
            # 添加随机延迟，避免被识别为爬虫
            time.sleep(random.uniform(1, 2))
            
            # 发送请求
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()  # 检查请求是否成功
            
            print(f"请求状态码: {response.status_code}")
            print(f"响应内容长度: {len(response.text)} 字符")
            
            # 保存响应内容以便调试（可选）
            with open('baidu_response_debug.html', 'w', encoding='utf-8') as f:
                f.write(response.text)
            print("响应内容已保存到baidu_response_debug.html")
            
            # 解析HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 尝试多种可能的结果选择器，适应百度页面变化
            # 1. 尝试传统的结果选择器
            result_divs = soup.find_all('div', class_='result', limit=num_results)
            
            # 2. 如果没有找到结果，尝试新的选择器
            if not result_divs:
                result_divs = soup.select('div[class*="result-"]', limit=num_results)
            
            # 3. 如果仍然没有找到结果，尝试通用的链接选择器
            if not result_divs:
                result_divs = soup.find_all('h3', class_='t', limit=num_results)
                result_divs = [h3.parent for h3 in result_divs if h3.parent]
            
            # 4. 最后尝试直接查找所有链接
            if not result_divs:
                links = soup.find_all('a', href=True, limit=num_results*2)  # 获取更多链接以筛选
                # 筛选百度搜索结果链接
                result_divs = []
                seen_links = set()
                for link in links:
                    href = link.get('href')
                    # 排除百度内部链接，只保留搜索结果链接
                    if href and 'baidu.com' not in href and href not in seen_links:
                        result_divs.append(link.parent)
                        seen_links.add(href)
                        if len(result_divs) >= num_results:
                            break
            
            print(f"找到{len(result_divs)}个结果元素")
            
            for div in result_divs:
                try:
                    # 尝试多种方式提取标题
                    title = ""
                    # 方式1: 查找h3标签
                    h3_tag = div.find('h3')
                    if h3_tag:
                        title = h3_tag.get_text(strip=True)
                    
                    # 方式2: 如果h3标签不存在，尝试获取div的文本
                    if not title:
                        title = div.get_text(strip=True)[:100]  # 限制长度
                    
                    # 尝试多种方式提取链接
                    link = ""
                    # 方式1: 查找a标签
                    a_tag = div.find('a', href=True)
                    if a_tag and a_tag.get('href'):
                        link = a_tag.get('href')
                    
                    # 方式2: 查找data-href属性
                    if not link:
                        link = div.get('data-href', '')
                    
                    # 方式3: 查找href属性
                    if not link:
                        link = div.get('href', '')
                    
                    # 提取摘要
                    snippet = ""
                    # 尝试多种可能的摘要选择器
                    snippet_tags = div.find_all(['div', 'p'], class_=['c-abstract', 'content', 'summary'])
                    if snippet_tags:
                        snippet = snippet_tags[0].get_text(strip=True)
                    
                    # 如果没有找到摘要，使用div的部分文本
                    if not snippet:
                        snippet = div.get_text(strip=True)[:200]  # 限制长度
                    
                    # 添加到结果列表（至少需要标题或链接）
                    if title or link:
                        # 清理标题和链接
                        title = title.replace('\n', '').strip()[:100]  # 限制长度并清理换行
                        link = link.strip()
                        snippet = snippet.replace('\n', '').strip()[:300]  # 限制长度并清理换行
                        
                        # 如果链接是相对链接，转换为绝对链接
                        if link and not link.startswith(('http://', 'https://')):
                            link = f"https://www.baidu.com{link}" if link.startswith('/') else f"https://www.baidu.com/{link}"
                        
                        search_results.append(SearchResult(title, link, snippet))
                        print(f"添加结果: 标题='{title[:30]}...', 链接='{link[:50]}...'")
                except Exception as inner_e:
                    print(f"处理单个结果时出错: {str(inner_e)}")
                    continue
            
            print(f"requests备选方案获取到{len(search_results)}条结果")
            
            # 如果仍然没有结果，添加一个默认提示结果
            if not search_results:
                default_title = f"{query} - 搜索结果"
                default_link = f"https://www.baidu.com/s?wd={requests.utils.quote(query)}"
                default_snippet = f"无法直接提取搜索结果，请访问百度搜索查看关于'{query}'的详细信息。"
                search_results.append(SearchResult(default_title, default_link, default_snippet))
                print("添加默认搜索结果链接")
            
            return search_results
        except Exception as e:
            print(f"requests备选方案搜索出错: {str(e)}")
            import traceback
            traceback.print_exc()
            
            # 发生异常时，至少返回一个包含搜索链接的结果
            default_title = f"{query} - 搜索结果"
            default_link = f"https://www.baidu.com/s?wd={requests.utils.quote(query)}"
            default_snippet = f"搜索过程中发生错误，请访问百度搜索查看关于'{query}'的详细信息。"
            return [SearchResult(default_title, default_link, default_snippet)]

    def _search_generic(self, query: str, num_results: int) -> List[SearchResult]:
        """通用搜索实现"""
        # 对于其他搜索引擎，也使用百度搜索的备选方案
        return self._search_baidu_with_requests(query, num_results)

    def _run(self, query: str) -> str:
        """执行网页搜索，返回结构化结果"""
        params = self._parse_query(query)
        search_query = params["query"]
        engine = params["engine"]
        num_results = params["num"]
        
        if not search_query:
            return self._format_result(False, "请提供搜索关键词", {
                "suggestions": "请提供有效的搜索关键词"
            })
            
        try:
            # 根据指定的搜索引擎执行搜索
            if engine == "baidu":
                results = self._search_baidu(search_query, num_results)
            else:
                # 其他搜索引擎也使用百度搜索的备选方案
                results = self._search_generic(search_query, num_results)
            
            # 格式化搜索结果
            if not results:
                details = {
                    "query": search_query,
                    "engine": engine,
                    "num_results": 0,
                    "suggestions": "搜索无结果，请尝试使用不同的关键词或搜索引擎"
                }
                return self._format_result(False, f"无法获取关于'{search_query}'的搜索结果", details)
                
            # 确保我们正确处理结果
            print(f"_run方法收到{len(results)}条结果")
            
            # 构建结果详情
            result_details = []
            for i, result in enumerate(results, 1):
                result_details.append({
                    "index": i,
                    "title": result.title,
                    "url": result.url,
                    "snippet": result.snippet
                })
            
            details = {
                "query": search_query,
                "engine": engine,
                "num_results": len(results),
                "results": result_details,
                "suggestions": "搜索成功，可以使用web_download下载图片或web_screenshot进行截图"
            }
            
            return self._format_result(True, f"成功获取{len(results)}条关于'{search_query}'的搜索结果", details)
            
        except Exception as e:
            error_msg = f"无法获取搜索结果: {str(e)}"
            print(error_msg)
            details = {
                "error_type": "search_error",
                "query": search_query,
                "engine": engine,
                "suggestions": "搜索失败，请检查网络连接或尝试使用其他工具"
            }
            return self._format_result(False, error_msg, details)