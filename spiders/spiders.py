# development time: 2025-08-20  16:01
# developer: 元英
import datetime
import json
import hashlib
import random

from Crypto.Util.Padding import unpad
import base64
import time
from Crypto.Cipher import AES, DES
from Crypto.Util.Padding import pad  # pkcs7填充
import base64
from lxml import etree
import re
import math
from urllib.parse import urlencode, unquote
import traceback  # 堆栈库

from .base_spider import BaseSpider
from util.tool import element_to_text, pdf_to_text
from util.verification_code import ocr_code


class Spider1(BaseSpider):
    website = "ccgp.gov.cn"
    name = "中国政府采购网"
    url = "https://www.ccgp.gov.cn/"
    search_api = "https://search.ccgp.gov.cn/bxsearch"

    def __init__(self):
        BaseSpider.__init__(self)
        self.params = {
            "searchtype": "1",
            "page_index": "1",  # 页码
            "bidSort": "",
            "buyerName": "",
            "projectId": "",
            "pinMu": "",
            "bidType": "",
            "dbselect": "bidx",
            "kw": "卫星",  # 关键词
            "start_time": self.standard_time(self.start_time),  # 开始时间
            "end_time": self.standard_time(self.end_time),  # 结束时间
            "timeType": "6",  # 指定时间
            "displayZone": "",
            "zoneId": "",
            "pppStatus": "0",
            "agentName": ""
        }
        self.run_flag = True
        self.first_page_num = 1

    def master(self):
        for k in self.keys:
            self.params["page_index"] = str(self.first_page_num)
            self.params["kw"] = k

            headers = self.update_headers()
            resp = self.req("get", url=self.search_api, headers=headers, params=self.params)
            total_page = self.gain_total_page(resp)

            if not total_page:
                self.logger.info(f"[{k}] | 无数据")

            self.process(resp)

            # 分页
            for page_num in range(self.first_page_num + 1, total_page + 1):
                self.params["page_index"] = page_num
                resp = self.req("get", url=self.search_api, headers=headers, params=self.params)

                self.process(resp)
            time.sleep(4)

        return self

    def process(self, resp):

        urls = self.clean_urls(resp)

        for title, release_time, link in urls:
            detail = self.req("get", url=link, headers=self.headers)
            origin, text = self.clean_detail(detail)

            self.add(title, release_time, origin, text, link)

    def clean_urls(self, resp):

        sele = etree.HTML(resp)
        lis = sele.xpath(".//ul[@class='vT-srch-result-list-bid']/li")
        urls = []

        for li in lis:
            title = etree.tostring(li.xpath("./a")[0], method="text", encoding="unicode").strip()
            if self.adopt_title_filter(title):
                continue

            link = li.xpath("./a/@href")[0]
            time_organ = li.xpath("./span/text()")[0]
            release_time = time_organ.split("|")[0].strip()

            urls.append([title, release_time, link])

        return urls

    def clean_detail(self, detail):
        try:
            sele = etree.HTML(detail)
            origin = self.name

            content_ele = sele.xpath(".//div[@class='vF_detail_content']")[0]
            content = etree.tostring(content_ele, method="html", encoding="unicode")

            text = element_to_text(content)

            return origin, text
        except Exception as e:
            self.logger.error(f"错误行号：{e.__traceback__.tb_lineno}")
            raise

    def update_headers(self):

        headers = {}
        headers.update(self.headers)

        headers[
            "Accept"] = "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7"

        return headers

    def gain_total_page(self, resp):
        """ 获取总页数 """

        sele = etree.HTML(resp)
        p_eles = sele.xpath(".//p[@class='pager']")
        if not p_eles:
            return 0  # 没有页码表元素，说明没有数据

        total_page = 1
        for i in p_eles[0].xpath("./*/text()"):
            if str(i).isdigit():

                if int(i) > total_page:
                    total_page = int(i)

        return int(total_page)

    def standard_time(self, tt):
        return tt.replace("-", ":")


# 弃用
class Spider2(BaseSpider):
    website = "bulletin.cebpubservice.com"
    name = "中国招标投标公共服务平台"
    url = "https://bulletin.cebpubservice.com"
    search_api = ""

    def __init__(self):
        BaseSpider.__init__(self)
        self.run_flag = True

    def master(self):
        return self

    def clean(self):
        pass

    def is_next(self):
        pass


class Spider3(BaseSpider):
    website = "ggzy.gov.cn/"
    name = "全国公共资源交易平台"
    url = "https://www.ggzy.gov.cn"
    search_api = "https://deal.ggzy.gov.cn/ds/deal/dealList_find.jsp"

    def __init__(self):
        BaseSpider.__init__(self)
        self.data = {
            "TIMEBEGIN_SHOW": self.start_time,  # 开始时间
            "TIMEEND_SHOW": self.end_time,  # 结束时间
            "TIMEBEGIN": self.start_time,  # 开始时间
            "TIMEEND": self.end_time,  # 结束时间
            "SOURCE_TYPE": "1",  # 数据来源（省平台1或央企招投标2）
            "DEAL_TIME": "06",
            "DEAL_CLASSIFY": "00",  # 数据来源（省平台00或央企招投标01）
            "DEAL_STAGE": "0100",  # 业务及信息类型（不限业务的交易公告 0001）
            "DEAL_PROVINCE": "0",
            "DEAL_CITY": "0",
            "DEAL_PLATFORM": "0",
            "BID_PLATFORM": "0",
            "DEAL_TRADE": "0",
            "isShowAll": "1",
            "PAGENUMBER": "1",  # 页码
            "FINDTXT": "卫星"  # 关键词
        }
        self.total_page = 0
        self.run_flag = True
        self.first_page_num = 1

    def master(self):

        for k in self.keys:  # 遍历关键词
            for i, n,l in [("1", "00","0001"), ('2',"01" ,"0101")]:  # 遍历数据源

                try:
                    self.data["SOURCE_TYPE"] = str(i)
                    self.data["DEAL_CLASSIFY"] = n
                    self.data["DEAL_STAGE"] = l
                    self.data["FINDTXT"] = k
                    self.data["PAGENUMBER"] = str(self.first_page_num)  # 必须初始化页码参数

                    # 第一次请求搜索接口
                    resp = self.req("post", url=self.search_api, headers=self.headers, data=self.data)

                    # 获取总页数
                    try:
                        self.total_page = resp["ttlpage"]
                    except Exception as e:
                        self.logger.error(f"{e} | {k} | {i,l} | {resp} | {self.data}")
                    # 如果总页数为0
                    if not self.total_page:
                        self.logger.info(f"[{k}]没有搜索结果")
                        continue
                    self.logger.info(f"关键词：[{k}] | {i,n,l} | 第一页")
                    self.process(resp)

                    # 分页逻辑
                    for page_num in range(self.first_page_num + 1, self.total_page + 1):
                        self.logger.info(f"关键词：[{k}] | {i, n, l} | 第{page_num}页")
                        self.data["PAGENUMBER"] = int(page_num)

                        resp = self.req("post", url=self.search_api, headers=self.headers, data=self.data)
                        self.process(resp)

                except Exception as e:
                    self.logger.error(f"{self.name} | 出错 | {e} | 错误行号：{e.__traceback__.tb_lineno}")

        return self

    def process(self, resp):
        urls = self.clean_url(resp)

        for t, u in urls:
            b_u = u.replace("/a/", "/b/").replace("http:", "https:")
            source = self.req("get", url=b_u, headers=self.headers)

            res = self.clean_detail(source, t)
            if not res:
                continue
            title, release_date, origin, text = res
            link = b_u
            self.add(title, release_date, origin, text, link)
            time.sleep(1)

    def clean_url(self, data: dict):
        try:
            datas = data["data"]

            urls = []
            for d in datas:
                title = d["title"].strip()

                if self.adopt_title_filter(title):
                    continue  # 过滤掉存在过滤词的url
                urls.append((title, d["url"]))

            return urls
        except Exception as e:
            self.logger.error(f"{self.name} | 出错 | {e} | 错误行号：{e.__traceback__.tb_lineno}")

    def clean_detail(self, source: str, tit):
        doc_pattern = r"class=\"h4_o\">(.+?)</h4>.+?(?:发布|签署)时间：(.+?)</span>.+?platformName\">(.+?)</label>"  # 提取标题，时间，来源。

        if any(k in source for k in self.filter_content):
            self.logger.info(f"{tit}--被过滤，网站：{self.name}")
            return None
        res = re.findall(doc_pattern, source, re.DOTALL)

        if not res:
            print(source)
            self.logger.error("匹配失败", exc_info=True)
            return None

        else:
            title, release_date, origin = res[0]

        # 清洗正文
        source = re.sub("<style.*?>.*</style>", "", source, flags=re.DOTALL)  # 删除css标签及内容
        doc_sele = etree.HTML(source)

        content = doc_sele.xpath(".//div[@id='mycontent']")[0]
        n_t = etree.tostring(content, method="html", encoding="unicode")
        text = element_to_text(n_t)

        return title, release_date, origin, text


class Spider4(BaseSpider):
    website = "ccgp-sichuan.gov.cn"
    name = "四川政府采购网"
    url = "https://www.ccgp-sichuan.gov.cn"
    search_api = "https://www.ccgp-sichuan.gov.cn/gpcms/rest/web/v2/info/selectInfoForIndex"
    code_api = "https://www.ccgp-sichuan.gov.cn/gpcms/rest/web/v2/index/getVerify"  # 验证码接口
    detail_api = "https://www.ccgp-sichuan.gov.cn/gpcms/rest/web/v2/index/selectInfoByOpenTenderCode"

    def __init__(self):
        BaseSpider.__init__(self)
        self.params = {
            "title": "办公",
            "region": "",
            "siteId": "94c965cc-c55d-4f92-8469-d5875c68bd04",
            "channel": "c5bff13f-21ca-4dac-b158-cb40accd3035",
            "currPage": "1",  # 当前页
            "pageSize": "40",  # 40条每页
            "noticeType": "00101",
            "regionCode": "",
            "cityOrArea": "",
            "purchaseManner": "",  # 采购方式（空为不限，1为公开招标）
            "openTenderCode": "",
            "purchaser": "",
            "agency": "",
            "purchaseNature": "",
            "operationStartTime": self.standard_time(self.start_time),
            "operationEndTime": self.standard_time(self.end_time),
            "verifyCode": "2200",
            "_t": "1755766552103"
        }
        self.page_total = 0
        self.run_flag = True
        self.first_page_num = 1

    def master(self):

        for k in self.keys:
            try:
                self.params["title"] = k
                self.params["verifyCode"] = self.code
                self.params["_t"] = str(int(time.time() * 1000))
                self.params["currPage"] = self.first_page_num

                search_result = self.req("get", url=self.search_api, headers=self.headers, params=self.params)

                total = search_result["data"]["total"]
                if not total:
                    self.logger.info(f"[{k}]没有数据")
                    continue

                # 计算总页数和当前页
                self.page_total = math.ceil(total / int(self.params["pageSize"]))

                self.process(search_result)

                # 分页逻辑
                for page_num in range(self.first_page_num + 1, self.page_total + 1):
                    self.params["currPage"] = page_num
                    search_result = self.req("get", url=self.search_api, headers=self.headers,
                                             params=self.params)
                    self.process(search_result)


            except Exception as e:
                self.logger.error(f"{self.name} | 出错 | {e} | 错误行号：{e.__traceback__.tb_lineno}")

        return self

    def process(self, resp):

        urls = self.clean_url(resp)

        for t, u,link in urls:
            detail_data = self.req("get", url=u, headers=self.headers)
            time.sleep(2.5)
            res = self.clean_detail(detail_data, t)
            if not res:
                continue
            title, release_date, origin, content = res

            self.add(title, release_date, origin, content, link)

    @property
    def code(self):
        """
        返回验证码
        :return:
        """

        resp = self.req("get", self.code_api, headers=self.headers)
        return ocr_code(resp)

    def clean_url(self, search_result):
        try:
            "https://www.ccgp-sichuan.gov.cn/maincms-web/article?"\
             "type=notice&"\
             "id=5a539c06-53fd-4b15-bb75-e57ed3e9cd72&"\
              "planId=8a69ced2977e23aa019786ea5b37186f"
            datas = search_result["data"]["rows"]
            urls = []
            if not datas:
                return None

            for d in datas:
                title = d["title"].strip()
                if self.adopt_title_filter(title):
                    self.logger.info(f"{title}--被过滤，网站：{self.name}")
                    continue

                # 拼接详情内容url
                params = {"site": d["site"], "planId": d["planId"], "_t": 1755826448587}
                encode_params = urlencode(params)
                url = self.detail_api + "?" + encode_params

                # 拼接人工访问链接
                link = f"https://www.ccgp-sichuan.gov.cn/maincms-web/article?type=notice&id={d['id']}&planId={d['planId']}"
                urls.append((title, url,link))
            return urls
        except Exception as e:
            self.logger.error(f"{self.name} | 出错 | {e} | 错误行号：{e.__traceback__.tb_lineno}")

            raise e

    def clean_detail(self, data, tit):
        """ 清洗详情内容 """

        try:

            details = data["data"]["rows"]
            notice_types = [i["noticeType"] for i in details]  # 获取该项目所有公告类型

            if ("001026" in notice_types) or ("0010004" in notice_types):
                self.logger.info(f"{tit}--被过滤，网站：{self.name}")
                return None  # 001026指的是结果公告，001004指的是废标公告

            for d in details:

                if tit != d["title"]:  # 判断多个公告是否是我们请求的公告
                    continue

                release_date = d["noticeTime"]
                origin = d["author"]
                n_content = d["content"]

                content = element_to_text(n_content)
                return tit, release_date, origin, content
        except Exception as e:
            self.logger.error(f"{self.name} | 出错 | {e} | 错误行号：{e.__traceback__.tb_lineno}")

    def standard_time(self, tt: str):
        """
        规范时间，将时间转为当前网站适配的时间
        :return:
        """

        return tt + " 00:00:00"


