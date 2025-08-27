# development time: 2025-08-26  8:44
# developer: 元英


import re
from lxml import etree
from util.tool import element_to_text

from curl_cffi import Session
from curl_cffi.requests.exceptions import HTTPError, ConnectionError, Timeout  # 导入curl_cffi的异常类

from abc import ABC, abstractmethod

from lxml import etree
import json
from urllib3.util.retry import Retry
from util.log import logger
from setting import *


class BaseSpider(ABC):
    # ------------------------------ 子类必须定义：网站元信息（类属性） ------------------------------
    website: str = ""  # 网站域名
    name: str = ""  # 网站名称
    base_url: str = ""  # 基础URL（用于拼接相对链接）
    search_api: str = ""  # 搜索接口URL
    detail_api: str = ""  # 详情页API（可选）

    def __init__(self, start_time: str, end_time: str, keys: list, filter_title: list, filter_content: list):
        # 1. 通用初始化
        self.start_time = start_time
        self.end_time = end_time
        self.keys = keys
        self.filter_title = filter_title
        self.filter_content = filter_content

        # 2. 请求配置
        self.session = Session()
        self.headers = self._get_default_headers()  # 默认请求头（钩子）
        self.search_data = self._prepare_search_data()  # 搜索参数（钩子）
        self.req_config = self._get_search_req_config()  # 请求配置（钩子）

        # 3. 状态管理
        self.df = self._init_dataframe()  # 数据存储
        self.logger = logger
        self.temp_meta = {"release_time": "", "origin": ""}  # 临时存储详情页元数据


    # ------------------------------ 通用工具：基础配置（子类极少覆盖） ------------------------------
    def _get_default_headers(self) -> dict:
        """默认请求头：子类可覆盖添加特殊Header（如X-Requested-With）"""
        return {
            "Accept": "*/*",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36 Edg/139.0.0.0",
        }

    def _init_dataframe(self) -> dict:
        """通用数据存储结构：所有子类统一"""
        return {"标题": [], "时间": [], "来源": [], "正文": [], "链接": [], "所在网站": []}


    # ------------------------------ 核心配置钩子：子类必须实现（最小差异点） ------------------------------
    @abstractmethod
    def _prepare_search_data(self) -> dict:
        """钩子1：返回该网站的初始搜索参数（如Spider3的data、Spider4的params）"""
        pass

    @abstractmethod
    def _get_search_req_config(self) -> dict:
        """钩子2：定义搜索请求的核心配置（覆盖所有参数格式/响应类型）
        返回格式：
        {
            "method": "post",          # 请求方法："get"/"post"
            "param_type": "data",      # 参数传递方式："data"/"params"
            "param_format": "form",    # 参数格式："form"（默认）/"json"（需序列化）
            "resp_type": "json",       # 搜索响应类型："json"/"html"
            "page_param_name": "PAGENUMBER"  # 分页参数名（如"currPage"/"pageNo"）
        }
        """
        pass

    @abstractmethod
    def _extract_total_page(self, parsed_resp) -> int:
        """钩子3：提取总页数（parsed_resp为预处理后的响应：JSON字典或HTML selector）"""
        pass

    @abstractmethod
    def _parse_list_item(self, list_data) -> dict:
        """钩子4：解析单个列表项（list_data为单条列表数据：JSON字典或HTML节点）
        返回格式：{"title": "xxx", "raw_detail_url": "xxx", "list_time": "xxx", "list_origin": "xxx"}
        """
        pass

    @abstractmethod
    def _parse_detail(self, detail_data) -> tuple[str, str, str]:
        """钩子5：解析详情页（detail_data为预处理后的详情数据：HTML selector/API字典/PDF二进制）
        返回格式：(content: 正文, release_time: 发布时间, origin: 来源)
        """
        pass


    # ------------------------------ 场景适配钩子：子类按需覆盖（非必须） ------------------------------
    def _get_dynamic_params(self) -> dict:
        """钩子6：获取动态参数（如验证码、时间戳，默认返回空）"""
        return {}

    def _get_channels(self) -> list:
        """钩子7：获取需遍历的渠道/分类（如Spider6的channel_ids，默认返回空列表）"""
        return []

    def _standardize_time(self, time_str: str) -> str:
        """钩子8：标准化时间格式（如Spider10的日期差值、Spider4的拼接时分秒，默认返回原字符串）"""
        return time_str

    def _process_detail_url(self, raw_url: str, list_item: dict) -> str:
        """钩子9：处理详情页URL（如Spider6的AES加密、Spider7的参数拼接，默认返回原URL）"""
        return raw_url

    def _preprocess_search_resp(self, resp: dict | str) -> dict | etree._Element:
        """钩子10：预处理搜索响应（如Spider5的JSON字符串解析、Spider6的HTML转selector，默认返回原响应）"""
        req_config = self._get_search_req_config()
        if req_config["resp_type"] == "html":
            return etree.HTML(resp) if isinstance(resp, str) else resp
        elif req_config["resp_type"] == "json":
            # 处理嵌套JSON（如Spider5的resp["result"]是JSON字符串）
            if "result" in resp and isinstance(resp["result"], str):
                try:
                    resp["result"] = json.loads(resp["result"])
                except:
                    pass
            return resp
        return resp

    def _preprocess_detail_data(self, detail_raw: dict | str | bytes) -> any:
        """钩子11：预处理详情页原始数据（如API转字典、PDF二进制保留，默认返回原数据）"""
        req_config = self._get_search_req_config()
        if isinstance(detail_raw, str) and "<html" in detail_raw[:20]:
            return etree.HTML(detail_raw)  # HTML详情页转selector
        elif isinstance(detail_raw, dict) or isinstance(detail_raw, bytes):
            return detail_raw  # API字典或PDF二进制直接返回
        return detail_raw

    def _get_detail_type(self, list_item: dict) -> str:
        """钩子12：指定详情页类型（默认"html"，可选"api"/"pdf"）"""
        return "html"


    # ------------------------------ 分页定制钩子（子类按需覆盖） ------------------------------
    def _get_initial_page(self) -> int | str:
        """钩子13：定义第一页的页码（支持数字或字符串，如0、1、"10"）"""
        return 1

    def _get_next_page(self, current_page: int | str) -> int | str:
        """钩子14：定义从当前页计算下一页的规则
        :param current_page: 当前页码（与_initial_page类型一致）
        :return: 下一页页码
        """
        # 默认实现：页码+1（适用于1→2→3...场景）
        return current_page + 1

    def _is_page_valid(self, current_page: int | str, total_page: int) -> bool:
        """钩子15：判断当前页码是否有效（未超过总页数）
        :param current_page: 当前页码
        :param total_page: 总页数（由_extract_total_page返回）
        :return: 是否继续分页
        """
        # 默认实现：当前页≤总页数（适用于常规分页）
        return int(current_page) <= total_page


    # ------------------------------ 通用流程：基类实现（子类无需修改） ------------------------------
    def _update_search_data(self, keyword: dict, channel: any = None) -> None:
        """更新搜索参数：关键词+渠道+动态参数"""

        # 1. 更新关键词（字典：{参数键名: 关键词值}（推荐，精准映射））
        param_key, param_value = next(iter(keyword.items()))
        self.search_data[param_key] = param_value

        # 2. 更新渠道（如Spider6的channelId）
        if channel is not None:
            channel_keys = ["channelId", "SOURCE_TYPE", "regionCode"]
            for key in channel_keys:
                if key in self.search_data:
                    self.search_data[key] = channel
                    break

        # 3. 更新动态参数（如验证码、时间戳）
        dynamic_params = self._get_dynamic_params()
        for k, v in dynamic_params.items():
            if k in self.search_data:
                self.search_data[k] = v

        # 4. 标准化时间参数
        time_keys = ["starttime", "endtime", "TIMEBEGIN", "TIMEEND", "operationStartTime", "operationEndTime"]
        for key in time_keys:
            if key in self.search_data and self.search_data[key]:
                self.search_data[key] = self._standardize_time(self.search_data[key])

    def _prepare_req_params(self) -> dict:
        """准备请求参数：适配form/json格式"""
        req_config = self._get_search_req_config()
        if req_config["param_format"] == "json":
            # JSON格式需序列化（如Spider10/11）
            return json.dumps(self.search_data, separators=(",", ":"))
        # form/params格式直接返回字典
        return self.search_data

    def _fetch_search_resp(self) -> dict | etree._Element:
        """发送搜索请求：适配GET/POST、data/params、form/json"""
        req_config = self._get_search_req_config()
        method = req_config["method"].lower()
        param_type = req_config["param_type"]
        req_params = self._prepare_req_params()

        # 构建请求参数
        req_kwargs = {}
        if param_type == "data":
            req_kwargs["data"] = req_params
        elif param_type == "params":
            req_kwargs["params"] = req_params
        elif param_type == "json":
            req_kwargs["json"] = req_params


        # 发送请求
        resp = self._req(method, self.search_api, **req_kwargs)
        # 预处理响应（JSON转字典/HTML转selector）
        return self._preprocess_search_resp(resp)

    def _fetch_detail_data(self, detail_url: str) -> any:
        """获取详情页数据：适配HTML/API/PDF"""
        detail_type = self._get_detail_type({})
        if detail_type == "api":
            # API类型详情页（如Spider7/9）
            resp = self._req("get", detail_url)
            return self._preprocess_detail_data(resp)
        elif detail_type == "pdf":
            # PDF类型详情页（如Spider8/10）
            resp = self._req("get", detail_url)
            return self._preprocess_detail_data(resp.content if isinstance(resp, str) else resp)
        else:
            # HTML类型详情页（如Spider3/5）
            resp = self._req("get", detail_url)
            return self._preprocess_detail_data(resp)

    def _req(self, method: str, url: str, **kwargs) -> dict | str | bytes:
        """通用请求：重试+自动解析响应"""
        for retry in range(3):
            try:
                resp = getattr(self.session, method)(
                    url, headers=self.headers, verify=False, **kwargs
                )
                resp.raise_for_status()
                # 自动解析响应类型
                if "json" in resp.headers.get("Content-Type", ""):
                    return resp.json()
                elif "text" in resp.headers.get("Content-Type", "") or "<html" in resp.text[:20]:
                    return resp.text
                else:
                    return resp.content  # 二进制（如PDF）
            except HTTPError as e:
                if e.response.status_code in [404, 403, 410]:
                    self.logger.error(f"致命错误[{e.response.status_code}]：{url}")
                    return {} if method == "post" else ""
                self.logger.error(f"请求重试[{retry + 1}]：{e} | {url}")
            except Exception as e:
                self.logger.error(f"网络重试[{retry + 1}]：{e} | {url}")
                if retry == 2:
                    return {} if method == "post" else ""
        return {} if method == "post" else ""

    def _process_list(self, parsed_resp) -> list[dict]:
        """处理列表页：解析所有列表项"""
        list_items = []
        req_config = self._get_search_req_config()
        # 适配JSON/HTML列表数据
        if req_config["resp_type"] == "json":
            # 提取列表数据（适配不同JSON路径）
            list_data_path = ["data", "rows", "search_ZbGg", "list", "middle.listAndBox"]
            data = parsed_resp
            for path in list_data_path:
                if path in data and isinstance(data[path], list):
                    data = data[path]
                    break
            if not isinstance(data, list):
                data = parsed_resp.get("data", {}).get("rows", [])
        elif req_config["resp_type"] == "html":
            # HTML列表数据（如Spider6的.article-list3-t）
            data = parsed_resp.xpath(".//div[@class='article-list3-t']") or parsed_resp.xpath(
                ".//table[@class='content_table']/tbody/tr")

        # 解析单个列表项
        for item in data:
            list_item = self._parse_list_item(item)
            if not list_item or self.adopt_title_filter(list_item["title"]):
                continue
            # 处理详情页URL
            list_item["detail_url"] = self._process_detail_url(list_item["raw_detail_url"], list_item)
            list_items.append(list_item)
        return list_items

    def master(self) -> "BaseSpider":
        """主流程：覆盖所有场景（多渠道+多关键词+分页+详情页）"""
        try:
            # 1. 获取需遍历的渠道（如Spider6的channel_ids）
            channels = self._get_channels() or [None]
            for channel in channels:
                # 2. 遍历关键词
                for keyword in self.keys:
                    try:
                        # 3. 初始化搜索参数（关键词+渠道+动态参数）
                        self._update_search_data(keyword, channel)
                        page_param_name = self._get_search_req_config()["page_param_name"]
                        first_page = self._get_initial_page()  # 获取第一页页码
                        self.search_data[page_param_name] = first_page  # 重置为第1页

                        # 4. 首次请求：获取总页数
                        parsed_resp = self._fetch_search_resp()
                        total_page = self._extract_total_page(parsed_resp)
                        if not total_page:
                            self.logger.info(f"渠道[{channel}]关键词[{keyword}]：无结果")
                            continue

                        # 5. 处理第1页
                        list_items = self._process_list(parsed_resp)
                        self._process_detail_batch(list_items)

                        # 6. 处理后续分页
                        for page_num in range(2, total_page + 1):
                            self.search_data[page_param_name] = str(page_num)
                            parsed_resp = self._fetch_search_resp()
                            list_items = self._process_list(parsed_resp)
                            self._process_detail_batch(list_items)

                    except Exception as e:
                        self.logger.error(f"渠道[{channel}]关键词[{keyword}]失败：{e}", exc_info=True)
            return self
        except Exception as e:
            self.logger.error(f"主流程失败：{e}", exc_info=True)
            return self

    def _process_detail_batch(self, list_items: list[dict]) -> None:
        """批量处理详情页：存储数据"""
        for item in list_items:
            try:
                # 获取详情页数据
                detail_data = self._fetch_detail_data(item["detail_url"])
                # 解析详情页
                content, release_time, origin = self._parse_detail(detail_data)
                if not content:
                    continue
                # 补充默认值
                release_time = release_time or item.get("list_time", "")
                origin = origin or item.get("list_origin", self.name)
                # 存储数据
                self.add(item["title"], release_time, origin, content, item["detail_url"])
            except Exception as e:
                self.logger.error(f"详情页失败[{item['detail_url']}]：{e}", exc_info=True)


    # ------------------------------ 通用工具方法（子类直接使用） ------------------------------
    def adopt_title_filter(self, title: str) -> bool:
        """标题过滤：通用逻辑"""
        if any(word in title for word in self.filter_title):
            self.logger.info(f"标题过滤：{title}")
            return True
        return False

    def add(self, title: str, date: str, origin: str, content: str, link: str) -> None:
        """数据存储：通用逻辑"""
        self.df["标题"].append(title.strip())
        self.df["时间"].append(date.strip())
        self.df["来源"].append(origin.strip())
        self.df["正文"].append(content.strip())
        self.df["链接"].append(link.strip())
        self.df["所在网站"].append(self.name)
        self.logger.info(f"已添加：{title} | {link}")

    def save(self, save_path: str = "spider_result.xlsx") -> None:
        """数据保存：通用逻辑"""
        import pandas as pd
        if not any(self.df.values()):
            self.logger.info("无有效数据，不保存")
            return
        pd.DataFrame(self.df).to_excel(save_path, index=False, engine="openpyxl")
        self.logger.info(f"保存完成：{save_path}（{len(self.df['标题'])}条）")


    def req(self,method:str,url:str,headers:dict,params:dict=None,data=None,json_d:dict=None) ->dict|str|bytes:

        method_lower = method.lower()
        if method_lower not in ["get","post"]:
            self.logger.error("不支持该方法")
            raise ValueError("不支持该方法")

        # 获取请求方法
        fetch_func = getattr(self.session, method_lower)
        for i in range(3):  # 重试三次

            try:
                resp = fetch_func(url,headers=headers,params=params,json=json_d,data=data,verify=False)
                resp.raise_for_status()
                break   # 只要请求不出错就不重试
            except Exception as e:
                self.logger.error(f"链接：{url}，请求出错：{e}")
                if i == 2:
                    raise
                continue  # 请求出错就重试
            except HTTPError as e:
                self.logger.error(f"请求出错（状态码不为2）；{e} | 链接：{url}")
                continue  # 请求出错就重试

        try:
            return resp.json()
        except ValueError as e:
            # 解析JSON失败，根据Content-Type判断
            content_type = resp.headers.get('Content-Type', '').lower()

            # 文本类型（如text/html、text/plain等）
            if content_type.startswith(('text/', 'application/json', 'application/javascript')):
                return resp.text

            # 二进制类型（如图片、文件等）
            else:
                return resp.content




