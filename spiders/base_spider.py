# development time: 2025-08-20  14:15
# developer: 元英

# import requests
from curl_cffi import Session
from curl_cffi.requests.exceptions import HTTPError, ConnectionError, Timeout  # 导入curl_cffi的异常类

from typing import Callable
import pandas
from urllib3.util.retry import Retry
from Purchase.util.log import logger
from Purchase.setting import *


class BaseSpider(object):
    name = "BaseSpider"
    def __init__(self):
        self.logger = logger
        self.headers = {
            "Accept": "*/*",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36 Edg/139.0.0.0",
        }
        self.start_time = START_TIME
        self.end_time = END_TIME
        self.keys = KEYS
        self.filter_title = FILTER_TITLE
        self.filter_content = FILTER_CONTENT
        self.session =Session()
        self.df = {
            "标题":[],
            "时间":[],
            "来源":[],
            "正文":[],
            "链接":[],
            "所在网站":[],
        }


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


    def add(self,title,date,origin,content,link,website):
        self.df["标题"].append(title)
        self.df["时间"].append(date)
        self.df["来源"].append(origin)
        self.df["正文"].append(content)
        self.df["链接"].append(link)
        self.df["所在网站"].append(website)
        self.logger.info(f"{title} | {link} | {website} | 已添加")

    def adopt_title_filter(self, title: str) ->bool:
        if any(k in title for k in self.filter_title):
            self.logger.info(f"{title}--已被过滤")
            return True
        return False

    def save(self):
        """ 存储逻辑 """
        df = pandas.DataFrame(self.df)
        df.to_excel(".xlsx",index=False)