class Spider5(BaseSpider):
    website = "ggzyfw.beijing.gov.cn/"
    name = "北京市公共资源交易服务平台"
    url = "https://ggzyfw.beijing.gov.cn"
    search_api = "https://ggzyfw.beijing.gov.cn/elasticsearch/search"

    def __init__(self):
        BaseSpider.__init__(self)
        self.data = {
            "searchword": "卫星",
            "scope": "title",
            "channel_first": "jyxx",
            "channel_second": "all",
            "channel_third": "",
            "channel_fourth": "",
            "legislationType": "",
            "ext": "",
            "ext8": "",
            "starttime": self.start_time,
            "endtime": self.end_time,
            "sort": "",
            "page": "1",
            "size": ""
        }
        self.run_flag = True
        self.page_total = 0
        self.first_page_num = 1

    def master(self):
        for k in self.keys:
            self.data["searchword"] = k
            self.data["page"] = self.first_page_num

            try:
                resp = self.req("post", url=self.search_api, headers=self.headers, data=self.data)

                # 计算总页数
                total_records = resp["total"]
                if not total_records:
                    continue

                self.page_total = math.ceil(total_records / resp["size"])

                self.process(resp)

                # 开始分页
                for page_num in range(self.first_page_num + 1, self.page_total + 1):
                    self.data["page"] = str(page_num)

                    resp = self.req("post", url=self.search_api, headers=self.headers, data=self.data)
                    self.process(resp)

            except Exception as e:
                self.logger.error(f"{self.name} | 出错 | {e} | 错误行号：{e.__traceback__.tb_lineno}")

        return self

    def process(self, resp):

        urls = self.clean_url(resp)

        for title, release_time, u, origin in urls:
            content = self.req("get", url=u, headers=self.headers)
            text = self.clean_detail(content)
            self.add(title, release_time, origin, text, u)

    def clean_url(self, resp: dict):
        """ 解析出所有url """

        urls = []
        datas = json.loads(resp["result"])
        for d in datas:
            tit = d["title"]
            title = re.sub("</?b.*?>", "", tit, flags=re.DOTALL).strip()
            if self.adopt_title_filter(title):
                continue
            link = d["link"]
            origin = d["source"]
            release_time = d["releaseDate"]
            url = self.url + link
            urls.append((title, release_time, url, origin))
        return urls

    def clean_detail(self, content: str):
        """ 清洗详情信息 """
        sele = etree.HTML(content)
        ele = sele.xpath(".//div[@class='newsCon']")[0]
        n_t = etree.tostring(ele, method="html", encoding="unicode")
        text = element_to_text(n_t)
        return text


class Spider6(BaseSpider):
    website = "ggzy.zwfwb.tj.gov.cn"
    name = "天津市公共资源交易网"
    url = "http://ggzy.zwfwb.tj.gov.cn"
    search_api = "http://ggzy.zwfwb.tj.gov.cn/queryContent_{}-jyxx.jspx"
    channel_ids = {
        "政府采购": "76",
        "工程建设": "75",
        # "土地使用权": "237",
        # "国有产权": "78",
        # "农村产权": "255",
        # "矿业权交易": "247",
        # "二类疫苗": "303",
        # "药品采购": "240",
        # "碳排放权": "308",
        # "排污权": "311",
        # "林权交易": "266",
        # "知识产权": "314",
        # "用水权": "368",
        # "其他": "243",
    }  # 公告来源渠道参数

    def __init__(self):
        BaseSpider.__init__(self)
        self.params = {
            "title": "",
            "inDates": "",
            "ext": "",
            "ext1": "",
            "origin": "",
            "channelId": "76",
            "beginTime": self.start_time,
            "endTime": self.end_time
        }
        self.page_total = 0
        self.run_flag = True
        self.first_page_num = 1

    def master(self):
        for channel_id in self.channel_ids.values():
            for k in self.keys:
                # try:
                # 搜索请求
                self.params["title"] = k
                self.params["channelId"] = channel_id
                self.search_api = self.search_api.format(self.first_page_num)
                resp = self.req("get", url=self.search_api, headers=self.headers, params=self.params)

                # 获取总页数
                sele = etree.HTML(resp)
                # 获取总页数
                page_data = sele.xpath(".//div[@class='page-list']/ul/li[1]/a/text()")[0]
                self.page_total = int(re.findall("/([0-9]+?)页", page_data)[0].strip())

                if not self.page_total:
                    continue

                self.process(resp)
                for page_num in range(self.first_page_num + 1, self.page_total + 1):
                    self.search_api = self.search_api.format(page_num)
                    resp = self.req("get", url=self.search_api, headers=self.headers, params=self.params)

                    self.process(resp)

                # except Exception as e:
                #     self.logger.error(f"{self.name} | 出错 | {e} | 错误行号：{e.__traceback__.tb_lineno}")

        return self

    def process(self, resp):

        urls = self.clean_urls(resp)

        for u in urls:
            detail = self.req("get", url=u, headers=self.headers)
            title, release_time, origin, text = self.clean_detail(detail)

            self.add(title, release_time, origin, text, u)

    def clean_urls(self, resp: str) -> list:
        """ 清洗出详情页的链接 """

        urls = []
        sele = etree.HTML(resp)

        div_eles = sele.xpath(".//div[@class='article-list3-t']")
        for div in div_eles:
            title_ele, u = div.xpath("./a")[0], div.xpath("./a/@url")[0]  # 获取公告标题和未加密的链接

            title = etree.tostring(title_ele, method="text", encoding="utf8").decode("utf8").strip()

            if any(k in title for k in self.filter_title):
                self.logger.info(f"{title}--已被过滤")
                continue

            url = self.encrypt_url(u)
            urls.append(url)

        return urls

    def clean_detail(self, detail):
        """ 清洗出标准数据 """

        sele = etree.HTML(detail)

        content_ele = sele.xpath(".//div[@id='content']")[0]
        title = content_ele.xpath("./div[@class='content-title']/text()")[0].strip()
        release_time, origin = content_ele.xpath(".//font[1]/text()")[0].split("    ")

        release_time = release_time.strip("发布日期：")
        origin = origin.strip("发布来源：")

        # 删除标题元素和发布时间以及来源元素
        es = content_ele.xpath(".//font")
        for e in es:
            # 获取当前p元素的父节点（即div）
            parent = e.getparent()
            # 通过父节点删除当前p元素
            if parent is not None:  # 确保父节点存在
                parent.remove(e)

        # 然后提取正文元素
        text_ele = content_ele.xpath(".//div[@id='content']")[0]

        new_text = etree.tostring(text_ele, method="html", encoding="unicode")
        text = element_to_text(new_text)
        return title, release_time, origin, text

    def encrypt_url(self, url: str):
        """ 返回加密后的详情页链接 """

        u_id = url.rstrip("/").split("/")[-1].replace(".jhtml", "")
        plaintext = u_id.encode()
        key = "qnbyzzwmdgghmcnm".encode()

        cipher = AES.new(key, AES.MODE_ECB)
        ciphertext = cipher.encrypt(pad(plaintext, AES.block_size))
        new_id = base64.b64encode(ciphertext).decode().strip("==").replace("/", "^")

        # 函数接收匹配对象，只替换捕获组的内容，别的内容保留
        new_url = re.sub("/(\w+?)\.jhtml", lambda m: f"/{new_id}.jhtml", url)
        return new_url


class Spider7(BaseSpider):
    website = "szj.hebei.gov.cn"
    name = "河北省招标投标公共服务平台"
    url = "https://szj.hebei.gov.cn/zbtbfwpt/index"
    search_api = "https://szj.hebei.gov.cn/zbtbfwpt/tender/xxgk/zbgg.do"
    detail_api = "https://szj.hebei.gov.cn/zbtbfwpt/infogk/newDetail.do"

    def __init__(self):
        BaseSpider.__init__(self)
        # 更新请求头
        self.headers["X-Requested-With"] = "XMLHttpRequest"

        self.data = {
            "page": "0",
            "TimeStr": f"{self.start_time},{self.end_time}",
            "allDq": "",
            "allHy": "reset1,",
            "AllPtName": "",
            "KeyStr": "办公",
            "KeyType": "ggname",
            "captcha": ""
        }
        self.detail_params = {
            "categoryid": "101101",
            "infoid": "I1300000001137328001001",
            "laiyuan": "ptn"
        }
        self.run_flag = True
        self.page_total = 0
        self.first_page_num = 0

    def master(self):
        # for k in self.keys:
        for k in ["办公"]:
            self.data["KeyStr"] = k
            self.data["page"] = str(self.first_page_num)
            try:
                # 1. 首次请求
                search_result = self.req("post", url=self.search_api, headers=self.headers, data=self.data)

                # 2. 解析分页信息，计算总页数，获取当前页
                page_size = search_result["t"].get("pagesize", 10)
                total_records = search_result["t"].get("zbggrecords", 0)

                # 判断有无数据
                if not total_records:
                    self.logger.info(f"[{k}]关键词没有数据")
                    continue

                self.page_total = math.ceil(total_records / page_size) if page_size != 0 else 0

                self.process(search_result)

                for page_num in range(self.first_page_num + 1, self.page_total + 1):
                    self.data["page"] = str(page_num)
                    search_result = self.req("post", url=self.search_api, headers=self.headers, data=self.data)
                    self.process(search_result)



            except Exception as e:
                self.logger.error(f"{self.name} | 出错 | {e} | 错误行号：{e.__traceback__.tb_lineno}")

        return self

    def process(self, resp):

        info_ids = self.clean_url(resp)

        # 循环处理详情页
        for title, release_time, origin, info_id in info_ids:
            self.detail_params["infoid"] = info_id
            # 拼接出详情页的url
            link = f"{self.detail_api}?{urlencode(self.detail_params)}"

            detail = self.req("post", url=link, headers=self.headers)

            # 清洗出正文，添加结果
            text = self.clean_detail(detail)
            self.add(title, release_time, origin, text, link)

    def clean_url(self, data: dict):

        infos = data["t"]["search_ZbGg"]
        info_ids = []
        for i in infos:
            title = i["bulletinname"].strip()

            # 过滤
            if self.adopt_title_filter(title):
                continue

            info_id = i["tenderbulletincode"]
            origin = i["sourcename"]
            datetime_obj = datetime.datetime.fromtimestamp(i["bulletinissuetime"] / 1000)
            release_time = datetime_obj.strftime("%Y-%m-%d %H:%M:%S")
            info_ids.append([title, release_time, origin, info_id])

        return info_ids

    def clean_detail(self, detail):

        sele = etree.HTML(detail)
        try:
            parent_ele = sele.xpath('.//div[@class=" editcon"]')[0]
        except IndexError:
            parent_ele = sele.xpath(".//div[@class='infro_table']/tbody/tr[4]/td")[0]

        title_ele = parent_ele.xpath("./h2")[0]

        # 删除标题节点
        parent_ele.remove(title_ele)

        new_html = etree.tostring(parent_ele, method="html", encoding="unicode")
        text = element_to_text(new_html)
        return text