class Spider3(BaseSpider):
    # 1. 网站元信息
    website = "ggzy.gov.cn/"
    name = "全国公共资源交易平台"
    base_url = "https://www.ggzy.gov.cn"
    search_api = "https://deal.ggzy.gov.cn/ds/deal/dealList_find.jsp"

    # 2. 必须钩子1：初始搜索参数
    def _prepare_search_data(self) -> dict:
        return {
            "TIMEBEGIN_SHOW": self.start_time,
            "TIMEEND_SHOW": self.end_time,
            "TIMEBEGIN": self.start_time,
            "TIMEEND": self.end_time,
            "SOURCE_TYPE": "1",
            "DEAL_TIME": "06",
            "DEAL_CLASSIFY": "00",
            "DEAL_STAGE": "0100",
            "DEAL_PROVINCE": "0",
            "DEAL_CITY": "0",
            "DEAL_PLATFORM": "0",
            "BID_PLATFORM": "0",
            "DEAL_TRADE": "0",
            "isShowAll": "1",
            "PAGENUMBER": "1",
            "FINDTXT": ""
        }

    # 3. 必须钩子2：搜索请求配置
    def _get_search_req_config(self) -> dict:
        return {
            "method": "post",
            "param_type": "data",
            "param_format": "form",
            "resp_type": "json",
            "page_param_name": "PAGENUMBER"
        }

    # 4. 必须钩子3：提取总页数
    def _extract_total_page(self, parsed_resp: dict) -> int:
        return int(parsed_resp.get("data", {}).get("ttlpage", 0))

    # 5. 必须钩子4：解析列表项
    def _parse_list_item(self, list_data: dict) -> dict:
        return {
            "title": list_data.get("title", ""),
            "raw_detail_url": list_data.get("url", ""),
            "list_time": "",
            "list_origin": self.name
        }

    # 6. 必须钩子5：解析详情页（HTML）
    def _parse_detail(self, detail_data: etree._Element) -> tuple[str, str, str]:
        # 提取时间和来源
        pattern = r"class=\"h4_o\">(.+?)</h4>.+?(?:发布|签署)时间：(.+?)</span>.+?platformName\">(.+?)</label>"
        raw_html = etree.tostring(detail_data, encoding="unicode")
        res = re.findall(pattern, raw_html, re.DOTALL)
        release_time = res[0][1] if res else ""
        origin = res[0][2] if res else self.name

        # 提取正文
        content_div = detail_data.xpath(".//div[@id='mycontent']")[0]
        content_html = etree.tostring(content_div, method="html", encoding="unicode")
        content = element_to_text(content_html)
        return content, release_time, origin

    # 7. 场景钩子：处理详情页URL（替换/a/为/b/、http转https）
    def _process_detail_url(self, raw_url: str, list_item: dict) -> str:
        return raw_url.replace("/a/", "/b/").replace("http:", "https:")

    # 8. 场景钩子：遍历数据源（1和2）
    def _get_channels(self) -> list:
        return [1, 2]







