# development time: 2025-08-26  8:44
# developer: 元英

from Purchase.spiders.draft_base_spider import BaseSpider
import re
from lxml import etree
from Purchase.util.tool import element_to_text,pdf_to_text
from Purchase.setting import *

class Spider3(BaseSpider):
    # 1. 定义网站元信息（类属性，固定格式）
    website = "ggzy.gov.cn/"
    name = "全国公共资源交易平台"
    base_url = "https://www.ggzy.gov.cn"
    search_api = "https://deal.ggzy.gov.cn/ds/deal/dealList_find.jsp"

    # 2. 实现抽象方法1：准备搜索参数（网站特有data结构）
    def _prepare_search_data(self) -> dict:
        return {
            "TIMEBEGIN_SHOW": self.start_time,
            "TIMEEND_SHOW": self.end_time,
            "TIMEBEGIN": self.start_time,
            "TIMEEND": self.end_time,
            "SOURCE_TYPE": "1",  # 默认数据源，后续会被_update_search_data覆盖
            "DEAL_TIME": "06",
            "DEAL_CLASSIFY": "00",
            "DEAL_STAGE": "0100",  # 该网站特有参数
            "DEAL_PROVINCE": "0",
            "DEAL_CITY": "0",
            "DEAL_PLATFORM": "0",
            "BID_PLATFORM": "0",
            "DEAL_TRADE": "0",
            "isShowAll": "1",
            "PAGENUMBER": "1",  # 分页参数名（该网站用PAGENUMBER）
            "FINDTXT": ""  # 关键词参数名（该网站用FINDTXT）
        }

    # 3. 实现抽象方法2：提取总页数
    def _extract_total_page(self, resp: dict) -> int:
        return int(resp.get("data", {}).get("ttlpage", 0))

    # 4. 实现抽象方法3：解析列表页（该网站resp["data"]是列表数据）
    def _parse_list_page(self, resp: dict) -> list[dict]:
        list_items = []
        try:
            datas = resp.get("data", [])
            for d in datas:
                list_items.append({
                    "title": d.get("title", ""),
                    "release_time": "",  # 列表页无时间，详情页提取（先占位）
                    "detail_url": d.get("url", ""),
                    "origin": self.name  # 来源默认网站名
                })
        except Exception as e:
            self.logger.error(f"列表页解析失败：{e} | 响应数据：{resp}", exc_info=True)
        return list_items

    # 5. 实现抽象方法4：解析详情页（该网站正文在id=mycontent的div）
    def _parse_detail_page(self, detail_html: str, title: str) -> str:
        try:
            # 提取标题、时间、来源（详情页补充列表页缺失的时间）
            doc_pattern = r"class=\"h4_o\">(.+?)</h4>.+?(?:发布|签署)时间：(.+?)</span>.+?platformName\">(.+?)</label>"
            res = re.findall(doc_pattern, detail_html, re.DOTALL)
            if res:
                _, release_time, origin = res[0]
                # 更新当前数据的时间和来源（通过闭包或实例变量，此处简化为直接用）
                self.current_release_time = release_time  # 临时存储时间，add时使用
                self.current_origin = origin

            # 清洗正文
            detail_html = re.sub("<style.*?>.*</style>", "", detail_html, flags=re.DOTALL)
            doc_sele = etree.HTML(detail_html)
            content_div = doc_sele.xpath(".//div[@id='mycontent']")[0]
            content_html = etree.tostring(content_div, method="html", encoding="unicode")
            return element_to_text(content_html)
        except Exception as e:
            self.logger.error(f"详情页解析失败：{e} | 标题：{title}", exc_info=True)
            return ""

    # 6. 覆盖钩子方法1：数据源类型（该网站需遍历[1,2]）
    def _get_source_types(self) -> list:
        return [1, 2]

    # 7. 覆盖钩子方法2：处理详情页URL（该网站需替换/a/为/b/、http转https）
    def _process_detail_url(self, raw_url: str) -> str:
        return raw_url.replace("/a/", "/b/").replace("http:", "https:")

    # 8. 覆盖钩子方法3：更新搜索参数（补充该网站特有参数）
    def _update_search_data(self, keyword: str, source_type: int = None) -> None:
        super()._update_search_data(keyword, source_type)  # 调用父类通用逻辑
        # 补充该网站特有参数（如有需要）
        if source_type is not None:
            self.search_data["SOURCE_TYPE"] = str(source_type)

    # 9. 覆盖add方法：补充详情页提取的时间和来源（列表页无时间时）
    def add(self, title: str, date: str, origin: str, content: str, link: str) -> None:
        # 用详情页提取的时间和来源替换列表页的空值
        final_date = self.current_release_time if hasattr(self, "current_release_time") else date
        final_origin = self.current_origin if hasattr(self, "current_origin") else origin
        super().add(title, final_date, final_origin, content, link)  # 调用父类add


spider = Spider3(START_TIME,END_TIME,KEYS,FILTER_TITLE,FILTER_CONTENT)
spider.master()
spider.save()