class Spider8(BaseSpider):
    website = "sxbid.com.cn"
    name = "山西省招标投标公共服务平台"
    url = "https://www.sxbid.com.cn"

    search_api = "https://www.sxbid.com.cn/f/new/search/searchList"

    def __init__(self):
        BaseSpider.__init__(self)
        self.data = {
            "pageNo": "1",
            "pageSize": "15",
            "searchField": "title",
            "searchContent": "卫星",
            "recentType": "",
            "startDate": self.start_time,
            "endDate": self.end_time,
            "releaseType": "",
            "projectPalce": "",
            "industryClassification": "",
            "cId": "3d6e34806adf48d5a59ad94f6f31deb5"
        }
        self.run_flag = True
        self.page_total = 0
        self.first_page_num = 1

    def master(self):
        # for k in self.keys:
        for k in ["办公"]:
            self.data["searchContent"] = k
            self.data["pageNo"] = self.first_page_num

            try:
                # 1. 首次请求
                resp = self.req("post", url=self.search_api, headers=self.headers, data=self.data)

                # 获取数据总页数
                sele = etree.HTML(resp)
                tt = sele.xpath(".//div[@class='list_pages']/form/span/text()")[0]
                all_num = int(re.findall(" ([0-9]+?)条", tt)[0])

                if not all_num:
                    self.logger.info(f"[{k}]关键词没有数据")
                    continue

                self.page_total = math.ceil(all_num / int(self.data["pageSize"]))

                self.process(resp)

                # 2. 开始分页
                for page_num in range(self.first_page_num + 1, self.page_total + 1):
                    self.data["pageNo"] = str(page_num)
                    resp = self.req("post", url=self.search_api, headers=self.headers, data=self.data)

                    self.process(resp)
            except Exception as e:
                self.logger.error(f"{self.name} | 出错 | {e} | 错误行号：{e.__traceback__.tb_lineno}")

        return self

    def process(self, resp):

        urls = self.clean_urls(resp)
        for title, u in urls:
            detail = self.req("get", url=u, headers=self.headers)
            release_time, origin, text = self.clean_detail(detail)

            self.add(title, release_time, origin, text, u)
            time.sleep(1)

    def clean_urls(self, resp: str):

        sele = etree.HTML(resp)

        table = sele.xpath(".//*[@class='content_table']")[0]
        a_eles = table.xpath("./tbody/tr/td[1]/a")

        urls = []

        for a in a_eles:
            title = a.xpath("./text()")[0].strip()

            if self.adopt_title_filter(title):
                continue

            link = a.xpath("./@href")[0]
            url = self.url + link
            urls.append((title, url))

        return urls

    def clean_detail(self, detail):

        doc_pattern = r"发布日期：(.+?)</span>.+?来源：(.+?)</span>"
        release_time, origin = re.findall(doc_pattern, detail, flags=re.DOTALL)[0]

        sele = etree.HTML(detail)
        src = sele.xpath(".//div[@class='page_content']/iframe/@src")[0]
        pdf_url = unquote(self.url + re.findall("file=(.+)", src)[0])

        content = self.req("get", url=pdf_url, headers=self.headers)

        text = pdf_to_text(content)

        return release_time, origin, text


class Spider9(BaseSpider):
    website = "ggzyjy.nmg.gov.cn"
    name = "内蒙古自治区公共资源交易网"
    url = "https://ggzyjy.nmg.gov.cn"
    search_api = "https://ggzyjy.nmg.gov.cn/trssearch/openSearch/searchPublishResource"
    detail_api = "https://ggzyjy.nmg.gov.cn/trssearch/openSearch/getPublishResourceDealContent?sourceDataKey={}"


    def __init__(self):
        BaseSpider.__init__(self)
        self.params = {
            "noticeName": "卫星",
            "projectCode": "",
            "bidSectionCodes": "",
            "pageSize": "10",
            "pageNum": "1",
            "noticeTypeName": "",
            "platformCode": "",
            "regionCode": "",
            "startTime": self.standard_time(self.start_time),
            "endTime": self.standard_time(self.end_time),
            "transactionTypeName": "",
            "industriesTypeName": ""
        }
        self.page_total = 0
        self.run_flag = True
        self.first_page_num = 1

    def master(self):
        for k in self.keys:
            self.params["noticeName"] = k
            self.params["pageNum"] = self.first_page_num

            # 1. 首次请求搜索接口
            resp = self.req("get", url=self.search_api, headers=self.headers, params=self.params)
            total_records = resp["data"]["total"]

            if not total_records:
                self.logger.info(f"[{k}]没有搜索结果")
                continue

            self.page_total = math.ceil(total_records / int(self.params["pageSize"]))

            self.process(resp)

            # 2. 开始分页处理（第一页已请求）
            for page_num in (self.first_page_num + 1, self.page_total + 1):
                self.params["pageNum"] = str(page_num)
                resp = self.req("get", url=self.search_api, headers=self.headers, params=self.params)

                self.process(resp)

        return self

    def process(self, resp):
        """ 将clean_urls和clean_detail、add合并 """

        urls = self.clean_urls(resp)

        for title, source_id,link in urls:
            detail_url = self.detail_api.format(source_id)
            detail_resp = self.req("get", url=detail_url, headers=self.headers)
            release_time, origin, text = self.clean_detail(detail_resp)

            self.add(title, release_time, origin, text, link)

    def clean_urls(self, resp):

        datas = resp["data"]["data"]
        urls = []
        for d in datas:
            title = d["projectName"].strip()
            if self.adopt_title_filter(title):
                continue

            sourceId = d["sourceDataKey"]

            # 拼接人工访问的链接
            link = f"https://ggzyjy.nmg.gov.cn/jyxx/index_24.html?id={sourceId}"

            urls.append([title, sourceId,link])

        return urls

    def clean_detail(self, detail):

        data = detail["data"]["dealContent"]

        release_time = data["noticeSendTime"]
        content = data["noticeContent"]

        text = element_to_text(content)

        # 由于没有来源
        origin = None

        return release_time, origin, text

    def standard_time(self, date):
        return date + " 00:00:00"


class Spider10(BaseSpider):
    website = "lntb.gov.cn"
    name = "辽宁省招标投标监管网"
    url = "https://www.lntb.gov.cn"
    search_api = "https://www.lntb.gov.cn/mhback/api/cTenderProjectNode/checkListToPublicTable"
    detail_api = "https://www.lntb.gov.cn/mhback/api/cTenderNoticeController/getDetail/{}"

    def __init__(self):
        BaseSpider.__init__(self)
        self.run_flag = True
        self.headers["content-type"] = "application/json;charset=UTF-8"
        self.data = {
            "keyword": "机器人",
            "regionLevel": "",
            "regionCode": "",
            "tradeCode": "",
            "classificationCode": "",
            "noticeType": "c_tender_notice",
            "noticeIndex": "",
            "time": self.standard_time(self.start_time),
            "creditShow": "",
            "number": 1,
            "size": 10,
            "total": 0
        }
        self.page_total = 0
        self.first_page_num = 1

    def master(self):

        for k in self.keys:
            self.data["keyword"] = k
            self.data["number"] = self.first_page_num
            data = json.dumps(self.data, separators=(',', ':'))

            # 第一次请求
            resp = self.req("post", url=self.search_api, headers=self.headers, data=data)
            total_records = resp["data"]["total"]
            if not total_records:
                self.logger.info(f"[{k}]关键词没有数据")
                continue

            self.page_total = math.ceil(total_records / int(self.data["size"]))

            self.process(resp)

            # 分页逻辑
            for page_num in range(self.first_page_num + 1, self.page_total + 1):
                self.data["number"] = page_num
                data = json.dumps(self.data, separators=(',', ':'))
                resp = self.req("post", url=self.search_api, headers=self.headers, data=data)
                self.process(resp)

        return self

    def process(self, resp):

        ids = self.clean_urls(resp)
        for title, release_time, origin, id_ in ids:
            text = self.clean_detail(id_)
            link = f"https://www.lntb.gov.cn/#/notice?id={id_}"
            self.add(title, release_time, origin, text, link)

    def clean_urls(self, resp):
        datas = resp["data"]["list"]
        ids = []
        for data in datas:
            title = data["title"].strip()
            if self.adopt_title_filter(title):
                continue
            id_ = data['id']
            tt = data["time"]
            # 2. 处理格式：fromisoformat支持 "+00:00"，需将 "+0000" 替换为 "+00:00"
            formatted_str = tt.replace("+0000", "+00:00")
            # 3. 解析为带时区的 datetime 对象
            utc_dt = datetime.datetime.fromisoformat(formatted_str)
            # 直接转为 "YYYY-MM-DD" 字符串（最常用）
            release_time = utc_dt.strftime("%Y-%m-%d")  # 结果："2025-02-11"

            # 没有来源
            origin = None

            ids.append((title, release_time, origin, id_))

        return ids

    def clean_detail(self, id_):

        u = self.detail_api.format(id_)
        resp = self.req("post", url=u, headers=self.headers)
        pdf_u = resp["data"]["attName"].replace("/home", "")

        pdf_url = f"{self.url}{pdf_u}"

        content = self.req("get", url=pdf_url, headers=self.headers)

        text = pdf_to_text(content)

        return text

    def standard_time(self, tt):
        # 获取当前日期
        current_date = datetime.date.today()
        # 将目标日期字符串转为date对象
        target_date = datetime.datetime.strptime(tt, "%Y-%m-%d").date()
        # 计算日期差值
        delta = abs(target_date - current_date)
        # 获得相差天数
        return str(delta.days)


