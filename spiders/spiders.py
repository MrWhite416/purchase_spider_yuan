# development time: 2025-08-20  16:01
# developer: 元英
import datetime
import json
import sys
import time
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad  # pkcs7填充
import base64
from lxml import etree
import re
import math
from urllib.parse import urlencode, unquote
import traceback  # 堆栈库

from Purchase.spiders.base_spider import BaseSpider
from Purchase.util.tool import element_to_text,pdf_to_text
from Purchase.util.verification_code import ocr_code


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
            "start_time": "2025:08:13",  # 开始时间
            "end_time": "2025:08:20",  # 结束时间
            "timeType": "6",  # 指定时间
            "displayZone": "",
            "zoneId": "",
            "pppStatus": "0",
            "agentName": ""
        }
        self.run_flag = False

    def master(self):
        return self
        pass

    def clean(self, resp):
        pass

    def is_next(self):
        """ 判断是否有下一页 """


class Spider2(BaseSpider):
    website = "bulletin.cebpubservice.com"
    name = "中国招标投标公共服务平台"
    url = "https://bulletin.cebpubservice.com"
    search_api = ""

    def __init__(self):
        BaseSpider.__init__(self)
        self.run_flag = False

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
            "DEAL_CLASSIFY": "00",
            "DEAL_STAGE": "0100",  # 业务及信息类型（不限业务的交易公告 0100）
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
        self.run_flag = False

    def master(self):
        try:
            for k in self.keys:  # 遍历关键词
                for i in [1, 2]:  # 遍历数据源

                    try:
                        self.data["SOURCE_TYPE"] = str(i)
                        self.data["FINDTXT"] = k

                        # 第一次请求搜索接口
                        resp = self.req("post", url=self.search_api, headers=self.headers, data=self.data)

                        # 获取总页数和当前页
                        self.total_page = resp["data"]["ttlpage"]
                        # 如果总页数为0
                        if not self.total_page:
                            self.logger.info(f"[{k}]没有搜索结果")
                            continue
                        current_page = int(self.data["PAGENUMBER"])

                        self.process(resp)

                        # 分页逻辑
                        for page_num in range(current_page+1, self.total_page+1):
                            self.data["PAGENUMBER"] = int(page_num)

                            resp = self.req("post", url=self.search_api, headers=self.headers, data=self.data)
                            self.process(resp)

                    except Exception as e:
                        self.logger.error(f"出错：{e}",exc_info=True)

            return self

        except Exception as e:
            self.logger.error(f"主函数出错：{e}",exc_info=True)
            return self

    def process(self,resp):
        urls = self.clean_url(resp)

        for t, u in urls:
            b_u = u.replace("/a/", "/b/").replace("http:", "https:")
            source = self.req("get", url=b_u, headers=self.headers)

            res = self.clean_detail(source, t)
            if not res:
                continue
            title, release_date, origin, text = res
            link = b_u
            self.add(title, release_date, origin, text, link, self.name)

    def clean_url(self, data: dict):
        try:
            datas = data["data"]

            urls = []
            for d in datas:
                title = d["title"]

                if self.adopt_title_filter(title):
                    continue  # 过滤掉存在过滤词的url
                urls.append((title, d["url"]))

            return urls
        except Exception as e:
            self.logger.error(f"错误信息：{e} | 错误数据：{data}",exc_info=True)

    def clean_detail(self, source: str, tit):
        doc_pattern = r"class=\"h4_o\">(.+?)</h4>.+?(?:发布|签署)时间：(.+?)</span>.+?platformName\">(.+?)</label>"  # 提取标题，时间，来源。

        if any(k in source for k in self.filter_content):
            self.logger.info(f"{tit}--被过滤，网站：{self.name}")
            return None
        res = re.findall(doc_pattern, source, re.DOTALL)

        if not res:
            print(source)
            self.logger.error("匹配失败",exc_info=True)
            return None

        else:
            title, release_date, origin = res[0]
            self.logger.info(f"{title},{release_date},{origin}")

        # 清洗正文
        source = re.sub("<style.*?>.*</style>", "", source, flags=re.DOTALL)  # 删除css标签及内容
        doc_sele = etree.HTML(source)

        content = doc_sele.xpath(".//div[@id='mycontent']")[0]
        n_t = etree.tostring(content,method="html",encoding="unicode")
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
        self.run_flag = False

    def master(self):

        for k in self.keys:
            try:
                self.params["title"] = k
                self.params["verifyCode"] = self.code
                self.params["_t"] = str(int(time.time() * 1000))

                search_result = self.req("get", url=self.search_api, headers=self.headers, params=self.params)

                total = search_result["data"]["total"]
                if not total:
                    self.logger.info(f"[{k}]没有数据")
                    continue

                # 计算总页数和当前页
                self.page_total = math.ceil(total / int(self.params["pageSize"]))
                current_page=int(self.params["currPage"])

                self.process(search_result)

                # 分页逻辑
                for page_num in range(current_page+1,self.page_total+1):
                    self.params["currPage"] = page_num
                    search_result = self.req("get", url=self.search_api, headers=self.headers,
                                             params=self.params)
                    self.process(search_result)


            except Exception as e:
                self.logger.error(f"出错：{e}",exc_info=True)

        return self



    def process(self,resp):

        urls = self.clean_url(resp)

        for t, u in urls:
            detail_data = self.req("get", url=u, headers=self.headers)
            time.sleep(2.5)
            res = self.clean_detail(detail_data, t)
            if not res:
                continue
            title, release_date, origin, content = res

            self.add(title, release_date, origin, content, u, self.name)

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
            datas = search_result["data"]["rows"]
            urls = []
            if not datas:
                return None

            for d in datas:
                title = d["title"]
                if self.adopt_title_filter(title):
                    self.logger.info(f"{title}--被过滤，网站：{self.name}")
                    continue

                # 拼接详情内容url
                params = {"site": d["site"], "planId": d["planId"], "_t": 1755826448587}
                encode_params = urlencode(params)
                url = self.detail_api + "?" + encode_params
                urls.append((title, url))
            return urls
        except Exception as e:
            self.logger.error(f"链接清洗函数出错：{e}",exc_info=True)
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
                self.logger.info(f"{tit},{release_date},{origin}")
                return tit, release_date, origin, content
        except Exception as e:
            self.logger.error(f"详情内容清洗出错：{e}",exc_info=True)

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
        self.run_flag = False
        self.page_total = 0

    def master(self):
        for k in self.keys:
            self.data["searchword"] = k

            try:
                resp = self.req("post", url=self.search_api, headers=self.headers, data=self.data)

                # 计算总页数
                total_records = resp["total"]
                if not total_records:
                    continue

                self.page_total = math.ceil(total_records / resp["size"])
                current_page = int(self.data["page"])

                self.process(resp)

                # 开始分页
                for page_num in range(current_page+1,self.page_total+1):
                    self.data["page"] = str(page_num)

                    resp = self.req("post", url=self.search_api, headers=self.headers, data=self.data)
                    self.process(resp)

            except Exception as e:
                self.logger.error(f'出错：{e}',exc_info=True)



        return self

    def process(self,resp):

        urls = self.clean_url(resp)

        for title, release_time, u, origin in urls:
            content = self.req("get", url=u, headers=self.headers)
            text = self.clean_detail(content)
            self.add(title, release_time, origin, text, u, self.name)
            self.logger.info(f"{title} | {release_time} | {origin}")

    def clean_url(self, resp: dict):
        """ 解析出所有url """

        urls = []
        datas = json.loads(resp["result"])
        for d in datas:
            tit = d["title"]
            title = re.sub("</?b.*?>", "", tit, flags=re.DOTALL)
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
        n_t = etree.tostring(ele,method="html",encoding="unicode")
        text = element_to_text(n_t)
        self.logger.info(text)
        return text

    def is_next(self):
        pass


