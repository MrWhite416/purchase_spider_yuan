# development time: 2025-08-26  8:44
# developer: 元英


# import requests
from curl_cffi import Session
from curl_cffi.requests.exceptions import HTTPError, ConnectionError, Timeout  # 导入curl_cffi的异常类

from abc import ABC, abstractmethod
from typing import Callable
import pandas
from urllib3.util.retry import Retry
# from Purchase.util.log import logger
from loguru import logger
from Purchase.setting import *



class BaseSpider(ABC):
    # 子类必须定义的“网站元信息”（类属性，固定格式）
    website: str = ""  # 网站域名
    name: str = ""  # 网站名称（用于存储和日志）
    base_url: str = ""  # 网站基础URL（用于拼接详情页链接）
    search_api: str = ""  # 搜索接口URL

    def __init__(self, start_time: str, end_time: str, keys: list, filter_title: list, filter_content: list):
        # 初始化通用参数（所有爬虫共用）
        self.start_time = start_time
        self.end_time = end_time
        self.keys = keys  # 关键词列表
        self.filter_title = filter_title  # 标题过滤词
        self.filter_content = filter_content  # 内容过滤词
        self.logger = logger

        # 通用请求配置
        self.session = Session()
        self.headers = self._get_default_headers()  # 默认请求头（钩子方法）

        # 数据存储容器（统一格式）
        self.df = self._init_dataframe()

        # 搜索参数（由子类实现，初始化时自动加载）
        self.search_data = self._prepare_search_data()  # 抽象方法：子类实现参数结构

    def _get_default_headers(self) -> dict:
        """钩子方法：默认请求头，子类可覆盖（如添加特殊Header）"""
        return {
            "Accept": "*/*",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36 Edg/139.0.0.0",
        }

    def _init_dataframe(self) -> dict:
        """初始化数据存储结构（通用，子类无需修改）"""
        return {
            "标题": [], "时间": [], "来源": [], "正文": [], "链接": [], "所在网站": []
        }

    # ------------------------------ 抽象方法：子类必须实现（差异点） ------------------------------
    @abstractmethod
    def _prepare_search_data(self) -> dict:
        """抽象方法1：准备搜索参数（每个网站的data结构不同）"""
        pass

    @abstractmethod
    def _extract_total_page(self, resp: dict) -> int:
        """抽象方法2：提取总页数（分页规则不同，如ttlpage / total/size）"""
        pass

    @abstractmethod
    def _parse_list_page(self, resp: dict) -> list[dict]:
        """抽象方法3：解析列表页响应（resp结构不同，返回统一格式的列表数据）
        返回格式：[{"title": "xxx", "release_time": "xxx", "detail_url": "xxx", "origin": "xxx"}, ...]
        """
        pass

    @abstractmethod
    def _parse_detail_page(self, detail_html: str, title: str) -> str:
        """抽象方法4：解析详情页正文（XPath/正则不同，返回清洗后的正文）"""
        pass

    # ------------------------------ 钩子方法：子类按需覆盖（特殊逻辑） ------------------------------
    def _get_source_types(self) -> list:
        """钩子方法1：数据源类型列表（如Spider3的[1,2]，默认无）"""
        return []

    def _process_detail_url(self, raw_url: str) -> str:
        """钩子方法2：处理详情页URL（如替换协议/路径、拼接base_url，默认返回原URL）"""
        return raw_url

    def _update_search_data(self, keyword: str, source_type: int = None) -> None:
        """钩子方法3：更新搜索参数（关键词/数据源，通用逻辑可覆盖）"""
        # 通用：更新关键词
        if "FINDTXT" in self.search_data:
            self.search_data["FINDTXT"] = keyword
        elif "searchword" in self.search_data:
            self.search_data["searchword"] = keyword

        # 通用：更新数据源（如有）
        if source_type is not None and "SOURCE_TYPE" in self.search_data:
            self.search_data["SOURCE_TYPE"] = str(source_type)

    # ------------------------------ 通用核心流程（子类无需修改） ------------------------------
    def req(self, method: str, url: str, **kwargs) -> dict | str | bytes:
        """通用请求方法：含重试、JSON/文本自动解析，子类直接调用"""
        method = method.lower()
        if method not in ["get", "post"]:
            self.logger.error(f"不支持的请求方法：{method}")
            raise ValueError(f"不支持的请求方法：{method}")

        fetch_func = getattr(self.session, method)
        resp = None
        for retry in range(3):
            try:
                resp = fetch_func(
                    url, headers=self.headers, verify=False, **kwargs
                )
                resp.raise_for_status()
                break
            except HTTPError as e:
                self.logger.error(f"请求失败（状态码异常）：{e} | URL：{url} | 重试次数：{retry + 1}")
            except Exception as e:
                self.logger.error(f"请求异常：{e} | URL：{url} | 重试次数：{retry + 1}")
                if retry == 2:
                    raise  # 重试3次失败则抛出异常

        # 自动解析响应格式
        if not resp:
            return {} if method == "post" else ""
        try:
            return resp.json()
        except ValueError:
            content_type = resp.headers.get("Content-Type", "").lower()
            return resp.text if content_type.startswith(("text/", "application/")) else resp.content

    def master(self) -> "BaseSpider":
        """通用主流程：关键词循环→数据源循环→分页请求→数据处理，子类无需重写"""
        try:
            # 1. 遍历关键词
            for keyword in self.keys:
                # 2. 遍历数据源（如有，由子类_get_source_types定义）
                source_types = self._get_source_types() or [None]  # 无数据源则默认1个循环
                for source_type in source_types:
                    try:
                        # 3. 更新当前关键词/数据源的搜索参数
                        self._update_search_data(keyword, source_type)
                        # 4. 重置分页参数（统一重置为第1页）
                        self._reset_page_param()

                        # 5. 第一次请求：获取总页数
                        search_resp = self.req("post", self.search_api, data=self.search_data)
                        if not search_resp:
                            self.logger.info(f"关键词[{keyword}]、数据源[{source_type}]：搜索响应为空")
                            continue

                        # 6. 提取总页数
                        total_page = self._extract_total_page(search_resp)
                        if total_page == 0:
                            self.logger.info(f"关键词[{keyword}]、数据源[{source_type}]：无搜索结果")
                            continue

                        # 7. 处理第1页数据
                        self._process_list_page(search_resp, keyword)

                        # 8. 处理后续分页（从第2页开始）
                        for page_num in range(2, total_page + 1):
                            self._update_page_param(page_num)  # 更新分页参数
                            page_resp = self.req("post", self.search_api, data=self.search_data)
                            self._process_list_page(page_resp, keyword)

                    except Exception as e:
                        self.logger.error(
                            f"关键词[{keyword}]、数据源[{source_type}]处理失败：{e}",
                            exc_info=True
                        )
            return self
        except Exception as e:
            self.logger.error(f"主流程异常：{e}", exc_info=True)
            return self

    def _reset_page_param(self) -> None:
        """重置分页参数为第1页（钩子方法：适配不同网站的分页参数名）"""
        if "PAGENUMBER" in self.search_data:
            self.search_data["PAGENUMBER"] = "1"
        elif "page" in self.search_data:
            self.search_data["page"] = "1"

    def _update_page_param(self, page_num: int) -> None:
        """更新分页参数（钩子方法：适配不同网站的分页参数名）"""
        if "PAGENUMBER" in self.search_data:
            self.search_data["PAGENUMBER"] = str(page_num)
        elif "page" in self.search_data:
            self.search_data["page"] = str(page_num)

    def _process_list_page(self, list_resp: dict, keyword: str) -> None:
        """通用列表页处理：解析列表→请求详情→解析详情→存储，子类无需重写"""
        # 1. 解析列表页数据（子类实现_parse_list_page）
        list_items = self._parse_list_page(list_resp)
        if not list_items:
            self.logger.info(f"关键词[{keyword}]：列表页无有效数据")
            return

        # 2. 循环处理每个列表项
        for item in list_items:
            title = item.get("title", "")
            release_time = item.get("release_time", "")
            raw_detail_url = item.get("detail_url", "")
            origin = item.get("origin", self.name)  # 来源默认取网站名

            # 3. 标题过滤
            if self.adopt_title_filter(title):
                continue

            # 4. 处理详情页URL（子类可覆盖_process_detail_url）
            detail_url = self._process_detail_url(raw_detail_url)
            if not detail_url:
                self.logger.warning(f"标题[{title}]：详情页URL无效")
                continue

            # 5. 请求详情页
            detail_html = self.req("get", detail_url)
            if not detail_html or not isinstance(detail_html, str):
                self.logger.warning(f"标题[{title}]：详情页请求失败或非文本")
                continue

            # 6. 内容过滤
            if self._filter_detail_content(detail_html):
                self.logger.info(f"标题[{title}]：详情页含过滤词，跳过")
                continue

            # 7. 解析详情页正文（子类实现_parse_detail_page）
            content = self._parse_detail_page(detail_html, title)
            if not content:
                self.logger.warning(f"标题[{title}]：详情页正文解析为空")
                continue

            # 8. 存储数据（通用add方法）
            self.add(title, release_time, origin, content, detail_url)

    def _filter_detail_content(self, detail_html: str) -> bool:
        """通用内容过滤：含过滤词则返回True（需过滤）"""
        return any(filter_word in detail_html for filter_word in self.filter_content)

    # ------------------------------ 通用数据操作（子类直接使用） ------------------------------
    def add(self, title: str, date: str, origin: str, content: str, link: str) -> None:
        """通用数据添加：子类无需修改"""
        self.df["标题"].append(title.strip())
        self.df["时间"].append(date.strip())
        self.df["来源"].append(origin.strip())
        self.df["正文"].append(content.strip())
        self.df["链接"].append(link.strip())
        self.df["所在网站"].append(self.name)
        self.logger.info(f"已添加：{title} | {link}")

    def adopt_title_filter(self, title: str) -> bool:
        """通用标题过滤：子类无需修改"""
        if any(filter_word in title for filter_word in self.filter_title):
            self.logger.info(f"标题过滤：{title}")
            return True
        return False

    def save(self, save_path: str = "spider_result.xlsx") -> None:
        """通用数据存储：子类直接调用"""
        if not any(self.df.values()):  # 无数据则不保存
            self.logger.info("无有效数据，不生成Excel")
            return
        df = pandas.DataFrame(self.df)
        df.to_excel(save_path, index=False, engine="openpyxl")
        self.logger.info(f"数据已保存至：{save_path}，共{len(df)}条")