class Spider11(BaseSpider):
    website = "ggzyzx.jl.gov.cn"
    name = "吉林省公共资源交易中心"
    url = "http://www.ggzyzx.jl.gov.cn"
    search_api = "https://haiyun.jl.gov.cn/irs/front/search"

    def __init__(self):
        BaseSpider.__init__(self)
        self.run_flag = True
        self.data = {
            "code": "1892dd01822",
            "searchWord": "人工智能",
            "orderBy": "time",
            "dataTypeId": "501",
            "searchBy": "all",
            "pageNo": 1,
            "pageSize": 10,
            "granularity": "ALL",
            "beginDateTime": "",
            "endDateTime": "",
            "isSearchForced": 0,
            "customFilter": {
                "operator": "and",
                "properties": [
                    {
                        "property": "channel_id",
                        "operator": "eq",
                        "value": "69308",
                        "weight": 100
                    }
                ]
            }
        }
        self.is_next = True  # 判断是否继续
        self.headers["Content-Type"] = "application/json"
        self.first_page_num = 1

    def master(self):
        for k in self.keys:
            self.data["searchWord"] = k
            self.data["pageNo"] = self.first_page_num

            # 1. 第一次请求
            data = json.dumps(self.data, separators=(',', ':'))
            resp = self.req("post", url=self.search_api, headers=self.headers, data=data)

            # 2. 计算总页数和当前页
            total_page = int(resp["data"]["pager"]["pageCount"])

            # 3. 判断有无数据
            if not total_page:
                self.logger.info(f"[{k}]关键词没有数据")
                continue

            self.process(resp)

            # 分页逻辑
            for page_num in range(self.first_page_num + 1, total_page + 1):
                if not self.is_next:
                    break
                self.data["pageNo"] = page_num
                data = json.dumps(self.data, separators=(',', ':'))
                resp = self.req("post", url=self.search_api, headers=self.headers, data=data)

                self.process(resp)

        return self

    def process(self, resp):

        urls = self.clean_urls(resp)
        for title, date_str, url in urls:
            detail = self.req("get", url=url, headers=self.headers)

            origin, text = self.clean_detail(detail)

            self.add(title, date_str, origin, text, url)

    def clean_urls(self, resp):

        datas = resp["data"]["middle"]["listAndBox"]
        urls = []
        for d in datas:
            data = d["data"]
            date_str = data["time"]
            release_date = datetime.datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S").date()
            start_date = datetime.datetime.strptime(self.start_time, "%Y-%m-%d").date()

            # 发布时间不小于我们设置的开始时间
            if release_date < start_date:
                self.is_next = False
                break
            title = data["title"]

            # 清洗title
            title = re.sub("<.+?>", "", title, flags=re.DOTALL).strip()

            # 筛选
            if self.adopt_title_filter(title):
                continue

            url = data["url"]
            urls.append([title, date_str, url])

        return urls

    def clean_detail(self, detail):

        sele = etree.HTML(detail)

        origin_text = etree.tostring(sele.xpath(".//div[@class='l_text']/label")[0], method="text", encoding="unicode")

        origin = re.findall("laiyuan = \'(.+?)\'", origin_text, flags=re.DOTALL)[0]

        # 正文内容的块元素
        div_ele = sele.xpath(".//div[@id='detailCnt']")[0]
        parent = div_ele.xpath("./div")[0]
        son = parent.xpath("./p[1]")[0]
        # 删除节点
        parent.remove(son)

        text_html = etree.tostring(div_ele, method="html", encoding="unicode")
        text = element_to_text(text_html)

        return origin, text


class Spider12(BaseSpider):
    name = "黑龙江公共资源交易网"
    url = "http://ggzyjyw.hlj.gov.cn"
    search_api = "https://ggzyjyw.hlj.gov.cn/inteligentsearch/rest/esinteligentsearch/getFullTextDataNew"
    website = "ggzyjyw.hlj.gov.cn"

    def __init__(self):
        BaseSpider.__init__(self)
        self.run_flag = True
        self.data = {
            "token": "",
            "pn": 0,
            "rn": 10,
            "sdt": "",
            "edt": "",
            "wd": "卫星",
            "inc_wd": "",
            "exc_wd": "",
            "fields": "title",
            "cnum": "012;013",
            "sort": "{\"webdate\":\"0\",\"id\":\"0\"}",
            "ssort": "",
            "cl": 500,
            "terminal": "",
            "condition": [],
            "time": [
                {
                    "fieldName": "webdate",
                    "startTime": self.standardize_time(self.start_time),
                    "endTime": self.standardize_time(self.end_time)
                }
            ],
            "highlights": "title;searchtitle;content",
            "statistics": None,
            "unionCondition": [],
            "accuracy": "",
            "noParticiple": "1",
            "searchRange": None,
            "noWd": True
        }
        self.first_page_num = 0

    def master(self):
        for k in self.keys:
            try:
                # 1. 初始化搜索参数
                self.data["wd"] = k
                self.data["pn"] = self.first_page_num
                # 2. 首次请求
                resp = self.req("post", url=self.search_api, headers=self.headers, data=json.dumps(self.data))

                # 3. 总页数
                total_page = math.ceil(resp["result"]["totalcount"] / self.data["rn"])
                if not total_page:
                    self.logger.info(f"[{k}] | {self.name} | 无数据 | {resp} | {self.data}")
                    continue
                self.process(resp)

                # 4. 分页逻辑
                for page_num in range(self.first_page_num + 1, total_page + 1):
                    page_num = page_num * 10

                    self.data["pn"] = page_num

                    resp = self.req("post", url=self.search_api, headers=self.headers, data=json.dumps(self.data))
                    self.process(resp)


            except Exception as e:
                self.logger.error(f"{self.name} | 出错 | {e} | 错误行号：{e.__traceback__.tb_lineno}")

        return self

    def process(self, resp):
        try:
            urls = self.clean_urls(resp)
            for title, release_date, link in urls:
                detail = self.req("get", url=link, headers=self.headers)
                origin, text = self.clean_detail(detail)

                self.add(title, release_date, origin, text, link)
        except Exception as e:
            self.logger.error(f"{self.name} | 出错 | {e} | 错误行号：{e.__traceback__.tb_lineno}")

    def clean_urls(self, resp):
        try:
            urls = []
            datas = resp["result"]["records"]
            for d in datas:
                title = d["title"].strip()
                if self.adopt_title_filter(title):
                    continue

                category_name = d["categoryname"]
                if category_name not in ["采购/预审公告", "招标/资审公告"]:
                    continue

                release_date = d["infodate"]
                link = self.url + d["linkurl"]
                urls.append([title, release_date, link])

            return urls
        except Exception as e:
            self.logger.error(f"{self.name} | 出错：{e} | 错误行号：{e.__traceback__.tb_lineno}")

    def clean_detail(self, detail):

        sele = etree.HTML(detail)
        div_content = sele.xpath(".//div[@class='ewb-art-bd']")[0]

        content_text = etree.tostring(div_content, method="html", encoding="unicode")
        text = element_to_text(content_text)
        origin = None

        return origin, text

    def standardize_time(self, time_str: str) -> str:
        return f"{time_str} 00:00:00"


class Spider13(BaseSpider):
    website = "www.jszbtb.com"
    name = "江苏省招标投标公共服务平台"
    url = "https://www.jszbtb.com"
    search_api = "https://api.jszbtb.com/DataSyncApi/HomeTenderBulletin"

    def __init__(self):
        BaseSpider.__init__(self)
        self.run_flag = True
        self.params = {
            "PageSize": "20",
            "CurrentPage": "1",
            "StartDateTime": self.standard_time(self.start_time),
            "EndDateTime": self.standard_time(self.end_time),
            "Keyword": "机器人"
        }
        self.first_page_num = 1

    def master(self):
        for k in self.keys:
            try:
                # 1. 初始化搜索参数
                self.params["Keyword"] = k
                self.params["CurrentPage"] = str(self.first_page_num)

                # 2. 首次请求
                resp = self.req("get", url=self.search_api, headers=self.headers, params=self.params)
                total_page = resp["data"]["totalPage"]
                self.process(resp)

                # 分页逻辑
                for page_num in range(self.first_page_num + 1, total_page + 1):
                    self.params["CurrentPage"] = str(page_num)
                    resp = self.req("get", url=self.search_api, headers=self.headers, params=self.params)
                    self.process(resp)
            except Exception as e:
                self.logger.error(f"{self.name} | 出错 | {e} | 错误行号：{e.__traceback__.tb_lineno}")

        return self

    def process(self, resp):

        urls = self.clean_urls(resp)
        for title, release_date, detail_url,link in urls:
            detail = self.req("get", url=detail_url, headers=self.headers)
            origin, text = self.clean_detail(detail)

            self.add(title, release_date, origin, text, link)
            time.sleep(random.randint(20,50)*0.01)

    def clean_urls(self, resp):

        urls = []
        datas = resp["data"]["data"]
        for d in datas:
            title = d["projectName"].strip()
            if self.adopt_title_filter(title):
                continue

            release_date = d["create_time"]
            id_ = d["id"]
            detail_url = "https://api.jszbtb.com/DataSyncApi/TenderBulletin/id/{}".format(id_)

            link = f"https://www.jszbtb.com/#/bulletindetail/TenderBulletin/{id_}?release={{\"release\":\"{release_date.split('T')[0]}\"}}"

            urls.append([title, release_date, detail_url,link])

        return urls

    def clean_detail(self, detail):

        data = detail["data"]["data"][0]

        content = data["bulletincontent"]

        # 解析正文
        text = element_to_text(content)

        # 获取来源
        platform_code = data["platformcode"]
        origins_link = "https://api.jszbtb.com/PlatformApi/ConnectedPlatform"
        origin_resp = self.req("get", url=origins_link, headers=self.headers)
        origins = origin_resp["datalist"]
        origin = None
        for origin_dict in origins:
            if origin_dict["platformCode"] == platform_code:
                origin = origin_dict["platformName"]
                break
        return origin, text

    def standard_time(self,tt):
        return tt+" 00:00:00"


class Spider14(BaseSpider):
    website = "ggzy.zj.gov.cn"
    name = "浙江省公共资源交易服务平台"
    url = "https://ggzy.zj.gov.cn"
    search_api = "https://ggzy.zj.gov.cn/inteligentsearch/rest/esinteligentsearch/getFullTextDataNew"

    def __init__(self):
        BaseSpider.__init__(self)
        self.run_flag = True
        self.data = {
            "token": "",
            "pn": 0,
            "rn": 12,
            "sdt": "",
            "edt": "",
            "wd": "",
            "inc_wd": "",
            "exc_wd": "",
            "fields": "title",
            "cnum": "001",
            "sort": "{\"webdate\":\"0\"}",
            "ssort": "title",
            "cl": 200,
            "terminal": "",
            "condition": [
                {
                    "fieldName": "titlenew",
                    "isLike": True,
                    "likeType": 0,
                    "equal": "卫星"
                },
                {
                    "fieldName": "categorynum",
                    "isLike": True,
                    "likeType": 2,
                    "equal": "002002001"
                },
                {
                    "fieldName": "infoc",
                    "isLike": True,
                    "likeType": 2,
                    "equal": "33"
                }
            ],
            "time": [
                {
                    "fieldName": "webdate",
                    "startTime": self.standard_time(self.start_time),
                    "endTime": self.standard_time(self.end_time)
                }
            ],
            "highlights": "",
            "statistics": None,
            "unionCondition": None,
            "accuracy": "",
            "noParticiple": "0",
            "searchRange": None,
            "isBusiness": "1"
        }
        self.first_page_num = 0

    def master(self):
        for k in self.keys:
            self.data["condition"][0]["equal"] = k
            self.data["pn"] = self.first_page_num

            data = json.dumps(self.data)
            resp = self.req("post", url=self.search_api, headers=self.headers, data=data)

            total_page = math.ceil(resp["result"]["totalcount"] / self.data["rn"])
            if not total_page:
                self.logger.info(f"[{k}] | {self.name} | 无数据")
                continue

            self.process(resp)

            # 分页
            for page_num in range(self.first_page_num + 1, total_page + 1):
                self.data["pn"] = page_num * self.data["rn"]

                data = json.dumps(self.data)
                resp = self.req("post", url=self.search_api, headers=self.headers, data=data)

                self.process(resp)

        return self

    def process(self, resp):

        urls = self.clean_urls(resp)
        for title, release_date, origin, link in urls:
            detail = self.req("get", url=link, headers=self.headers)
            text = self.clean_detail(detail)

            self.add(title, release_date, origin, text, link)

    def clean_urls(self, resp):

        urls = []
        records = resp["result"]["records"]

        for d in records:
            title = d["titlenew"].strip()
            if self.adopt_title_filter(title):
                continue

            release_date = d["infodate"]
            link = self.url + d["linkurl"]
            origin = d["infod"]
            urls.append([title, release_date, origin, link])

        return urls

    def clean_detail(self, detail):

        sele = etree.HTML(detail)
        table_content = sele.xpath(".//table")[0]

        content_text = etree.tostring(table_content, method="html", encoding="unicode")
        text = element_to_text(content_text)

        return text

    def standard_time(self,tt):
        return tt+" 00:00:00"