class Spider6(BaseSpider):
    website = "ggzy.zwfwb.tj.gov.cn"
    name = "天津市公共资源交易网"
    url = "http://ggzy.zwfwb.tj.gov.cn"
    search_api = "http://ggzy.zwfwb.tj.gov.cn/queryContent_{}-jyxx.jspx"
    channel_ids = {
        "政府采购权": "76",
        "工程建设": "75",
        "土地使用权": "237",
        "国有产权": "78",
        "农村产权": "255",
        "矿业权交易": "247",
        "二类疫苗": "303",
        "药品采购": "240",
        "碳排放权": "308",
        "排污权": "311",
        "林权交易": "266",
        "知识产权": "314",
        "用水权": "368",
        "其他": "243",
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
        self.run_flag = False


    def master(self):
        for channel_id in self.channel_ids.values():
            for k in self.keys:
                try:
                    # 搜索请求
                    self.params["title"] = k
                    self.params["channelId"] = channel_id
                    current_page = 1
                    self.search_api = self.search_api.format(current_page)
                    resp = self.req("get", url=self.search_api, headers=self.headers, params=self.params)

                    # 获取总页数
                    sele = etree.HTML(resp)
                    # 获取总页数
                    page_data = sele.xpath(".//div[@class='page-list']/ul/li[1]/a/text()")[0]
                    self.page_total = int(re.findall("/([0-9]+?)页", page_data)[0].strip())

                    if not self.page_total:
                        continue

                    self.process(resp)
                    for page_num in range(current_page+1,self.page_total+1):
                        self.search_api = self.search_api.format(page_num)
                        resp = self.req("get", url=self.search_api, headers=self.headers, params=self.params)

                        self.process(resp)

                except Exception as e:
                    self.logger.error(f"出错：{e}",exc_info=True)

        return self

    def process(self,resp):

        urls = self.clean_urls(resp)


        for u in urls:
            detail = self.req("get", url=u, headers=self.headers)
            title, release_time, origin, text = self.clean_detail(detail)

            self.add(title, release_time, origin, text, u, self.name)
            self.logger.info(f"{title}, {release_time}, {origin}")



    def clean_urls(self, resp: str) -> list:
        """ 清洗出详情页的链接 """

        urls = []
        sele = etree.HTML(resp)


        div_eles = sele.xpath(".//div[@class='article-list3-t']")
        for div in div_eles:
            title_ele, u = div.xpath("./a")[0], div.xpath("./a/@url")[0]  # 获取公告标题和未加密的链接

            title = etree.tostring(title_ele, method="text", encoding="utf8").decode("utf8")

            if any(k in title for k in self.filter_title):
                self.logger.info(f"{title}--已被过滤")
                continue

            url = self.encrypt_url(u)
            urls.append(url)

        return urls

    def clean_detail(self, detail):
        """ 清洗出标准数据 """

        sele = etree.HTML(detail)
        content_ele = sele.xpath(".//div[@id='content']")[1]

        try:
            title = content_ele.xpath("./table/tbody/tr/td/div/p[1]/font/b/text()")[0]
            release_time, origin = content_ele.xpath("./table/tbody/tr/td/div/p[2]/font/text()")[0].split("    ")
            release_time = release_time.strip("发布日期：")
            origin = origin.strip("发布来源：")

            # 删除标题元素和发布时间以及来源元素
            es = content_ele.xpath("./table/tbody/tr/td/div/p[position()>0 and position()<3]")
            for e in es:
                # 获取当前p元素的父节点（即div）
                parent = e.getparent()
                # 通过父节点删除当前p元素
                if parent is not None:  # 确保父节点存在
                    parent.remove(e)

            # 然后提取正文元素
            text_ele = content_ele.xpath("./table/tbody/tr/td/div")[0]
            new_text= etree.tostring(text_ele,method="html",encoding="unicode")
            text = element_to_text(new_text)
            return title, release_time, origin, text
        except Exception as e:
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
        self.logger.info(new_url + f"| id: {u_id}  new_id: {new_id}")
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
        self.run_flag = False
        self.page_total = 0

    def master(self):
        # for k in self.keys:
        for k in ["办公"]:
            self.data["KeyStr"] = k

            try:
                # 1. 首次请求
                search_result = self.req("post", url=self.search_api, headers=self.headers, data=self.data)

                # 2. 解析分页信息，计算总页数，获取当前页
                page_size = search_result["t"].get("pagesize",10)
                total_records = search_result["t"].get("zbggrecords", 0)

                # 判断有无数据
                if not total_records:
                    self.logger.info(f"[{k}]关键词没有数据")
                    continue

                self.page_total = math.ceil(total_records / page_size) if page_size != 0 else 0
                current_page = int(self.data["page"])

                self.process(search_result)

                for page_num in range(current_page+1,self.page_total+1):
                    self.data["page"] = str(page_num)
                    search_result = self.req("post", url=self.search_api, headers=self.headers, data=self.data)
                    self.process(search_result)



            except Exception as e:
                self.logger.error(
                    f"关键词[{k}]第{self.data['page']}页处理失败: {str(e)}",
                    exc_info=True  # 记录完整堆栈，便于调试
                )


        return self

    def process(self,resp):

        info_ids = self.clean_url(resp)

        # 循环处理详情页
        for title, release_time, origin, info_id in info_ids:
            self.detail_params["infoid"] = info_id
            # 拼接出详情页的url
            link = f"{self.detail_api}?{urlencode(self.detail_params)}"

            detail = self.req("post", url=link, headers=self.headers)

            # 清洗出正文，添加结果
            text = self.clean_detail(detail)
            self.add(title, release_time, origin, text, link, self.name)
            self.logger.info(f"{title} | {release_time} | {origin} | {self.name}")

    def clean_url(self, data: dict):

        infos = data["t"]["search_ZbGg"]
        info_ids = []
        for i in infos:
            title = i["bulletinname"]

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

        new_html = etree.tostring(parent_ele,method="html",encoding="unicode")
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
        self.run_flag = False
        self.page_total = 0

    def master(self):
        # for k in self.keys:
        for k in ["办公"]:
            self.data["searchContent"] = k

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
                current_page = self.data["pageNo"]

                self.process(resp)

                # 2. 开始分页
                for page_num in range(current_page+1,self.page_total+1):
                    self.data["pageNo"] = str(page_num)
                    resp = self.req("post", url=self.search_api, headers=self.headers, data=self.data)

                    self.process(resp)
            except Exception as e:
                self.logger.error(f"出错：{e},{e.__traceback__.tb_lineno}",exc_info=True)

        return self

    def process(self,resp):

        urls = self.clean_urls(resp)
        for title, u in urls:
            detail = self.req("get", url=u, headers=self.headers)
            release_time, origin, text = self.clean_detail(detail)

            self.add(title, release_time, origin, text, u, self.name)
            time.sleep(1)
            self.logger.info(f"{title} | {release_time} | {origin} | {self.name}")


    def clean_urls(self, resp: str):

        sele = etree.HTML(resp)

        table = sele.xpath(".//*[@class='content_table']")[0]
        a_eles = table.xpath("./tbody/tr/td[1]/a")

        urls = []

        for a in a_eles:
            title = a.xpath("./text()")[0]

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

        content = self.req("get",url=pdf_url,headers=self.headers)

        text = pdf_to_text(content)


        return release_time, origin,text


class Spider9(BaseSpider):
    website = "ggzyjy.nmg.gov.cn"
    name = "内蒙古自治区公共资源交易网"
    url = "https://ggzyjy.nmg.gov.cn"
    search_api = "https://ggzyjy.nmg.gov.cn/trssearch/openSearch/searchPublishResource"
    detail_api = "https://ggzyjy.nmg.gov.cn/trssearch/openSearch/getPublishResourceDealContent?sourceDataKey={}"

    describe = ""

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
        self.run_flag=False

    def master(self):
        for k in self.keys:
            self.params["noticeName"] = k
            current_page = int(self.params["pageNum"])
            # 1. 首次请求搜索接口
            resp = self.req("get",url=self.search_api,headers=self.headers,params=self.params)
            total_records = resp["data"]["total"]

            if not total_records:
                self.logger.info(f"[{k}]没有搜索结果")
                continue

            self.page_total = math.ceil(total_records / int(self.params["pageSize"]))

            self.process(resp)

            # 2. 开始分页处理（第一页已请求）
            for page_num in (current_page+1,self.page_total+1):
                self.params["pageNum"] = str(page_num)
                resp = self.req("get", url=self.search_api, headers=self.headers,params=self.params)

                self.process(resp)


        return self


    def process(self,resp):
        """ 将clean_urls和clean_detail、add合并 """

        urls = self.clean_urls(resp)

        for title, source_id in urls:
            detail_url = self.detail_api.format(source_id)
            detail_resp = self.req("get", url=detail_url, headers=self.headers)
            release_time, origin, text = self.clean_detail(detail_resp)

            self.add(title,release_time,origin,text,detail_url,self.name)
            self.logger.info(f"{title} | {release_time} | {origin} | {self.name}")



    def clean_urls(self,resp):

        datas = resp["data"]["data"]
        urls = []
        for d in datas:
            title = d["projectName"]
            if self.adopt_title_filter(title):
                continue

            sourceId = d["sourceDataKey"]
            urls.append([title,sourceId])

        return urls

    def clean_detail(self,detail):

        data = detail["data"]["dealContent"]

        release_time = data["noticeSendTime"]
        content = data["noticeContent"]

        text = element_to_text(content)

        # 由于没有来源
        origin= None

        return release_time,origin,text



    def standard_time(self,date):
        return date+ " 00:00:00"


class Spider10(BaseSpider):
    website = "lntb.gov.cn"
    name = "辽宁省招标投标监管网"
    url = "https://www.lntb.gov.cn"
    search_api = "https://www.lntb.gov.cn/mhback/api/cTenderProjectNode/checkListToPublicTable"
    detail_api = "https://www.lntb.gov.cn/mhback/api/cTenderNoticeController/getDetail/{}"

    def __init__(self):
        BaseSpider.__init__(self)
        self.run_flag = False
        self.headers["content-type"]= "application/json;charset=UTF-8"
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

    def master(self):

        for k in self.keys:
            self.data["keyword"] = k
            data = json.dumps(self.data, separators=(',', ':'))

            # 第一次请求
            resp = self.req("post",url=self.search_api,headers=self.headers,data=data)
            total_records = resp["data"]["total"]
            if not total_records:
                self.logger.info(f"[{k}]关键词没有数据")
                continue

            self.page_total = math.ceil(total_records / int(self.data["size"]))
            current_page = self.data["number"]

            self.process(resp)

            # 分页逻辑
            for page_num in range(current_page+1,self.page_total+1):
                self.data["number"] = page_num
                data = json.dumps(self.data, separators=(',', ':'))
                resp = self.req("post", url=self.search_api, headers=self.headers, data=data)
                self.process(resp)

        return self

    def process(self,resp):

        ids = self.clean_urls(resp)
        for title,release_time,origin,id_ in ids:
            text=self.clean_detail(id_)
            link = f"https://www.lntb.gov.cn/#/notice?id={id_}"
            self.add(title,release_time,origin,text,link,self.name)

    def clean_urls(self,resp):
        datas = resp["data"]["list"]
        ids= []
        for data in datas:
            title = data["title"]
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

            ids.append((title,release_time,origin,id_))

        return ids

    def clean_detail(self,id_):

        u = self.detail_api.format(id_)
        resp = self.req("post",url=u,headers=self.headers)
        pdf_u = resp["data"]["attName"].replace("/home","")

        pdf_url = f"{self.url}{pdf_u}"

        content = self.req("get",url=pdf_url,headers=self.headers)

        text = pdf_to_text(content)

        return text



    def standard_time(self,tt):
        # 获取当前日期
        current_date = datetime.date.today()
        # 将目标日期字符串转为date对象
        target_date = datetime.datetime.strptime(tt, "%Y-%m-%d").date()
        # 计算日期差值
        delta = abs(target_date - current_date)
        # 获得相差天数
        return str(delta.days)



    def is_next(self):
        pass


class Spider11(BaseSpider):
    website = "ggzyzx.jl.gov.cn"
    name = "吉林省公共资源交易中心"
    url = "http://www.ggzyzx.jl.gov.cn"
    search_api = "https://haiyun.jl.gov.cn/irs/front/search"

    def __init__(self):
        BaseSpider.__init__(self)
        self.run_flag = False
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
        self.headers["Content-Type"] = "application/json"


    def master(self):
        for k in self.keys:
            self.data["searchWord"] = k

            # 1. 第一次请求
            data = json.dumps(self.data, separators=(',', ':'))
            resp = self.req("post",url=self.search_api,headers=self.headers,data=data)

            # 2. 计算总页数和当前页
            total_page = int(resp["data"]["pager"]["pageCount"])
            current_page = self.data["pageNo"]

            # 3. 判断有无数据
            if not total_page:
                self.logger.info(f"[{k}]关键词没有数据")
                continue

            self.process(resp)

            # 分页逻辑
            for page_num in range(current_page+1,total_page+1):

                self.data["pageNo"] = page_num
                data = json.dumps(self.data, separators=(',', ':'))
                resp = self.req("post", url=self.search_api, headers=self.headers, data=data)

                self.process(resp)

        return self

    def process(self,resp):

        urls = self.clean_urls(resp)
        for title,date_str,url in urls:
            detail = self.req("get",url=url,headers=self.headers)

            origin,text= self.clean_detail(detail)

            self.add(title, date_str, origin, text, url, self.name)

    def clean_urls(self,resp):

        datas = resp["data"]["middle"]["listAndBox"]
        urls = []
        for d in datas:
            data = d["data"]
            date_str = data["time"]
            release_date = datetime.datetime.strptime(date_str,"%Y-%m-%d %H:%M:%S").date()
            start_date = datetime.datetime.strptime(self.start_time,"%Y-%m-%d").date()

            # 发布时间不小于我们设置的开始时间
            if release_date>start_date:
                title = data["title"]

                # 清洗title
                title = re.sub("<.+?>","",title,flags=re.DOTALL)

                # 筛选
                if self.adopt_title_filter(title):
                    continue

                url = data["url"]
                urls.append([title,date_str,url])

        return urls

    def clean_detail(self,detail):

        sele = etree.HTML(detail)


        origin_text = etree.tostring(sele.xpath(".//div[@class='l_text']/label")[0],method="text",encoding="unicode")


        origin = re.findall("laiyuan = \'(.+?)\'",origin_text,flags=re.DOTALL)[0]

        # 正文内容的块元素
        div_ele = sele.xpath(".//div[@id='detailCnt']")[0]
        parent = div_ele.xpath("./div")[0]
        son = parent.xpath("./p[1]")[0]
        # 删除节点
        parent.remove(son)

        text_html = etree.tostring(div_ele,method="html",encoding="unicode")
        text = element_to_text(text_html)

        return origin,text


class Spider12(BaseSpider):
    website = "ggzyjyw.hlj.gov.cn"
    name = "黑龙江公共资源交易网"
    url = "http://ggzyjyw.hlj.gov.cn"
    search_api = ""

    def __init__(self):
        BaseSpider.__init__(self)
        self.run_flag = True

    def master(self):
        return self
        pass

    def clean(self):
        pass

    def is_next(self):
        pass


class Spider13(BaseSpider):
    website = "www.jszbtb.com"
    name = "江苏省招标投标公共服务平台"
    url = "https://www.jszbtb.com/?tt_force_outside=1#/newindex"
    search_api = ""

    def __init__(self):
        BaseSpider.__init__(self)
        self.run_flag = False

    def master(self):
        return self
        pass

    def clean(self):
        pass

    def is_next(self):
        pass


class Spider14(BaseSpider):
    website = "ggzy.zj.gov.cn"
    name = "浙江省公共资源交易服务平台"
    url = "https://ggzy.zj.gov.cn"
    search_api = ""

    def __init__(self):
        BaseSpider.__init__(self)
        self.run_flag = False

    def master(self):
        return self
        pass

    def clean(self):
        pass

    def is_next(self):
        pass


class Spider15(BaseSpider):
    website = "ggzyfw.fujian.gov.cn"
    name = "福建省公共资源交易电子公共服务平台"
    url = "https://ggzyfw.fujian.gov.cn"
    search_api = ""

    def __init__(self):
        BaseSpider.__init__(self)
        self.run_flag = False

    def master(self):
        return self
        pass

    def clean(self):
        pass

    def is_next(self):
        pass


class Spider16(BaseSpider):
    website = "www.jxsggzy.cn"
    name = "江西省公共资源交易网"
    url = "https://www.jxsggzy.cn/"
    search_api = ""

    def __init__(self):
        BaseSpider.__init__(self)
        self.run_flag = False

    def master(self):
        return self
        pass

    def clean(self):
        pass

    def is_next(self):
        pass


class Spider17(BaseSpider):
    website = ""
    name = ""
    url = ""
    search_api = ""

    def __init__(self):
        BaseSpider.__init__(self)
        self.run_flag = False

    def master(self):
        return self
        pass

    def clean(self):
        pass

    def is_next(self):
        pass


class Spider18(BaseSpider):
    website = ""
    name = ""
    url = ""
    search_api = ""

    def __init__(self):
        BaseSpider.__init__(self)
        self.run_flag = False

    def master(self):
        return self

    def clean(self):
        pass

    def is_next(self):
        pass


class Spider19(BaseSpider):
    website = ""
    name = ""
    url = ""
    search_api = ""

    def __init__(self):
        BaseSpider.__init__(self)
        self.run_flag = False

    def master(self):
        return self

    def clean(self):
        pass

    def is_next(self):
        pass


class Spider20(BaseSpider):
    website = ""
    name = ""
    url = ""
    search_api = ""

    def __init__(self):
        BaseSpider.__init__(self)
        self.run_flag = False

    def master(self):
        return self

    def clean(self):
        pass

    def is_next(self):
        pass


if __name__ == '__main__':
    s = Spider3()
    s.master()
