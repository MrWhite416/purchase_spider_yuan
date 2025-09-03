# development time: 2025-08-20  14:15
# developer: 元英
import math
import time

# import requests
from curl_cffi import Session
from curl_cffi.requests.exceptions import HTTPError, ConnectionError, Timeout  # 导入curl_cffi的异常类


from util.log import logger
from types import FunctionType
from setting import *
from functools import wraps


# 定义通用异常捕获装饰器
def exception_handler(func):
    @wraps(func)  # 保留原函数的元信息（如名称、文档）
    def wrapper(self, *args, **kwargs):
        try:
            # 调用被装饰的方法（子类实现的逻辑）
            return func(self, *args, **kwargs)
        except Exception as e:
            # 统一异常处理：日志记录、返回默认值等
            logger.error(f"来自 {self.__class__.__name__}（{self.name}） 类的方法 {func.__name__} 执行出错: {str(e)}", exc_info=True)
            # raise  # 可根据需求返回默认值或自定义结果
    return wrapper


# 3. 定义元类（自动为所有方法添加装饰器）
class ExceptionHandlerMeta(type):
    def __new__(cls, name, bases, namespace, **kwargs):
        # 遍历类的所有属性
        for attr_name, attr_value in namespace.items():
            # 只处理自定义方法（排除特殊方法如__init__、__str__等）
            if (
                    isinstance(attr_value, FunctionType)  # 是函数/方法
                    and not attr_name.startswith("__")  # 不是特殊方法（可根据需要调整）
            ):
                # 用装饰器包装方法
                namespace[attr_name] = exception_handler(attr_value)

        # 创建并返回新类
        return super().__new__(cls, name, bases, namespace)



class BaseSpider(metaclass=ExceptionHandlerMeta):
    # ------------------------------ 子类必须定义：网站元信息（类属性） ------------------------------
    website: str = ""  # 网站域名
    name: str = ""  # 网站名称
    base_url: str = ""  # 基础URL（用于拼接相对链接）
    search_api: str = ""  # 搜索接口URL（可能不止一个搜索接口）
    detail_api: str = ""  # 详情页API（可选）

    def __init__(self):
        # 1. 通用初始化
        self.start_time = START_TIME
        self.end_time = END_TIME
        self.keys = KEYS
        self.filter_title = FILTER_TITLE
        self.filter_content = FILTER_CONTENT

        # 2. 请求配置
        self.session = Session()
        self.headers = self._get_default_headers()  # 默认请求头（钩子）

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
        return {"标题": [], "时间": [], "来源": [], "链接": [], "所在网站": [], "正文": []}

    # ------------------------------ 通用工具方法（子类直接使用） ------------------------------
    def adopt_title_filter(self, title: str) -> bool:
        """标题过滤：通用逻辑"""

        # 过滤结果等已经开标的公告
        if any(word in title for word in self.filter_title):
            self.logger.info(f"标题过滤：{title}")
            return True

        return False

    def add(self, title: str, date: str, origin: str | None, content: str, link: str) -> None:
        """数据存储：通用逻辑"""
        self.df["标题"].append(title.strip() if title else None)
        self.df["时间"].append(date.strip())
        self.df["来源"].append(origin.strip() if origin else None)
        self.df["正文"].append(content.strip() if content else None)
        self.df["链接"].append(link.strip() if link else None)
        self.df["所在网站"].append(self.name)
        self.logger.info(f"已添加：{title} | {link} | 网站：{self.name}")

    def save(self, save_path: str = "spider_result.xlsx") -> None:
        """数据保存：通用逻辑"""
        import pandas as pd
        if not any(self.df.values()):
            self.logger.info("无有效数据，不保存")
            return
        pd.DataFrame(self.df).to_excel(save_path, index=False, engine="openpyxl")
        self.logger.info(f"保存完成：{save_path}（{len(self.df['标题'])}条）")

    def req(self, method: str, url: str, headers: dict, params: dict = None, data=None,
            json_d: dict | str = None) -> dict | str | bytes:

        method_lower = method.lower()
        if method_lower not in ["get", "post"]:
            self.logger.error("不支持该方法")
            raise ValueError("不支持该方法")

        # 获取请求方法
        fetch_func = getattr(self.session, method_lower)
        for i in range(3):  # 重试三次

            try:
                resp = fetch_func(url, headers=headers, params=params, json=json_d, data=data, verify=False,timeout=60)
                resp.raise_for_status()
                break  # 只要请求不出错就不重试

            except HTTPError as e:
                self.logger.error(f"请求出错（状态码不为2）；{e} | 链接：{url}")
                time.sleep(3)
                continue  # 请求出错就重试
            except Exception as e:
                self.logger.error(f"链接：{url} | 请求头：{headers} | 请求参数：{params or json_d or data} | 请求出错：{e}")
                if i == 2:
                    self.logger.critical(
                        f"链接：{url} | 请求头：{headers} | 请求参数：{params or json_d or data} | <三次请求全部失败>：{e}")
                continue  # 请求出错就重试


        try:
            return resp.json()
        except ValueError as e:
            # 解析JSON失败，根据Content-Type判断
            content_type = resp.headers.get('Content-Type', '').lower()

            # 取前16字节内容（足够判断大多数文件类型）
            content_sample = resp.content[:16] if resp.content else b''

            # 二进制文件的签名（Magic Number）
            binary_signatures = [
                b'%PDF-',  # PDF
                b'\x89PNG\r\n\x1a\n',  # PNG
                b'\xff\xd8\xff',  # JPEG
                b'GIF87a', b'GIF89a',  # GIF
                b'PK\x03\x04',  # ZIP
                b'RIFF',  # WAV/AVI
                b'MThd',  # MIDI
                b'\x1f\x8b',  # GZIP
            ]

            # 如果内容匹配任何二进制签名，判定为二进制
            for sig in binary_signatures:
                if content_sample.startswith(sig):
                    return resp.content

            # 文本类型（如text/html、text/plain等）
            if content_type.startswith(('text/', 'application/json', 'application/javascript')):
                return resp.text

            # 二进制类型（如图片、文件等）
            else:
                return resp.content