class Spider15(BaseSpider):
    website = "ggzyfw.fujian.gov.cn"
    name = "福建省公共资源交易电子公共服务平台"
    url = "https://ggzyfw.fujian.gov.cn"
    search_api = "https://ggzyfw.fujian.gov.cn/FwPortalApi/Trade/TradeInfo"

    def __init__(self):
        BaseSpider.__init__(self)
        self.run_flag = True
        self.data = {
            "pageNo": 1,
            "pageSize": 20,
            "total": 0,
            "AREACODE": "",
            "M_PROJECT_TYPE": "",
            "KIND": "ZFCG",
            "GGTYPE": "1",
            "PROTYPE": "D01",
            "timeType": "",
            "BeginTime": self.standard_time(self.start_time),
            "EndTime": self.standard_time(self.end_time),
            "createTime": [
                "2025-06-01 00:00:00",
                "2025-08-20 00:00:00"
            ],
            "NAME": "机器人",
            "ts": int(time.time() * 1000)
        }
        self.first_page_num = 1

    def master(self):

        for k in self.keys:

            # 1. 初始化查询参数
            self.data["NAME"] = k
            self.data["pageNo"] = self.first_page_num

            # 2. 首次查询
            headers = self.update_headers_new(self.data)
            resp = self.req("post", url=self.search_api, headers=headers, json_d=self.data)

            # 解密
            resp = self.aes_decrypt(resp)
            total_page = int(resp["PageTotal"])
            if not total_page:
                self.logger.info(f"[{k}] 没有查找到数据")
                continue

            self.process(resp)
            for page_num in range(self.first_page_num + 1, total_page + 1):
                self.data["pageNo"] = page_num
                headers = self.update_headers_new(self.data)
                resp = self.req("post", url=self.search_api, headers=headers, json_d=self.data)
                # 解密
                resp = self.aes_decrypt(resp)
                self.process(resp)

        return self

    def process(self, resp):

        urls = self.clean_urls(resp)
        detail_url = "https://ggzyfw.fujian.gov.cn/FwPortalApi/Trade/TradeInfoContent"
        for title, release_time, origin, show_detail_link, id_ in urls:
            detail_data = {
                "m_id": id_,
                "type": "PURCHASE_QUALI_INQUERY_ANN",
                "ts": int(time.time() * 1000)
            }
            headers = self.update_headers_new(detail_data)

            detail = self.req("post", url=detail_url, headers=headers, json_d=detail_data)
            text = self.clean_detail(detail)

            self.add(title, release_time, origin, text, show_detail_link)

    def clean_urls(self, resp):

        # 解析url
        urls = []
        show_detail_api = "https://ggzyfw.fujian.gov.cn/business/detail"
        datas = resp["Table"]
        for d in datas:
            title = d["NAME"].strip()
            if self.adopt_title_filter(title):
                continue

            origin = d["PLATFORM_NAME"]
            id_ = d["M_ID"]
            release_time = d["TM"]
            cid = d["PROCODE"]
            kind = d["KIND"]
            show_detail_link = f"{show_detail_api}?name={title}&cid={cid}&type={kind}"

            urls.append([title, release_time, origin, show_detail_link, id_])
        return urls

    def clean_detail(self, detail):

        content = self.aes_decrypt(detail)["Contents"]
        text = element_to_text(content)

        return text

    def get_sign(self, data):
        """ 获取签名密文 """

        def js_sort_key(t, e):
            """实现JS中的排序函数l(t, e)"""
            # 转换为字符串并大写，与JS的toString().toUpperCase()对应
            t_str = str(t).upper()
            e_str = str(e).upper()

            if t_str > e_str:
                return 1
            elif t_str == e_str:
                return 0
            else:
                return -1

        """处理对象并按照JS排序规则拼接字符串"""
        # 1. 获取字典的键并使用排序规则排序
        # 注意：Python 3的sorted使用key函数，这里用functools.cmp_to_key转换比较函数
        from functools import cmp_to_key
        keys = sorted(data.keys(), key=cmp_to_key(js_sort_key))

        # 2. 初始化结果列表
        result = []

        # 3. 遍历排序后的键
        for key in keys:
            value = data.get(key)

            # 4. 过滤None
            if not value and value != 0:
                continue

            # 5. 处理对象/数组类型
            if isinstance(value, (dict, list)):
                serialized = json.dumps(value, separators=(',', ':'))
                result.append(f"{key}{serialized}")

            # 6. 处理基本类型
            else:
                result.append(f"{key}{str(value)}")

        data = "B3978D054A72A7002063637CCDF6B2E5" + ''.join(result)

        # 4. 计算hash值
        # 创建MD5哈希对象
        md5 = hashlib.md5()
        # 确保数据是字节类型，如果是字符串则编码为UTF-8
        if isinstance(data, str):
            data = data.encode('utf-8')
        # 更新哈希对象（对应JavaScript的update(e)）
        md5.update(data)
        return md5.hexdigest()  # 返回十六进制字符串

    def update_headers_new(self, data):
        """ 新建请求头 """

        headers = {}
        headers["portal-sign"] = self.get_sign(data)

        headers.update(self.headers)
        return headers

    def aes_decrypt(self, resp, mode=AES.MODE_CBC, encoding='base64'):
        """
        AES 解密函数

        参数:
            ciphertext: 待解密的密文（字符串或字节）
            key: 密钥（字节或字符串，长度必须为16/24/32字节，对应AES-128/192/256）
            iv: 初始向量（字节或字符串，CBC等模式需要，长度必须为16字节）
            mode: 加密模式（默认CBC，可选ECB、GCM等）
            encoding: 密文编码方式（base64或hex，默认base64）

        返回:
            解密后的明文（字符串）
        """

        # 1.解密
        ciphertext = resp["Data"]
        key = "EB444973714E4A40876CE66BE45D5930"  # 16字节密钥（AES-128）
        iv = "B5A8904209931867"  # 16字节初始向量

        # 处理密钥
        if isinstance(key, str):
            key = key.encode('utf-8')
        # 验证密钥长度
        if len(key) not in [16, 24, 32]:
            raise ValueError("密钥长度必须为16、24或32字节（对应AES-128/192/256）")

        # 处理初始向量
        iv = iv.encode('utf-8')

        # 处理密文（解码）
        if isinstance(ciphertext, str):
            if encoding == 'base64':
                ciphertext = base64.b64decode(ciphertext)
            elif encoding == 'hex':
                ciphertext = bytes.fromhex(ciphertext)
            else:
                raise ValueError("编码方式必须是 'base64' 或 'hex'")

        # 创建解密器
        if mode == AES.MODE_ECB:
            # ECB模式不需要IV
            cipher = AES.new(key, mode)
        else:
            # CBC、GCM等模式需要IV
            cipher = AES.new(key, mode, iv=iv)

        # 解密（GCM模式需要额外处理tag）
        if mode == AES.MODE_GCM:
            # 假设最后16字节是tag
            tag = ciphertext[-16:]
            ciphertext = ciphertext[:-16]
            plaintext = cipher.decrypt_and_verify(ciphertext, tag)
        else:
            # 普通模式解密并去除填充
            plaintext = unpad(cipher.decrypt(ciphertext), AES.block_size)

        # 返回字符串形式的明文
        return json.loads(plaintext.decode('utf-8'))

    def standard_time(self,tt):
        return tt+ " 00:00:00"



class Spider16(BaseSpider):
    website = "www.jxsggzy.cn"
    name = "江西省公共资源交易网"
    url = "https://www.jxsggzy.cn/"
    search_api = "https://www.jxsggzy.cn/XZinterface/rest/esinteligentsearch/getFullTextDataNew"

    def __init__(self):
        BaseSpider.__init__(self)
        self.run_flag = True
        self.data = {
            "token": "",
            "pn": 10,
            "rn": 10,
            "sdt": self.start_time,
            "edt": self.end_time,
            "wd": "卫星",
            "inc_wd": "",
            "exc_wd": "",
            "fields": "title",
            "cnum": "",
            "sort": "{\"webdate\":0}",
            "ssort": "title",
            "cl": 500,
            "terminal": "",
            "condition": [
                {
                    "fieldName": "categorynum",
                    "isLike": True,
                    "likeType": 2,
                    "equal": "002"
                }
            ],
            "time": None,
            "highlights": "title;content",
            "statistics": None,
            "unionCondition": None,
            "accuracy": "",
            "noParticiple": "1",
            "searchRange": None
        }
        self.first_page_num = 0

    def master(self):
        for k in self.keys:
            self.data["wd"] = k
            self.data["pn"] = self.first_page_num

            data = json.dumps(self.data)
            resp = self.req("post", url=self.search_api, headers=self.headers, data=data)

            total_page = math.ceil(resp["result"]["totalcount"] / self.data["rn"])
            if not total_page:
                self.logger.info(f"[{k}] | {self.name} | 无数据")
                continue

            self.process(resp)

            # 分页
            for page_num in range(self.first_page_num + 1, total_page + 1):
                self.data["pn"] = page_num * self.data["rn"]

                data = json.dumps(self.data)
                resp = self.req("post", url=self.search_api, headers=self.headers, data=data)

                self.process(resp)

        return self

    def process(self, resp):

        urls = self.clean_urls(resp)
        for title, release_date, origin, link in urls:
            detail = self.req("get", url=link, headers=self.headers)
            try:
                text = self.clean_detail(detail)
            except:
                self.logger.info(link)
                raise

            self.add(title, release_date, origin, text, link)

    def clean_urls(self, resp):
        urls = []
        records = resp["result"]["records"]

        for d in records:
            title = d["titlenew"].strip()
            if self.adopt_title_filter(title):
                continue

            release_date = d["infodate"]
            link = self.url + d["linkurl"]
            origin = d["laiyuan"]
            urls.append([title, release_date, origin, link])

        return urls

    def clean_detail(self, detail):
        sele = etree.HTML(detail)
        div_content = sele.xpath(".//div[@class='text']")[0]

        content_text = etree.tostring(div_content, method="html", encoding="unicode")
        text = element_to_text(content_text)

        return text

    def is_next(self):
        pass


class Spider17(BaseSpider):
    website = "ggzyjy.shandong.gov.cn"
    name = "山东省公共资源交易网"
    url = "https://ggzyjy.shandong.gov.cn"
    search_api = "https://ggzyjy.shandong.gov.cn/queryContent_{}-jyxxgk.jspx"

    def __init__(self):
        BaseSpider.__init__(self)
        self.data = {
            "title": "卫星",
            "origin": "",
            "inDates": self.standard_time(self.start_time),
            "channelId": "151",
            "ext": ""
        }
        self.run_flag = True
        self.first_page_num = 1

    def master(self):
        for k in self.keys:
            try:
                # 搜索请求
                self.data["title"] = k
                self.search_api = self.search_api.format(self.first_page_num)
                resp = self.req("post", url=self.search_api, headers=self.headers, data=self.data)

                # 获取总页数
                sele = etree.HTML(resp)
                # 获取总页数
                page_data = sele.xpath(".//div[@class='page-list']/ul/li[1]/a/text()")[0]
                self.page_total = int(re.findall("/([0-9]+?)页", page_data)[0].strip())

                if not self.page_total:
                    self.logger.info(f"[{k}] | {self.name} | 没有数据")
                    continue

                self.process(resp)
                for page_num in range(self.first_page_num + 1, self.page_total + 1):
                    self.logger.info(f"第{page_num}页")
                    self.search_api = self.search_api.format(page_num)
                    resp = self.req("post", url=self.search_api, headers=self.headers, params=self.data)

                    self.process(resp)

            except Exception as e:
                self.logger.error(f"{self.name} | 出错 | {e} | 错误行号：{e.__traceback__.tb_lineno}")

        return self

    def process(self, resp):

        urls = self.clean_urls(resp)

        for u in urls:
            detail = self.req("get", url=u, headers=self.headers)
            title, release_time, origin, text = self.clean_detail(detail)

            self.add(title, release_time, origin, text, u)

    def clean_urls(self, resp: str) -> list:
        """ 清洗出详情页的链接 """
        try:
            urls = []
            sele = etree.HTML(resp)

            div_eles = sele.xpath(".//div[@class='article-list3-t']")
            for div in div_eles:
                title_ele, u = div.xpath("./a")[0], div.xpath("./a/@href")[0]  # 获取公告标题和未加密的链接

                title = etree.tostring(title_ele, method="text", encoding="utf8").decode("utf8").strip()

                if self.adopt_title_filter(title):
                    continue

                url = self.encrypt_url(u)
                urls.append(url)
            return urls

        except Exception as e:
            self.logger.error(f"{self.name} | 出错 | {e} | 错误行号：{e.__traceback__.tb_lineno}")

            return []

    def clean_detail(self, detail):
        """ 清洗出标准数据 """
        try:
            sele = etree.HTML(detail)

            title = sele.xpath(".//div[@class='div-title']/text()")[0].strip()
            release_time = sele.xpath("/html/body/div[4]/div[2]/div[5]/div[1]/span[1]/text()")[0]
            release_time = release_time.strip("公告发布时间：")
            origin = None

            # 然后提取正文元素
            text_ele = sele.xpath(".//table[@class='gycq-table']")[0]

            new_text = etree.tostring(text_ele, method="html", encoding="unicode")
            text = element_to_text(new_text)
            return title, release_time, origin, text
        except Exception as e:
            self.logger.error(f"{self.name} | 出错 | {e} | 错误行号：{e.__traceback__.tb_lineno} | 详细：{detail}")

            raise

    def encrypt_url(self, url: str):
        """ 返回加密后的详情页链接 """

        u_id = url.rstrip("/").split("/")[-1].replace(".jhtml", "")
        plaintext = u_id.encode()
        key = "qnbyzzwmdgghmcnm".encode()

        cipher = AES.new(key, AES.MODE_ECB)
        ciphertext = cipher.encrypt(pad(plaintext, AES.block_size))
        new_id = base64.b64encode(ciphertext).decode().strip("==").replace("/", "^")

        # 函数接收匹配对象，只替换捕获组的内容，别的内容保留
        new_url = re.sub("/(\w+?)\.jhtml", lambda m: f"/{new_id}.jhtml", url)
        return new_url

    def standard_time(self, tt: str):
        """
        规范时间，将时间转为当前网站适配的时间
        :return:
        """
        now = datetime.datetime.now().date()
        start = datetime.datetime.strptime(tt, "%Y-%m-%d").date()
        return abs((start - now).days)


class Spider18(BaseSpider):
    website = "hndzzbtb.fgw.henan.gov.cn"
    name = "河南省电子招标投标公共服务平台"
    url = "http://hndzzbtb.fgw.henan.gov.cn"
    search_api = "http://hnztbkhd.fgw.henan.gov.cn/xxfbcms/search/bulletin.html"

    def __init__(self):
        BaseSpider.__init__(self)
        self.run_flag = True
        self.params = {
            "dates": "300",
            "categoryId": "88",
            "industryName": "",
            "area": "",
            "status": "",
            "publishMedia": "",
            "sourceInfo": "",
            "showStatus": "",
            "word": "网站",
            "startcheckDate": self.start_time,
            "endcheckDate": self.end_time,
            "page": "1"
        }
        self.first_page_num = 1

    def master(self):
        for k in self.keys:
            self.params["word"] = k
            self.params["page"] = self.first_page_num

            # 首次请求
            resp = self.req("get", url=self.search_api, headers=self.headers, params=self.params)

            sele = etree.HTML(resp)
            total_page_ele = sele.xpath(".//div[@class='pagination']/label/text()")
            if not total_page_ele:
                self.logger.info(f"[{k}] | 无数据")
                continue
            total_page = int(total_page_ele[0].strip())

            self.process(resp)

            # 分页
            for page_num in range(self.first_page_num + 1, total_page + 1):
                self.logger.info(f"[{k}]，第{page_num}页")
                self.params["page"] = page_num
                resp = self.req("get", url=self.search_api, headers=self.headers, params=self.params)
                self.process(resp)

        return self

    def process(self, resp):

        urls = self.clean_urls(resp)
        for title, release_time, origin, link in urls:
            detail = self.req("get", url=link, headers=self.headers)
            text = self.clean_detail(detail)

            self.add(title, release_time, origin, text, link)

    def clean_urls(self, resp):

        sele = etree.HTML(resp)

        urls = []
        table_ele = sele.xpath(".//table[@class='table_text']")[0]
        trs = table_ele.xpath(".//tr")

        for tr in trs[1:]:
            title = tr.xpath('./td[1]/a/text()')[0].strip()
            if self.adopt_title_filter(title):
                continue
            href = tr.xpath('./td[1]/a/@href')[0]
            origin = tr.xpath('./td[4]/text()')[0]
            release_time = tr.xpath('./td[5]/text()')[0]

            link = href.replace("javascript:urlOpen(\'", "").replace("\')", '')
            urls.append([title, release_time, origin, link])
        return urls

    def clean_detail(self, detail):
        pdf_base_url = "http://222.143.32.113:8087/bulletin/getBulletin"
        sele = etree.HTML(detail)
        id_ = sele.xpath(".//div[@class='mian_list_03']/@index")[0]

        cipher_text = self.get_cipher_text()
        plain_text = self.des_decrypt(cipher_text)

        pdf_data_param = json.loads(plain_text)["data"]

        pdf_url = f"{pdf_base_url}/{pdf_data_param}/{id_}"  # 拼接pdf链接

        pdf_content = self.req("get", url=pdf_url, headers=self.headers)
        if len(pdf_content) == 0:
            self.logger.debug("错误：PDF数据为空")
            text = "pdf文件损坏"
        else:
            text = pdf_to_text(pdf_content)

        return text

    def get_cipher_text(self):
        cipher_text_url = "http://222.143.32.113:8087/permission/getSecretKey"
        return self.req("post", cipher_text_url, headers=self.headers)

    def des_decrypt(self, cipher_text):
        key = "Ctpsp@884*"[:8].encode("utf8")
        destor = DES.new(mode=DES.MODE_ECB, key=key)
        bytes_cipher = base64.b64decode(cipher_text)
        plain_text = unpad(destor.decrypt(bytes_cipher), block_size=8)
        return plain_text


class Spider19(BaseSpider):
    website = "hbggzyfwpt.cn"
    name = "湖北省公共资源交易电子服务系统"
    url = "https://www.hbggzyfwpt.cn"
    search_api = "https://www.hbggzyfwpt.cn/jyxx/zfcg/cgggNew"

    def __init__(self):
        BaseSpider.__init__(self)
        self.run_flag = True
        self.data = {
            "currentPage": "1",
            "pageSize": "10",
            "currentArea": "001",
            "area": "000",
            "publishTimeType": "4",
            "publishTimeStart": self.start_time,
            "publishTimeEnd": self.end_time,
            "bulletinTitle": "卫星",
            "purchaserMode": "99",
            "purchaserModeType": "0"
        }
        self.first_page_num = 1

    def master(self):
        for k in self.keys:
            self.data["bulletinTitle"] = k
            self.data["currentPage"] = str(self.first_page_num)

            resp = self.req("post", url=self.search_api, headers=self.headers)
            total_page = resp["pages"]
            total_data = resp["data"]
            if not total_data:
                self.logger.info(f"[{k}] | 无数据")
                continue

            self.process(resp)

            # 分页
            for page_num in range(self.first_page_num + 1, total_page + 1):
                self.logger.info(f"[{k}]，第{page_num}页")
                self.data["currentPage"] = str(page_num)
                resp = self.req("get", url=self.search_api, headers=self.headers, params=self.data)
                self.process(resp)
        return self

    def process(self, resp):
        urls = self.clean_urls(resp)

        for title, release_time, origin, content, link in urls:
            text = self.clean_detail(content)
            self.add(title, release_time, origin, text, link)

    def clean_urls(self, resp):

        datas = resp["data"]
        urls = []
        for d in datas:
            title = d["bulletinTitle"].strip()
            if self.adopt_title_filter(title):
                continue

            release_time = d["bulletinStartTime"].strip()
            origin = None

            content = d["bulletinContent"]
            guid = d["guid"]
            link = "https://www.hbggzyfwpt.cn/jyxx/zfcg/cgggDetail?guid=" + guid
            urls.append([title, release_time, origin, content, link])

        return urls

    def clean_detail(self, content):

        sele = etree.HTML(content)

        div_tit = sele.xpath("//div[1]")[0]
        div_tit.getparent().remove(div_tit)

        new_content = etree.tostring(sele, method="html", encoding="unicode")
        text = element_to_text(new_content)

        return text


class Spider20(BaseSpider):
    website = "hnsggzy.com"
    name = "湖南省公共资源交易服务平台"
    url = "https://www.hnsggzy.com/#/sy"
    search_api = "https://www.hnsggzy.com/tradeApi/governmentPurchase/projectInformation/selectAll"

    def __init__(self):
        BaseSpider.__init__(self)
        self.run_flag = True
        self.first_page_num = 1
        self.params = {
            "current": "1",
            "size": "10",
            "notice": "1",
            "noticeName": "卫星",
            "noticeSendTimeStart": self.standard_time(self.start_time),
            "noticeSendTimeEnd": self.standard_time(self.end_time),
            "descs": "noticeSendTime"
        }

    def master(self):
        for k in self.keys:
            self.params["noticeName"] = k
            self.params["current"] = str(self.first_page_num)

            resp = self.req("get", url=self.search_api, headers=self.headers, params=self.params)

            total_page = resp["data"]["pages"]
            total_records = resp["data"]["total"]
            if not total_records:
                self.logger.info(f"[{k}] | 无数据")
                continue

            self.process(resp)

            # 分页
            for page_num in range(self.first_page_num + 1, total_page + 1):
                self.params["current"] = str(page_num)
                resp = self.req("get", url=self.search_api, headers=self.headers, params=self.params)
                self.process(resp)

        return self

    def process(self, resp):

        urls = self.clean_urls(resp)
        for title, release_time, origin, id_, link in urls:
            detail_url = f"https://www.hnsggzy.com/tradeApi/governmentPurchase/projectInformation/getAnnouncementBySectionId?sectionId={id_}"

            detail = self.req("get", url=detail_url, headers=self.headers)
            self.logger.debug(link)
            text = self.clean_detail(detail)

            self.add(title, release_time, origin, text, link)

    def clean_urls(self, resp):

        datas = resp["data"]["records"]
        urls = []
        for d in datas:
            title = d["noticeName"]
            if self.adopt_title_filter(title):
                continue
            release_time = d["noticeSendTime"]
            id_ = d["bidSectionId"]
            origin = d["regionName"] + "公共资源交易中心" if d["regionName"] else None

            link = f"https://www.hnsggzy.com/#/resources/projectDetail/governmentPurchase?bidSectionId={id_}"
            urls.append([title, release_time, origin, id_, link])
        return urls

    def clean_detail(self, detail):

        content = detail["data"]["governmentProcureAnnouncementInformation"][0]["noticeContent"]
        if content:
            return element_to_text(content)
        else:
            return ""

    def standard_time(self,tt):
        return tt+" 00:00:00"


class Spider21(BaseSpider):
    website = "ygp.gdzwfw.gov.cn"
    name = "广东省公共资源交易平台"
    url = "https://ygp.gdzwfw.gov.cn/"
    search_api = "https://ygp.gdzwfw.gov.cn/ggzy-portal/search/v2/items"
    channel_ids = {"工程建设": "A", "政府采购": "D"}

    def __init__(self):
        BaseSpider.__init__(self)
        self.run_flag = True
        self.data = {
            "type": "trading-type",
            "openConvert": False,
            "keyword": "机器人",
            "siteCode": "44",
            "secondType": "A",
            "tradingProcess": "",
            "thirdType": "[]",
            "projectType": "",
            "publishStartTime": self.standard_time(self.start_time),
            "publishEndTime": self.standard_time(self.end_time),
            "pageNo": 1,
            "pageSize": 10
        }
        self.first_page_num = 1
        self.next = False  # 当一个关键词都不存在时触发下一个关键词搜索或者下一渠道，而不是继续下一页

    def master(self):
        for k in self.keys:
            for channel_name, channel in self.channel_ids.items():
                if channel_name == "政府采购":
                    self.data["tradingProcess"] = "2822,3822"
                elif channel_name == "工程建设":
                    self.data["tradingProcess"] = "503,517,3C14,3C81,2C14,2C81"

                self.next = False
                self.data["keyword"] = k
                self.data["secondType"] = channel
                self.data["pageNo"] = self.first_page_num
                headers = self.update_headers()

                data = json.dumps(self.data)
                resp = self.req("post", url=self.search_api, headers=headers, data=data)
                total_page = resp["data"]["pageTotal"]
                if not total_page:
                    self.logger.info(f"[{k}] | 无数据")
                    continue
                self.process(resp)

                # 分页
                for page_num in range(self.first_page_num + 1, total_page + 1):
                    self.logger.info(f"第{page_num}/{total_page}页 ")
                    self.data["pageNo"] = page_num
                    data = json.dumps(self.data)
                    resp = self.req("post", url=self.search_api, headers=headers, data=data)
                    self.process(resp)

                    if self.next:
                        self.logger.warn(f"[{k}] | {channel_name} | 不会再有数据了")
                        break
        return self

    def process(self, resp):
        urls = self.clean_urls(resp)

        node_url = "https://ygp.gdzwfw.gov.cn/ggzy-portal/center/apis/trading-notice/new/nodeList"
        detail_url = "https://ygp.gdzwfw.gov.cn/ggzy-portal/center/apis/trading-notice/new/detail"
        for title, date_, origin, notice_id, \
                version, project_code, site_code, \
                trading_process, project_type, channel in urls:

            # 请求详情内容接口之前的查询参数的接口
            node_params = {
                "siteCode": str(site_code),
                "tradingType": self.data["secondType"],
                "bizCode": str(trading_process),
                "projectCode": project_code,
                "classify": project_type
            }

            node_data = self.req("get", url=node_url, headers=self.headers, params=node_params)
            node_id = None  # 默认
            for i in node_data["data"]:
                if notice_id in str(i):
                    node_id = i["nodeId"]
                    break

            # 拼接详情页链接，供人工访问的
            link = f"""https://ygp.gdzwfw.gov.cn/#/44/new/jygg/v3/{channel}?noticeId={notice_id}&projectCode={project_code}&bizCode={trading_process}&siteCode={site_code}&publishDate={date_}&source={origin}&classify={project_type}&nodeId={node_id}"""

            # 请求详情内容接口
            detail_params = {
                "nodeId": str(node_id),
                "version": str(version),
                "tradingType": self.data["secondType"],
                "noticeId": str(notice_id),
                "bizCode": str(trading_process),
                "projectCode": str(project_code),
                "siteCode": str(site_code)
            }
            detail = self.req("get", url=detail_url, headers=self.headers, params=detail_params)

            text = self.clean_detail(detail)
            # 格式化时间
            dt = datetime.datetime.strptime(date_, "%Y%m%d%H%M%S")
            release_time = dt.strftime("%Y-%m-%d %H:%M:%S")
            self.add(title, release_time, origin, text, link)
            time.sleep(2)

    def clean_urls(self, resp):

        datas = resp["data"]["pageData"]
        urls = []
        for d in datas:
            title = d["noticeTitle"].strip()
            if self.adopt_title_filter(title):
                continue

            # 如果标题中一个关键词都不存在的情况
            if all(k not in title for k in self.keys):
                self.next = True
                continue

            origin = d["pubServicePlat"]
            date_ = d["publishDate"]

            notice_id = d["noticeId"]
            version = d["edition"]
            project_code = d["projectCode"]
            site_code = d["regionCode"]
            trading_process = d["tradingProcess"]
            project_type = d["projectType"]
            channel = d["noticeSecondType"]
            urls.append([title, date_, origin,
                         notice_id, version, project_code,
                         site_code, trading_process, project_type, channel])

        return urls

    def clean_detail(self, detail):

        content = detail["data"]["tradingNoticeColumnModelList"][1]["richtext"]
        text = element_to_text(content)
        return text

    def standard_time(self, tt):
        date_ = datetime.datetime.strptime(tt, "%Y-%m-%d")
        return date_.strftime("%Y%m%d%H%M%S")

    def update_headers(self):
        headers = {}
        headers["Content-Type"] = "application/json"
        headers.update(self.headers)

        return headers


class Spider22(BaseSpider):
    website = "gxggzy.gxzf.gov.cn"
    name = "广西壮族自治区公共资源交易服务平台"
    url = "http://gxggzy.gxzf.gov.cn"
    search_api = "http://gxggzy.gxzf.gov.cn/irs/front/search"

    def __init__(self):
        BaseSpider.__init__(self)
        self.run_flag = True
        self.data = {
            "code": "181aedab55d",
            "beginDateTime": self.standard_time(self.start_time),
            "endDateTime": self.standard_time(self.end_time),
            "dataTypeId": "18547",
            "configCode": "",
            "searchWord": "卫星",
            "orderBy": "related",
            "searchBy": "title",
            "appendixType": "",
            "granularity": "ALL",
            "isSearchForced": "0",
            "filters": [],
            "pageNo": 1,
            "pageSize": 10,
            "isAdvancedSearch": None,
            "isDefaultAdvanced": None,
            "advancedFilters": None,
            "historySearchWords": [
            ]
        }
        self.first_page_num = 1

    def master(self):
        for k in self.keys:
            self.data["searchWord"] = k
            self.data["pageNo"] = self.first_page_num

            headers = self.update_headers()
            data = json.dumps(self.data)
            resp = self.req("post", url=self.search_api, headers=headers, data=data)

            total_records = resp["data"]["pager"]["total"]
            total_page = math.ceil(total_records / self.data["pageSize"])

            if not total_page:
                self.logger.info(f"[{k}] | 无数据")
                continue

            self.process(resp)

        return self

    def process(self, resp):

        urls = self.clean_urls(resp)
        for title, release_time, origin, link in urls:
            detail = self.req("get", url=link, headers=self.headers)

            text = self.clean_detail(detail)

            self.add(title, release_time, origin, text, link)

    def clean_urls(self, resp):

        urls = []
        datas = resp["data"]["middle"]["listAndBox"]
        for d in datas:
            title = d["data"]["title_no_tag"]
            if self.adopt_title_filter(title):
                continue

            link = d["data"]["url"]
            origin = d["data"]["source"]
            release_time = d["data"]["time"]

            urls.append([title, release_time, origin, link])

        return urls

    def clean_detail(self, detail):

        sele = etree.HTML(detail)
        content_ele = sele.xpath(".//div[@class='ewb-page-line']/div[3]")[0]
        content = etree.tostring(content_ele, method="html", encoding="unicode")

        return element_to_text(content)

    def update_headers(self):
        headers = {}
        headers["Content-Type"] = "application/json"

        headers.update(self.headers)

        return headers

    def standard_time(self, tt):

        dt = datetime.datetime.strptime(tt, "%Y-%m-%d")
        return int(dt.timestamp() * 1000)


class Spider23(BaseSpider):
    website = "ggzy.hainan.gov.cn"
    name = "海南省公共资源交易服务平台"
    url = "https://ggzy.hainan.gov.cn"
    search_api = "https://ggzy.hainan.gov.cn/inteligentsearch/rest/esinteligentsearch/getFullTextDataNew"

    def __init__(self):
        BaseSpider.__init__(self)
        self.run_flag = True
        self.data = {
            "token": "",
            "pn": 0,
            "rn": 10,
            "sdt": "",
            "edt": "",
            "wd": "%20",
            "inc_wd": "",
            "exc_wd": "",
            "fields": "title",
            "cnum": "001",
            "sort": "{\"webdate\":\"0\"}",
            "ssort": "title",
            "cl": 200,
            "terminal": "",
            "condition": [
                {
                    "fieldName": "titlenew",
                    "equal": "卫星",
                    "notEqual": None,
                    "equalList": None,
                    "notEqualList": None,
                    "isLike": True,
                    "likeType": 0
                },
                {
                    "fieldName": "categorynum",
                    "equal": "003001002",
                    "notEqual": None,
                    "equalList": None,
                    "notEqualList": None,
                    "isLike": True,
                    "likeType": 2
                }
            ],
            "time": [
                {
                    "fieldName": "webdate",
                    "startTime": self.standard_time(self.start_time),
                    "endTime": self.standard_time(self.end_time)
                }
            ],
            "highlights": "title",
            "statistics": None,
            "unionCondition": None,
            "accuracy": "",
            "noParticiple": "1",
            "searchRange": [],
            "isBusiness": "1"
        }
        self.first_page_num = 0
        self.channel_data = {
            "工程建设": "003001002",
            "政府采购": "003002002"
        }

    def master(self):
        for k in self.keys:
            for channel_name, channel_id in self.channel_data.items():

                self.data["condition"][0]["equal"] = k
                self.data["pn"] = self.first_page_num
                self.data["condition"][1]["equal"] = channel_id

                data = json.dumps(self.data)
                resp = self.req("post", url=self.search_api, headers=self.headers, data=data)

                total_page = math.ceil(resp["result"]["totalcount"] / self.data["rn"])
                if not total_page:
                    self.logger.info(f"[{k}] | {self.name} | 无数据")
                    continue

                self.process(resp)

                # 分页
                for page_num in range(self.first_page_num + 1, total_page + 1):
                    self.data["pn"] = page_num * self.data["rn"]

                    data = json.dumps(self.data)
                    resp = self.req("post", url=self.search_api, headers=self.headers, data=data)

                    self.process(resp)

        return self

    def process(self, resp):

        urls = self.clean_urls(resp)
        for title, release_date, origin, link in urls:
            detail = self.req("get", url=link, headers=self.headers)
            try:
                text = self.clean_detail(detail)
            except:
                self.logger.info(link)
                raise

            self.add(title, release_date, origin, text, link)

    def clean_urls(self, resp):
        urls = []
        records = resp["result"]["records"]

        for d in records:
            title = d["titlenew"].strip()
            if self.adopt_title_filter(title):
                continue

            release_date = d["infodate"]
            link = self.url + d["linkurl"]
            origin = d["zhuanzai"]
            urls.append([title, release_date, origin, link])

        return urls

    def clean_detail(self, detail):
        sele = etree.HTML(detail)
        div_content = sele.xpath(".//div[@class='article-info jyxx-info']")[0]

        # # 注意：XPath索引从1开始，[position() <=4]表示前4个
        # children = div_content.xpath("./child::*[position() <= 4]")
        # for child in children:
        #     div_content.remove(child)

        content_text = etree.tostring(div_content, method="html", encoding="unicode")
        text = element_to_text(content_text)

        return text

    def standard_time(self, tt):

        return tt + " 00:00:00"

class Spider47(BaseSpider):
    website = "yaggzy.org.cn"
    name = "雅安市公共资源交易平台"
    url = "https://www.yaggzy.org.cn"
    search_api = {
        "建设工程": "https://www.yaggzy.org.cn/jyxx/jsgcZbgg",
        "政府采购": "https://www.yaggzy.org.cn/jyxx/zfcg/cggg"
    }

    def __init__(self):
        BaseSpider.__init__(self)
        self.run_flag = True
        self.params = {
            "建设工程": {
                "area": "001",
                "isYiFaZhaoBiao": "1"
            },
            "政府采购": {
                "area": "001"
            }
        }
        self.data = {
            "建设工程": {
                "currentPage": "1",
                "secondArea": "000",
                "industriesTypeCode": 000,
                "bulletinTitle": "办公"
            },
            "政府采购": {"currentPage": "1",
                         "secondArea": "000",
                         "bulletinTitle": "办公"}
        }

        self.first_page_num = 1
        self.is_next = True

    def master(self):
        for chanel, search_api in self.search_api.items():
            for k in self.keys:
                self.data["bulletinTitle"] = k
                self.data["currentPage"] = str(self.first_page_num)

                resp = self.req("post", url=search_api, headers=self.headers, params=self.params[chanel],
                                data=self.data[chanel])
                # 获取总页数
                total_page = self.get_total_page(resp)
                if not total_page:
                    self.logger.info(f"[{k}] | 无数据")

                self.process(resp)

                # 分页
                for page_num in range(self.first_page_num + 1, total_page + 1):
                    if not self.is_next:
                        break

                    self.data["currentPage"] = str(page_num)
                    resp = self.req("post", url=search_api, headers=self.headers, params=self.params[chanel],
                                    data=self.data[chanel])
                    self.process(resp)

        return self

    def process(self, resp):

        urls = self.clean_urls(resp)
        for tit, link in urls:

            detail = self.req("get", url=link, headers=self.headers)
            res = self.clean_detail(detail)
            if res == "停":
                break
            release_time, text, origin = res

            self.add(tit, release_time, origin, text, link)

    def clean_urls(self, resp):

        sele = etree.HTML(resp)
        urls = []
        li_eles = sele.xpath(".//li[@class='clearfloat']/table/tr")[1:]
        for li in li_eles:
            tit = li.xpath("./td[3]/a/text()")[0].strip()
            if self.adopt_title_filter(tit):
                continue

            status = li.xpath("./td[last()]/text()")[0]
            if status == "已结束":
                continue

            link = self.url + li.xpath("./td[3]/a/@href")[0]

            urls.append([tit, link])

        return urls

    def clean_detail(self, detail):
        sele = etree.HTML(detail)
        time_ele = sele.xpath(".//div[@class='time']/text()")[0]

        release_time = re.findall("[0-9]{4}-[0-9]{2}-[0-9]{2}", time_ele)[0]

        if self.time_fileter(release_time):
            self.is_next = False
            return "停"

        content_ele = sele.xpath(".//*[@class='nr']")[0]
        content = etree.tostring(content_ele, method="html", encoding="unicode")
        text = element_to_text(content)
        origin = None

        return release_time, text, origin

    def time_fileter(self, release_time):

        release_time = datetime.datetime.strptime(release_time, "%Y-%m-%d")
        start_time = datetime.datetime.strptime(self.start_time, "%Y-%m-%d")

        if release_time < start_time:
            return True
        return False

    def get_total_page(self, resp):

        sele = etree.HTML(resp)
        total_page = sele.cssselect("div.mmggxlh > a")[-2].text

        li_eles = sele.xpath(".//li[@class='clearfloat']/table/tr")[1:]
        # 如果第一页没有数据，说明总页数为0
        if not li_eles:
            return 0
        return int(total_page.strip())


class Spider48(BaseSpider):
    website = "msggzy.org.cn"
    name = "眉山市政务服务和公共资源交易服务中心"
    url = "https://www.msggzy.org.cn/front"
    search_api = "https://www.msggzy.org.cn/EWB-FRONT/rest/GgSearchAction/getInfoMationList"

    def __init__(self):
        BaseSpider.__init__(self)
        self.run_flag = True
        self.is_next = True  # 判断是否继续请求，遇到时间比开始时间还久远的就不再继续
        self.params = {
            "siteGuid": "7eb5f7f1-9041-43ad-8e13-8fcb82ea831a",
            "categoryNum": "",
            "kw": "办公",
            "pageIndex": 3,
            "pageSize": 20
        }
        self.first_page_num = 0

    def master(self):
        for k in self.keys:
            self.params["kw"] = k
            self.params["pageIndex"] = self.first_page_num

            data = {"params": json.dumps(self.params, separators=(",", ":"))}
            resp = self.req("post", url=self.search_api, headers=self.headers, data=data)
            total_page = math.ceil(resp["AllCount"] / self.params["pageSize"])

            if not total_page:
                self.logger.info(f"[{k}] | 无数据")
                continue

            self.process(resp)

            for page_num in range(self.first_page_num + 1, total_page + 1):
                if not self.is_next:
                    break

                self.params["pageIndex"] = page_num
                data = {"params": json.dumps(self.params, separators=(",", ":"))}
                resp = self.req("post", url=self.search_api, headers=self.headers, data=data)
                self.process(resp)

        return self

    def process(self, resp):
        urls = self.clean_urls(resp)

        for title, release_time, origin, link in urls:
            detail = self.req("get", url=link, headers=self.headers)
            text = self.clean_detail(detail)

            self.add(title, release_time, origin, text, link)

    def clean_urls(self, resp):
        datas = resp["custom"]
        urls = []
        for d in datas:
            title = d["title"]
            if self.adopt_title_filter(title):
                continue

            origin = d["zhuanzai"]

            release_time = d["infodate"]
            if self.time_fileter(release_time):
                self.is_next = False
                break  # 遇到时间比较久的直接跳出循环，因为后面的时间更久远

            link = "https://www.msggzy.org.cn/front" + d["infourl"]
            urls.append([title, release_time, origin, link])
        return urls

    def clean_detail(self, detail):

        sele = etree.HTML(detail)
        content_ele = sele.xpath(".//div[@class='the-content']/div[2]")[0]
        content = etree.tostring(content_ele, method="html", encoding="unicode")

        text = element_to_text(content)
        return text

    def time_fileter(self, release_time):

        release_time = datetime.datetime.strptime(release_time, "%Y-%m-%d")
        start_time = datetime.datetime.strptime(self.start_time, "%Y-%m-%d")

        if release_time < start_time:
            return True
        return False


class Spider49(BaseSpider):
    website = "b2b.10086.cn"
    name = "中国移动采购与招标网"
    url = "https://b2b.10086.cn"
    search_api = "https://b2b.10086.cn/api-b2b/api-sync-es/white_list_api/b2b/publish/queryList"

    def __init__(self):
        BaseSpider.__init__(self)
        self.run_flag = True
        self.first_page_num = 1
        self.data = {
            "name": "办公",
            "publishType": "PROCUREMENT",
            "purchaseType": "",
            "companyType": "",
            "size": 20,
            "current": 1,
            "creationDateStart": self.start_time,
            "creationDateEnd": self.end_time,
            "sfactApplColumn5": "PC"
        }

    def master(self):
        for k in self.keys:
            self.data["name"] = k
            self.data["current"] = self.first_page_num

            headers = self.update_headers()
            data = json.dumps(self.data)
            resp = self.req("post", url=self.search_api, headers=headers, data=data)

            # 获取总页数
            total_page = math.ceil(resp["data"]["totalElements"] / self.data["size"])

            if not total_page:
                self.logger.info(f"[{k}] | 无数据")
                continue

            self.process(resp)

            # 分页
            for page_num in range(self.first_page_num + 1, total_page + 1):
                self.data["current"] = page_num
                data = json.dumps(self.data)
                resp = self.req("post", url=self.search_api, headers=headers, data=data)
                self.process(resp)

        return self

    def process(self, resp):
        urls = self.clean_urls(resp)

        for id_, uuid_, title, publish_type, publish_one_type, release_time in urls:
            # 拼接人工访问的详情链接
            link = f"https://b2b.10086.cn/#/noticeDetail?publishId={id_}&publishUuid={uuid_}&publishType={publish_type}&publishOneType={publish_one_type}"

            # 详情接口
            detail_url = "https://b2b.10086.cn/api-b2b/api-sync-es/white_list_api/b2b/publish/queryDetail"
            detail_data = {
                "publishId": id_,
                "publishUuid": uuid_,
                "publishType": publish_type,
                "sfactApplColumn5": "PC"
            }

            data = json.dumps(detail_data)
            headers = self.update_headers()
            detail = self.req("post", url=detail_url, headers=headers, data=data)
            text = self.clean_detail(detail)
            origin = None

            self.add(title, release_time, origin, text, link)

    def clean_urls(self, resp):

        datas = resp["data"]["content"]
        urls = []
        for d in datas:
            title = d["name"]
            if self.adopt_title_filter(title):
                continue

            id_ = d["id"]
            uuid_ = d["uuid"]
            publish_type = d["publishType"]
            publish_one_type = d["publishOneType"]
            release_time = d["backDate"]

            urls.append([id_, uuid_, title, publish_type, publish_one_type, release_time])

        return urls

    def clean_detail(self, detail):
        b64_content = detail["data"]["noticeContent"]
        content = base64.b64decode(b64_content)
        text = pdf_to_text(content)
        return text

    def update_headers(self):
        headers = {}

        headers.update(self.headers)
        headers["Content-Type"] = "application/json"

        return headers


class Spider51(BaseSpider):
    website = "caigou.chinatelecom.com.cn"
    name = "中国电信阳光采购网"
    url = "https://caigou.chinatelecom.com.cn"
    search_api = "https://caigou.chinatelecom.com.cn/portal/base/announcementJoin/queryListNew"

    def __init__(self):
        BaseSpider.__init__(self)
        self.run_flag = True
        self.data = {
            "pageNum": 2,
            "pageSize": 10,
            "title": "卫星",
            "queryStartTime": "2025-06-01",
            "provinceCode": "",
            "queryEndTime": "2025-08-20",
            "noticeSummary": "",
            "type": "e2no"  # 表示查询招标公告
        }
        self.first_page_num = 1

    def master(self):
        for k in self.keys:
            self.data["title"] = k
            self.data["pageNum"] = self.first_page_num

            headers = self.update_headers()
            data = json.dumps(self.data)
            resp = self.req("post", url=self.search_api, headers=headers, data=data)
            total_page = self.gain_total_page(resp)
            if not total_page:
                self.logger.info(f"[{k}] | 无数据")

            self.process(resp)

            # 分页
            for page_num in range(self.first_page_num + 1, total_page + 1):
                self.logger.info(f"第{page_num}页")
                self.data["pageNum"] = page_num
                data = json.dumps(self.data)
                resp = self.req("post", url=self.search_api, headers=headers, data=data)
                self.process(resp)

        return self

    def process(self, resp):

        urls = self.clean_urls(resp)
        for title, release_time, id_, doc_type, view_code in urls:
            headers = self.update_headers()
            link = ("https://caigou.chinatelecom.com.cn/DeclareDetails?"
                    f"id={id_}&"
                    "type=1&"
                    f"docTypeCode={doc_type}&"
                    f"securityViewCode={view_code}")

            detail_url = "https://caigou.chinatelecom.com.cn/portal/base/tenderannouncement/view"
            detail_form = {
                "type": doc_type,
                "id": id_,
                "securityViewCode": view_code
            }

            detail_form = json.dumps(detail_form)
            detail = self.req("post", url=detail_url, headers=headers, data=detail_form)
            origin = None

            text = self.clean_detail(detail)
            self.add(title, release_time, origin, text, link)

    def clean_urls(self, resp):

        datas = resp["data"]["pageInfo"]["list"]
        urls = []
        for d in datas:
            title = d["docTitle"]
            if self.adopt_title_filter(title):
                continue
            if d["docType"] == "采购结果":
                continue

            release_time = d["createDate"]
            id_ = d["docId"]
            doc_type = d["docTypeCode"]
            view_code = d["securityViewCode"]
            urls.append([title, release_time, id_, doc_type, view_code])
        return urls

    def clean_detail(self, detail):

        content = detail["data"]["context"]
        text = element_to_text(content)
        return text

    def update_headers(self):

        headers = {}
        headers["content-type"] = "application/json;charset=UTF-8"

        headers.update(self.headers)

        return headers

    def gain_total_page(self, resp):
        total_records = resp["data"]["pageInfo"]["total"]

        return math.ceil(int(total_records) / int(self.data["pageNum"]))


if __name__ == '__main__':
    s = Spider3()
    s.master()
