import json
import re
import math

from copy import deepcopy

import parsel

# from loguru import logger
from util.log import logger
from tqdm import tqdm
import pandas as pd

from spiders.demo_crawler import Crawler
from spiders.main_parse import ContentParser, deep_clean_text, ProcurementAnnouncement,get_sub_parts,ocr_content
from spiders.SM2_encrypt import AccurateSM2Crypto
from spiders.DES_encrypt import decrypt_by_des, str_key
import random

import concurrent.futures
from concurrent.futures import ThreadPoolExecutor, as_completed
import queue

import time
from datetime import datetime
from setting import KEYS,START_TIME,END_TIME

KeyWords = KEYS
content_parser = ContentParser()


def get_now_time():
    return int(time.time() * 1000)


class Spider24:
    def __init__(self, thread_num=3):
        """
        eg:
            start_time='2025-05-23'
            end_time='2025-08-20'
        """
        self.start_time = START_TIME
        self.end_time = END_TIME
        self.key_words = KeyWords
        self.thread_num = thread_num

        self.crawler = Crawler(crawler_type='requests')

        self.detail_requests_queue = queue.Queue()
        self.other_page_requests_queue = queue.Queue()
        self.details_queue = queue.Queue()

        self.domain_name = 'https://ggzyjyjgj.cq.gov.cn'
        self.website_name = '重庆市公共资源交易网'
        self.fields = {
            'website_name': '',
            'url': '',
            'title': '',
            'publish_time': '',
            'source': '',
            'content': ''
        }
        self.df = None

    def master(self):
        def get_detail_requests_from_detail_list_res(detail_list_res):
            for detail in detail_list_res['result']['records']:
                """
                TODO:
                    是否记录列表页请求结果
                """
                self.detail_requests_queue.put({
                    'url': self.domain_name + detail['linkurl'],
                    'requests_type': 'get',
                })

        def key_word_search(key_word):
            url = 'https://ggzyjyjgj.cq.gov.cn/inteligentsearch1/rest/esinteligentsearch/getFullTextDataNew'
            post_json = {
                "token": "",
                "pn": 0,
                "rn": 15,
                "sdt": "", "edt": "",
                "wd": key_word,
                "inc_wd": "", "exc_wd": "", "fields": "title", "cnum": "010", "sort": "{\"webdate\":0}",
                "ssort": "title", "cl": 500, "terminal": "",
                "condition": [{"fieldName": "categorynum", "equal": "002007", "notEqual": None, "equalList": None,
                               "notEqualList": None, "isLike": True, "likeType": "2"}],
                "time": [
                    {
                        "fieldName": "webdate",
                        "startTime": f"{self.start_time} 00:00:00",
                        "endTime": f"{self.end_time} 23:59:59"
                    }
                ],
                "highlights": "title", "statistics": None, "unionCondition": None, "accuracy": "",
                "noParticiple": "0", "searchRange": None
            }
            res = self.crawler.get_response(
                url=url,
                requests_type='post',
                judgement=[],
                post_json=post_json
            )
            json_res = json.loads(res)

            get_detail_requests_from_detail_list_res(json_res)

            total_count = int(json_res['result']['totalcount'])
            each_page_num = 15
            if total_count > each_page_num:
                for page_num in range(1, math.ceil(total_count / each_page_num) + 1):
                    new_post_json = deepcopy(post_json)
                    new_post_json.update({
                        'pn': page_num * each_page_num
                    })
                    self.other_page_requests_queue.put({
                        'url': url,
                        'requests_type': 'post',
                        'judgement': [],
                        'post_json': new_post_json
                    })

        def other_pages_requests(item):
            res = self.crawler.get_response(
                url=item['url'],
                requests_type=item['requests_type'],
                judgement=item['judgement'],
                post_json=item['post_json']
            )
            json_res = json.loads(res)

            get_detail_requests_from_detail_list_res(json_res)

        def detail_requests(item):
            res = self.crawler.get_response(
                url=item['url'],
                requests_type=item['requests_type']
            )
            selector = parsel.Selector(res)
            content = content_parser.replace_p_tag(
                html_content=selector.xpath('//*[@class="ewb-article-info news_content"]').get()
            )
            publish_time = content_parser.normalize_xpath(selector, '//*[@class="ewb-article-sources"]')
            publish_time = re.findall(r'\d{4}-\d{2}-\d{2}', publish_time, flags=re.S)
            publish_time = publish_time[0] if publish_time else ''

            data_out = {
                '标题': content_parser.normalize_xpath(selector, '//h3'),
                '时间': publish_time,
                '来源': '',
                '链接': item['url'],
                '所在网站': self.website_name,
                '正文': content,

            }
            self.details_queue.put(data_out)

        # 启动线程池，根据关键字搜索
        logger.info('开始根据关键字搜索。。。')
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.thread_num) as executor:
            futures = []
            for s in self.key_words:
                future = executor.submit(key_word_search, s)
                futures.append(future)

            # 等待所有任务完成
            concurrent.futures.wait(futures)

        # 启动线程池，分页请求
        logger.info(f'开始请求分页，total: {self.other_page_requests_queue.qsize()}')
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.thread_num) as executor:
            futures = []
            while True:
                try:
                    s = self.other_page_requests_queue.get_nowait()
                    future = executor.submit(other_pages_requests, s)
                    futures.append(future)
                except queue.Empty:
                    break
            # 等待所有任务完成
            concurrent.futures.wait(futures)

        # 启动线程池，详情页请求清洗
        logger.info(f'开始请求详情页，total: {self.detail_requests_queue.qsize()}')
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.thread_num) as executor:
            futures = []
            duplicate_detail_list = []
            while True:
                try:
                    s = self.detail_requests_queue.get_nowait()
                    if s['url'] not in duplicate_detail_list:
                        future = executor.submit(detail_requests, s)
                        futures.append(future)
                        duplicate_detail_list.append(s['url'])
                except queue.Empty:
                    break
            # 等待所有任务完成
            concurrent.futures.wait(futures)

        logger.info('开始导出数据。。。')
        datas_list = []
        while True:
            try:
                datas_list.append(self.details_queue.get_nowait())
            except queue.Empty:
                break

        self.df = pd.DataFrame(datas_list)
        return self


class Spider25:
    def __init__(self, thread_num=3):
        """
        eg:
            start_time='2025-05-23'
            end_time='2025-08-20'
        """
        self.start_time = START_TIME
        self.end_time = END_TIME
        self.key_words = KeyWords
        self.thread_num = thread_num

        self.crawler = Crawler(crawler_type='requests')

        self.detail_requests_queue = queue.Queue()
        self.other_page_requests_queue = queue.Queue()
        self.details_queue = queue.Queue()

        self.domain_name = 'https://ggzy.guizhou.gov.cn'
        self.website_name = '贵州省公共资源交易网'
        self.fields = {
            'website_name': '',
            'url': '',
            'title': '',
            'publish_time': '',
            'source': '',
            'content': ''
        }
        self.df = None

    def master(self):
        def get_detail_requests_from_detail_list_res(detail_list_res):
            for detail in detail_list_res['list']:
                """
                TODO:
                    是否记录列表页请求结果
                """
                if detail.get('tenderProjectCode'):
                    self.detail_requests_queue.put({
                        'url': r'https://ggzy.guizhou.gov.cn/tradeInfo/detailHtmlData?code={}&type={}'.format(
                            detail['tenderProjectCode'], detail['announcement']
                        ),
                        'requests_type': 'api_get',
                    })
                else:
                    self.detail_requests_queue.put({
                        'url': detail['apiUrl'],
                        'requests_type': 'get',
                    })

        def key_word_search(channel_id, announcement, key_word):
            url = 'https://ggzy.guizhou.gov.cn/tradeInfo/es/list'
            post_json = {
                "channelId": channel_id,
                "pageNum": 1,
                "pageSize": 20,
                "announcement": announcement,
                "startTime": f"{self.start_time} 00:00:00",
                "endTime": f"{self.end_time} 23:59:59",
                "docTitle": key_word
            }
            res = self.crawler.get_response(
                url=url,
                requests_type='post',
                judgement=[],
                post_json=post_json
            )
            json_res = json.loads(res)

            get_detail_requests_from_detail_list_res(json_res)

            total_count = int(json_res['total'])
            each_page_num = 20
            if total_count > each_page_num:
                for page_num in range(2, math.ceil(total_count / each_page_num) + 1):
                    new_post_json = deepcopy(post_json)
                    new_post_json.update({
                        'pageNum': page_num,
                        'isPage': True
                    })
                    self.other_page_requests_queue.put({
                        'url': url,
                        'requests_type': 'post',
                        'judgement': [],
                        'post_json': new_post_json
                    })

        def other_pages_requests(item):
            res = self.crawler.get_response(
                url=item['url'],
                requests_type=item['requests_type'],
                judgement=item['judgement'],
                post_json=item['post_json']
            )
            json_res = json.loads(res)

            get_detail_requests_from_detail_list_res(json_res)

        def detail_requests(item):
            res = self.crawler.get_response(
                url=item['url'],
                requests_type='get',
                judgement=[]
            )
            if item['requests_type'] == 'api_get':
                json_res = json.loads(res)['data'][0]
                html_content = json_res['docHtmlCon']
                selector = parsel.Selector(html_content)

                content = content_parser.replace_p_tag(
                    html_content=selector.xpath('.').get()
                )
                # TODO: 正文后的PDF链接是否需要保存

                data_out = {
                    '标题': json_res['docTitle'].strip(),
                    '时间': json_res['docRelTime'].strip(),
                    '来源': json_res['docSourceName'].strip(),
                    '链接': fr"https://ggzy.guizhou.gov.cn/tradeInfo/detailHtml?metaId={json_res['metaDataId']}",
                    '所在网站': self.website_name,
                    '正文': content,

                }
            else:
                selector = parsel.Selector(res)
                content = content_parser.replace_p_tag(
                    html_content=selector.xpath('//*[@class="steps"]').get()
                )
                # TODO: 正文后的PDF链接是否需要保存

                data_out = {
                    '标题': content_parser.normalize_xpath(selector, '//h3'),  # json_res['docTitle'].strip(),
                    '时间': content_parser.normalize_xpath(selector, '//*[@class="fbrq"]'),
                    # json_res['docRelTime'].strip(),
                    '来源': content_parser.normalize_xpath(selector, '//*[@id="ly"]'),
                    # json_res['docSourceName'].strip(),
                    '链接': item['url'],
                    '所在网站': self.website_name,
                    '正文': content,

                }

            self.details_queue.put(data_out)

        # 启动线程池，根据模块、关键字搜索
        logger.info('开始根据关键字搜索。。。')
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.thread_num) as executor:
            futures = []
            channel_list = [
                {
                    'channel_name': '工程建设',
                    'channel_id': '5904475',
                    'announcement': '交易公告'
                },
                {
                    'channel_name': '政府采购',
                    'channel_id': '5904543',
                    'announcement': '采购公告'
                },
                {
                    'channel_name': '其他交易',
                    'channel_id': '5904479',
                    'announcement': '交易公告'
                }
            ]
            for search_args in [list(s.values()) for s in channel_list]:
                for s in self.key_words:
                    future = executor.submit(key_word_search, search_args[1], search_args[2], s)
                    futures.append(future)

            # 等待所有任务完成
            concurrent.futures.wait(futures)

        # 启动线程池，分页请求
        logger.info(f'开始请求分页，total: {self.other_page_requests_queue.qsize()}')
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.thread_num) as executor:
            futures = []
            while True:
                try:
                    s = self.other_page_requests_queue.get_nowait()
                    future = executor.submit(other_pages_requests, s)
                    futures.append(future)
                except queue.Empty:
                    break
            # 等待所有任务完成
            concurrent.futures.wait(futures)

        # 启动线程池，详情页请求清洗
        logger.info(f'开始请求详情页，total: {self.detail_requests_queue.qsize()}')
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.thread_num) as executor:
            futures = []
            duplicate_detail_list = []
            while True:
                try:
                    s = self.detail_requests_queue.get_nowait()
                    if s['url'] not in duplicate_detail_list:
                        future = executor.submit(detail_requests, s)
                        futures.append(future)
                        duplicate_detail_list.append(s['url'])
                except queue.Empty:
                    break
            # 等待所有任务完成
            concurrent.futures.wait(futures)

        logger.info('开始导出数据。。。')
        datas_list = []
        while True:
            try:
                datas_list.append(self.details_queue.get_nowait())
            except queue.Empty:
                break
        self.df = pd.DataFrame(datas_list)
        return self


class Spider26:
    def __init__(self, thread_num=3):
        """
        eg:
            start_time='2025-05-23'
            end_time='2025-08-20'
        """
        self.start_time = self.normalize_date(START_TIME)
        self.end_time = self.normalize_date(END_TIME)
        self.key_words = KeyWords
        self.thread_num = thread_num

        self.crawler = Crawler(crawler_type='requests')

        self.detail_requests_queue = queue.Queue()
        self.other_page_requests_queue = queue.Queue()
        self.details_queue = queue.Queue()

        self.domain_name = 'https://ggzy.yn.gov.cn/homePage'
        self.website_name = '云南省公共资源交易信息网'
        self.fields = {
            'website_name': '',
            'url': '',
            'title': '',
            'publish_time': '',
            'source': '',
            'content': ''
        }
        self.df = None

    @staticmethod
    def normalize_date(date_str):
        try:
            try:
                date_str = re.findall(r'\d{8}', date_str)[0]
            except:
                date_str = re.findall(r'(\d{4})\D+(\d{2})\D+(\d{2})', date_str)[0]
                date_str = ''.join(date_str)
            # logger.info('格式正确')
            # logger.info(date_str)
        except Exception as e:
            logger.exception(f'日期输入错误：{date_str}\n{e}')
        return date_str

    def master(self):
        def get_detail_requests_from_detail_list_res(detail_list_res, item):
            for detail in detail_list_res['value']['list']:
                """
                TODO:
                    是否记录列表页请求结果
                """
                self.detail_requests_queue.put({
                    'url': item['detail_api'].format(detail['guid']),
                    'requests_type': 'get',
                    'item': item
                })

        def key_word_search(key_word, item):
            url = f"https://ggzy.yn.gov.cn/ynggfwpt-home-api{item.get('search_api')}"
            post_json = {
                "pageNum": 1,
                "pageSize": 50,
                "cityId": "",
                "title": key_word,
                "startTime": f"{self.start_time}000000",
                "endTime": f"{self.end_time}235959"
            }
            post_json.update(item.get('post_json'))
            res = self.crawler.get_response(
                url=url,
                requests_type='post',
                judgement=[],
                post_json=post_json
            )
            json_res = json.loads(res)

            get_detail_requests_from_detail_list_res(json_res, item)

            total_count = int(json_res['value']['total'])
            each_page_num = 50
            if total_count > each_page_num:
                for page_num in range(2, math.ceil(total_count / each_page_num) + 1):
                    new_post_json = deepcopy(post_json)
                    new_post_json.update({
                        'pageNum': page_num
                    })
                    self.other_page_requests_queue.put({
                        'url': url,
                        'requests_type': 'post',
                        'judgement': [],
                        'post_json': new_post_json,
                        'item': item
                    })

        def other_pages_requests(item):
            res = self.crawler.get_response(
                url=item['url'],
                requests_type=item['requests_type'],
                judgement=item['judgement'],
                post_json=item['post_json']
            )
            json_res = json.loads(res)

            get_detail_requests_from_detail_list_res(json_res, item.get('item'))

        def detail_requests(item):
            res = self.crawler.get_response(
                url=item['url'],
                requests_type=item['requests_type'],
                judgement=[]
            )
            json_res = json.loads(res)['value']
            html_content = json_res[item['item'].get('html_content_field')]
            selector = parsel.Selector(html_content)

            content = content_parser.replace_p_tag(
                html_content=selector.xpath('.').get()
            )
            # TODO: 正文后的PDF链接是否需要保存

            source = ''
            source_field = item['item'].get('source_field')
            if source_field and json_res[source_field].strip() == '政府采购网':
                source = '云南省政府采购网'

            data_out = {
                '标题': json_res[item['item'].get('title_field')].strip(),
                '时间': json_res[item['item'].get('publish_time_field')].strip(),
                '来源': source,
                '链接': item['item'].get('detail_url').format(json_res['guid']),
                '所在网站': self.website_name,
                '正文': content,

            }

            self.details_queue.put(data_out)

        # 启动线程池，根据模块、关键字搜索
        logger.info('开始根据关键字搜索。。。')
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.thread_num) as executor:
            futures = []
            channel_list = [
                {
                    'channel_name': '工程建设',
                    'search_api': '/jyzyCenter/jyInfo/gcjs/getZbggList',
                    'detail_api': 'https://ggzy.yn.gov.cn/ynggfwpt-home-api/jyzyCenter/jyInfo/gcjs/findZbggByGuid?guid={}',
                    'post_json': {
                        "industryCode": "",
                        "childType": "",
                        "tradeType": "gcjs",
                    },
                    'title_field': 'bulletinname',
                    'publish_time_field': 'bulletinissuetime',
                    'bulletin_end_time': 'bulletinendtime',
                    # 'source_field': 'bulletinmedia',
                    'html_content_field': 'bulletincontent',
                    'detail_url': 'https://ggzy.yn.gov.cn/tradeHall/tradeDetail?guid={}&colCode=1&rowCode=招标公告'
                },
                {
                    'channel_name': '政府采购-公共资源交易平台',
                    'search_api': '/jyInfo/zfcg/getCgggList',
                    'detail_api': 'https://ggzy.yn.gov.cn/ynggfwpt-home-api/jyInfo/zfcg/findCgggByGuid?guid={}',
                    'post_json': {
                        "industryCode": "",
                        "childType": ""
                    },
                    'title_field': 'bulletintitle',
                    'publish_time_field': 'bulletinstarttime',
                    'bulletin_end_time': 'bulletinendtime',
                    # 'source_field': 'bulletinmedia',
                    'html_content_field': 'bulletincontent',
                    'detail_url': 'https://ggzy.yn.gov.cn/tradeHall/tradeDetail?guid={}&colCode=2&rowCode=采购公告'
                },
                {
                    'channel_name': '政府采购-政府采购平台',
                    'search_api': '/zfchw/getggList',
                    'detail_api': 'https://ggzy.yn.gov.cn/ynggfwpt-home-api/zfchw/findggByGuid?guid={}',
                    'post_json': {
                        "bulletinclass": "bxlx001"
                    },
                    'title_field': 'bulletinTitle',
                    'publish_time_field': 'finishDay',
                    'bulletin_end_time': '',  # 并于2025-09-16 09:00（北京时间）前递交投标文件
                    'source_field': 'creatorName',  # 政府采购网 -> 云南省政府采购网
                    'html_content_field': 'fileContent',
                    'detail_url': 'https://ggzy.yn.gov.cn/tradeHall/tradeDetail?guid={}&colCode=21&rowCode=采购公告'
                },
                {
                    'channel_name': '综合交易',
                    'search_api': '/jyzyCenter/jyInfo/gcjs/getZbggList',
                    'detail_api': 'https://ggzy.yn.gov.cn/ynggfwpt-home-api/jyzyCenter/jyInfo/gcjs/findZbggByGuid?guid={}',
                    'post_json': {
                        "tenderSpecializedType": "",
                        "childType": "",
                        "tradeType": "zhjy"
                    },
                    'title_field': 'bulletinname',
                    'publish_time_field': 'bulletinissuetime',
                    'bulletin_end_time': 'tenderdocdeadline',  # 并于2025-09-16 09:00（北京时间）前递交投标文件
                    # 'source_field': 'bulletinmedia',
                    'html_content_field': 'bulletincontent',
                    'detail_url': 'https://ggzy.yn.gov.cn/tradeHall/tradeDetail?guid={}&colCode=7&rowCode=招标公告'
                },
            ]
            for search_args in channel_list:
                for s in self.key_words:
                    future = executor.submit(
                        key_word_search,
                        s, search_args
                    )
                    futures.append(future)

            # 等待所有任务完成
            concurrent.futures.wait(futures)

        # 启动线程池，分页请求
        logger.info(f'开始请求分页，total: {self.other_page_requests_queue.qsize()}')
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.thread_num) as executor:
            futures = []
            while True:
                try:
                    s = self.other_page_requests_queue.get_nowait()
                    future = executor.submit(other_pages_requests, s)
                    futures.append(future)
                except queue.Empty:
                    break
            # 等待所有任务完成
            concurrent.futures.wait(futures)

        duplicate_detail_list = []
        request_configs = []

        while True:
            try:
                s = self.detail_requests_queue.get_nowait()
                if s['url'] not in duplicate_detail_list:
                    request_configs.append(s)
                    duplicate_detail_list.append(s['url'])
            except queue.Empty:
                break

        logger.info(f'开始请求详情页，total: {len(duplicate_detail_list)}')

        # 启动线程池，带进度条显示
        results = []
        with ThreadPoolExecutor(max_workers=self.thread_num) as executor:
            # 提交所有任务
            future_to_config = {executor.submit(detail_requests, config): config for config in request_configs}

            # 使用tqdm显示进度
            with tqdm(total=len(request_configs), desc="详情页请求进度") as pbar:
                for future in as_completed(future_to_config):
                    try:
                        result = future.result()
                        results.append(result)

                        # 如果detail_requests函数有返回值表示成功/失败，可以统计
                        # 这里假设返回结果有success字段，你需要根据实际情况调整
                        if hasattr(result, 'get') and result.get('success'):
                            success_count = sum(1 for r in results if r.get('success'))
                            fail_count = len(results) - success_count
                            pbar.set_postfix(成功=success_count, 失败=fail_count)
                        else:
                            # 如果没有明确的成功/失败标识，只显示完成数量
                            pbar.set_postfix(已完成=len(results))

                    except Exception as e:
                        # 处理单个请求的异常
                        logger.exception(f"请求失败: {e}")
                        results.append({'success': False, 'error': str(e)})

                    pbar.update(1)

        logger.info(f'详情页请求完成，共处理 {len(results)} 个请求')
        # return results

        logger.info('开始导出数据。。。')
        datas_list = []
        while True:
            try:
                datas_list.append(self.details_queue.get_nowait())
            except queue.Empty:
                break
        self.df = pd.DataFrame(datas_list)
        return self


class Spider27:
    def __init__(self, thread_num=3):
        """
        eg:
            start_time='2025-05-23'
            end_time='2025-08-20'
        """
        self.start_time = START_TIME
        self.end_time = END_TIME
        self.key_words = KeyWords
        self.thread_num = thread_num

        self.crawler = Crawler(crawler_type='requests')

        self.detail_requests_queue = queue.Queue()
        self.other_page_requests_queue = queue.Queue()
        self.details_queue = queue.Queue()

        self.domain_name = 'https://ggzy.xizang.gov.cn'
        self.website_name = '西藏自治区公共资源交易网'
        self.fields = {
            'website_name': '',
            'url': '',
            'title': '',
            'publish_time': '',
            'source': '',
            'content': ''
        }
        self.df = None

    def master(self):
        def get_detail_requests_from_detail_list_res(detail_list_res):
            for detail in detail_list_res:
                """
                TODO:
                    是否记录列表页请求结果
                """
                detail_href = re.findall(
                    r"'(.*?)'",
                    content_parser.normalize_xpath(detail, './p[1]/@onclick')
                )[0]
                self.detail_requests_queue.put({
                    'url': self.domain_name + detail_href,
                    'requests_type': 'get',
                })

        def key_word_search(key_word, item):
            url = 'https://ggzy.xizang.gov.cn/search/queryContents.jhtml'
            post_data = {
                'title': key_word,
                'channelId': '',
                'areaNo': '',
                'projectType': '',
                'inDates': '',
                'timeBegin': f"{self.start_time} 00:00:00",
                'timeEnd': f"{self.end_time} 23:59:59"
            }
            post_data.update(item['post_data'])
            res = self.crawler.get_response(
                url=url,
                requests_type='post',
                # judgement=[],
                # post_json=post_json,
                post_data=post_data
            )

            selector = parsel.Selector(res)

            get_detail_requests_from_detail_list_res(
                selector.xpath('//*[@class="detail_content_right_box_content_ul"]//li'))

            total_count = int(re.findall(r',count: (\d+)', res, flags=re.S)[0])
            each_page_num = 10
            if total_count > each_page_num:
                for page_num in range(2, math.ceil(total_count / each_page_num) + 1):
                    self.other_page_requests_queue.put({
                        'url': f'https://ggzy.xizang.gov.cn/search/queryContents_{page_num}.jhtml',
                        'requests_type': 'post',
                        # 'judgement': [],
                        'post_data': post_data
                    })

        def other_pages_requests(item):
            res = self.crawler.get_response(
                url=item['url'],
                requests_type=item['requests_type'],
                # judgement=item['judgement'],
                # post_json=item['post_json'],
                post_data=item['post_data']
            )
            # json_res = json.loads(res)
            selector = parsel.Selector(res)

            get_detail_requests_from_detail_list_res(
                selector.xpath('//*[@class="detail_content_right_box_content_ul"]//li'))

        def detail_requests(item):
            res = self.crawler.get_response(
                url=item['url'],
                requests_type=item['requests_type']
            )
            selector = parsel.Selector(res)

            content_res = self.crawler.get_response(
                url=r'https://ggzy.xizang.gov.cn/personalitySearch/initDetailbyProjectCode',
                requests_type='post',
                post_json={
                    "projectCode": re.findall(
                        r'招标编号：(.*)',
                        content_parser.normalize_xpath(selector, '//*[@class="title-code"]')
                    )[0].strip(),
                    "path": item['url'].split('/')[3],
                    "sId": re.findall(r'"sId":\s*(\d+)', res, flags=re.S)[0]
                },
                judgement=[]
            )
            content_json_res = json.loads(content_res)

            content = content_parser.replace_p_tag(
                html_content=re.findall('<html>.*?</html>', content_json_res['data']['listData'][0]['txt'], flags=re.S)[
                    0]
            )
            publish_time = content_parser.normalize_xpath(selector, '//*[@id="rtime"]')
            publish_time = re.findall(r'\d{4}-\d{2}-\d{2}', publish_time, flags=re.S)
            publish_time = publish_time[0] if publish_time else ''

            data_out = {
                '标题': content_parser.normalize_xpath(selector, '//*[@class="headline"]'),
                '时间': publish_time,
                '来源': '',
                '链接': item['url'],
                '所在网站': self.website_name,
                '正文': content,

            }
            self.details_queue.put(data_out)

        # 启动线程池，根据模块、关键字搜索
        logger.info('开始根据关键字搜索。。。')
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.thread_num) as executor:
            futures = []
            channel_list = [
                {
                    'channel_name': '工程建设',
                    'post_data': {
                        "channelId": "3541",
                    },
                },
                {
                    'channel_name': '政府采购',
                    'post_data': {
                        "channelId": "3547",
                    },
                },
            ]
            for search_args in channel_list:
                for s in self.key_words:
                    future = executor.submit(
                        key_word_search,
                        s, search_args
                    )
                    futures.append(future)

            # 等待所有任务完成
            concurrent.futures.wait(futures)

        # 启动线程池，分页请求
        logger.info(f'开始请求分页，total: {self.other_page_requests_queue.qsize()}')
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.thread_num) as executor:
            futures = []
            while True:
                try:
                    s = self.other_page_requests_queue.get_nowait()
                    future = executor.submit(other_pages_requests, s)
                    futures.append(future)
                except queue.Empty:
                    break
            # 等待所有任务完成
            concurrent.futures.wait(futures)

        # detail_url 去重
        duplicate_detail_list = []
        request_configs = []

        while True:
            try:
                s = self.detail_requests_queue.get_nowait()
                if s['url'] not in duplicate_detail_list:
                    request_configs.append(s)
                    duplicate_detail_list.append(s['url'])
            except queue.Empty:
                break

        logger.info(f'开始请求详情页，total: {len(duplicate_detail_list)}')

        # 启动线程池，带进度条显示
        results = []
        with ThreadPoolExecutor(max_workers=self.thread_num) as executor:
            # 提交所有任务
            future_to_config = {executor.submit(detail_requests, config): config for config in request_configs}

            # 使用tqdm显示进度
            with tqdm(total=len(request_configs), desc="详情页请求进度") as pbar:
                for future in as_completed(future_to_config):
                    try:
                        result = future.result()
                        results.append(result)

                        # 如果detail_requests函数有返回值表示成功/失败，可以统计
                        # 这里假设返回结果有success字段，你需要根据实际情况调整
                        if hasattr(result, 'get') and result.get('success'):
                            success_count = sum(1 for r in results if r.get('success'))
                            fail_count = len(results) - success_count
                            pbar.set_postfix(成功=success_count, 失败=fail_count)
                        else:
                            # 如果没有明确的成功/失败标识，只显示完成数量
                            pbar.set_postfix(已完成=len(results))

                    except Exception as e:
                        # 处理单个请求的异常
                        logger.exception(f"请求失败: {e}")
                        results.append({'success': False, 'error': str(e)})

                    pbar.update(1)

        logger.info(f'详情页请求完成，共处理 {len(results)} 个请求')
        # return results

        logger.info('开始导出数据。。。')
        datas_list = []
        while True:
            try:
                datas_list.append(self.details_queue.get_nowait())
            except queue.Empty:
                break
        self.df = pd.DataFrame(datas_list)
        return self


# # TODO 网站加载缓慢，且详情内容为图片
# class Spider28:
#     def __init__(self, thread_num=3):
#         """
#         eg:
#             start_time='2025-05-23'
#             end_time='2025-08-20'
#         """
#         self.start_time = START_TIME
#         self.end_time = END_TIME
#         self.key_words = KeyWords
#         self.thread_num = thread_num
#
#         self.crawler = Crawler(crawler_type='requests')
#
#         self.detail_requests_queue = queue.Queue()
#         self.other_page_requests_queue = queue.Queue()
#         self.details_queue = queue.Queue()
#
#         self.domain_name = 'http://www.sntba.com/website/index.aspx'
#         self.website_name = '陕西采购与招标网'
#         self.fields = {
#             'website_name': '',
#             'url': '',
#             'title': '',
#             'publish_time': '',
#             'source': '',
#             'content': ''
#         }
#         self.df = None
#
#     def master(self):
#         def get_detail_requests_from_detail_list_res(detail_list_res):
#             for detail in detail_list_res[1:]:
#                 """
#                 TODO:
#                     是否记录列表页请求结果
#                 """
#
#                 detail_href = content_parser.normalize_xpath(
#                     detail, './td[1]//a/@href'
#                 )
#                 detail_href = re.findall(r'http.*?html', detail_href)[0]
#
#                 self.detail_requests_queue.put({
#                     'url': detail_href,
#                     'requests_type': 'get',
#                     'title': content_parser.normalize_xpath(
#                         detail, './td[1]//a/@title'
#                     ),
#                     'publish_time': content_parser.normalize_xpath(
#                         detail, './td[5]'
#                     ),
#                 })
#
#         def key_word_search(key_word, item):
#             url = 'http://bulletin.sntba.com/xxfbcmses/search/bulletin.html'
#             params = {
#                 'searchDate': '2000-09-04',
#                 'dates': '300',
#                 'categoryId': item['categoryId'],
#                 'industryName': '',
#                 'area': '',
#                 'status': '',
#                 'publishMedia': '',
#                 'sourceInfo': '',
#                 'showStatus': '',
#                 'word': key_word,
#                 'startcheckDate': self.start_time,
#                 'endcheckDate': self.end_time
#             }
#             res = self.crawler.get_response(
#                 url=url,
#                 requests_type='get',
#                 # judgement=[],
#                 params=params
#             )
#             selector = parsel.Selector(res)
#             # json_res = json.loads(res)
#
#             get_detail_requests_from_detail_list_res(
#                 selector.xpath('//table[@class="table_text"]//tr')
#             )
#
#             total_page = content_parser.normalize_xpath(
#                 selector, '//*[@class="pagination"]', text_join=''
#             )
#             if not total_page:
#                 return True
#             total_page = int(re.findall(r'共(\d+)页', total_page)[0])
#             if total_page > 1:
#                 for page_num in range(2, total_page + 1):
#                     new_params = deepcopy(params)
#                     new_params.update({
#                         'page': page_num
#                     })
#                     self.other_page_requests_queue.put({
#                         'url': url,
#                         'requests_type': 'get',
#                         # 'judgement': [],
#                         'params': new_params
#                     })
#
#         def other_pages_requests(item):
#             res = self.crawler.get_response(
#                 url=item['url'],
#                 requests_type=item['requests_type'],
#                 # judgement=item['judgement'],
#                 params=item['params']
#             )
#             selector = parsel.Selector(res)
#             # json_res = json.loads(res)
#
#             get_detail_requests_from_detail_list_res(
#                 selector.xpath('//table[@class="table_text"]//tr')
#             )
#
#         def detail_requests(item):
#             res = self.crawler.get_response(
#                 url=item['url'],
#                 requests_type=item['requests_type']
#             )
#             selector = parsel.Selector(res)
#
#             pdf_index = content_parser.normalize_xpath(
#                 selector, '//*[@class="mian_list_03"]/@index'
#             )
#
#             content = ''
#             # content = content_parser.replace_p_tag(
#             #     html_content=selector.xpath('//*[@class="info xiangxiyekuang"]').get()
#             # )
#
#             source = content_parser.normalize_xpath(
#                 selector, '//*[@class="mian_list_02"]/p/span[contains(text(),  "发布媒介")]'
#             )
#             source = re.findall(r'发布媒介：(.*)', source)
#             source = source[0] if source else ''
#             data_out = {
#                 '标题': item['title'],
#                 '时间': item['publish_time'],
#                 '来源': source,
#                 '链接': item['url'],
#                 '所在网站': self.website_name,
#                 '正文': content,
#
#             }
#             self.details_queue.put(data_out)
#
#         # 启动线程池，根据模块、关键字搜索
#         logger.info('开始根据关键字搜索。。。')
#         with concurrent.futures.ThreadPoolExecutor(max_workers=self.thread_num) as executor:
#             futures = []
#             channel_list = [
#                 {
#                     'channel_name': '招标公告',
#                     'categoryId': '88'
#                 },
#             ]
#             for search_args in channel_list:
#                 for s in self.key_words:
#                     future = executor.submit(
#                         key_word_search,
#                         s, search_args
#                     )
#                     futures.append(future)
#
#             # 等待所有任务完成
#             concurrent.futures.wait(futures)
#
#         # 启动线程池，分页请求
#         logger.info(f'开始请求分页，total: {self.other_page_requests_queue.qsize()}')
#         with concurrent.futures.ThreadPoolExecutor(max_workers=self.thread_num) as executor:
#             futures = []
#             while True:
#                 try:
#                     s = self.other_page_requests_queue.get_nowait()
#                     future = executor.submit(other_pages_requests, s)
#                     futures.append(future)
#                 except queue.Empty:
#                     break
#             # 等待所有任务完成
#             concurrent.futures.wait(futures)
#
#         # 启动线程池，详情页请求清洗
#         logger.info(f'开始请求详情页，total: {self.detail_requests_queue.qsize()}')
#         with concurrent.futures.ThreadPoolExecutor(max_workers=self.thread_num) as executor:
#             futures = []
#             duplicate_detail_list = []
#             while True:
#                 try:
#                     s = self.detail_requests_queue.get_nowait()
#                     if s['url'] not in duplicate_detail_list:
#                         future = executor.submit(detail_requests, s)
#                         futures.append(future)
#                         duplicate_detail_list.append(s['url'])
#                 except queue.Empty:
#                     break
#             # 等待所有任务完成
#             concurrent.futures.wait(futures)
#
#         logger.info('开始导出数据。。。')
#         datas_list = []
#         while True:
#             try:
#                 datas_list.append(self.details_queue.get_nowait())
#             except queue.Empty:
#                 break
#
#         self.df = pd.DataFrame(datas_list)
        return self
#
#
# # TODO SM2加密
# class Spider29:
#     def __init__(self, thread_num=3):
#         """
#         eg:
#             start_time='2025-05-23'
#             end_time='2025-08-20'
#         """
#         self.start_time = START_TIME
#         self.end_time = END_TIME
#         self.key_words = KeyWords
#         self.thread_num = thread_num
#
#         self.crawler = Crawler(crawler_type='requests')
#
#         self.detail_requests_queue = queue.Queue()
#         self.other_page_requests_queue = queue.Queue()
#         self.details_queue = queue.Queue()
#
#         self.domain_name = 'https://ggzyjy.gansu.gov.cn'
#         self.website_name = '甘肃省公共资源交易网'
#         self.fields = {
#             'website_name': '',
#             'url': '',
#             'title': '',
#             'publish_time': '',
#             'source': '',
#             'content': ''
#         }
#         self.df = None
#
#     def master(self):
#         def get_detail_requests_from_detail_list_res(detail_list_res):
#             for detail in detail_list_res['result']['records']:
#                 """
#                 TODO:
#                     是否记录列表页请求结果
#                 """
#                 self.detail_requests_queue.put({
#                     'url': self.domain_name + detail['linkurl'],
#                     'requests_type': 'get',
#                 })
#
#         def key_word_search(key_word, item):
#             url = 'https://sjfz.ggzyjy.gansu.gov.cn:19002/api/renren-api/ESProjectList/searchByPage'
#             post_data = {
#                 "platformCode": "",
#                 "noticeName": key_word,
#                 "tradeType": item['tradeType'],
#                 "link": "PROJECT",
#                 "pageSize": 10,
#                 "page": 1,
#                 "important": "",
#                 "remote": ""
#             }
#
#             while True:
#                 # selector = parsel.Selector(res)
#                 # max_date = content_parser.normalize_xpath(selector, '(//*[@class="right_new1"]//li[1]/a/span)[last()]')
#                 # min_date = content_parser.normalize_xpath(selector, '((//*[@class="right_new1"]//li)[last()]/a/span)[last()]')
#
#                 crypto = AccurateSM2Crypto()
#                 encrypted = crypto.get_encrypted(json.dumps(post_data, separators=(',', ':'), ensure_ascii=False))
#                 res = self.crawler.get_response(
#                     url=url,
#                     requests_type='post',
#                     judgement=[],
#                     post_data=encrypted
#                 )
#                 json_res = json.loads(res)
#
#                 max_date = re.findall(r'\d{4}-\d{2}-\d{2}', json_res['data']['list'][0]['sendTime'])[0]
#                 min_date = re.findall(r'\d{4}-\d{2}-\d{2}', json_res['data']['list'][-1]['sendTime'])[0]
#
#                 if (not max_date) or (not min_date):
#                     break
#                 if datetime.strptime(max_date, '%Y-%m-%d') < datetime.strptime(self.start_time, '%Y-%m-%d'):
#                     break
#                 elif datetime.strptime(min_date, '%Y-%m-%d') <= datetime.strptime(self.start_time, '%Y-%m-%d') < datetime.strptime(max_date, '%Y-%m-%d'):
#                     for detail in json_res['data']['list']:
#                         detail_date = re.findall(r'\d{4}-\d{2}-\d{2}', detail['sendTime'])[0]
#                         if datetime.strptime(self.start_time, '%Y-%m-%d') > datetime.strptime(detail_date, '%Y-%m-%d'):
#                             break
#
#                         self.detail_requests_queue.put({
#                             'url': self.domain_name + detail['infourl'],
#                             'requests_type': 'get',
#                             'title': deep_clean_text(detail['noticeName']),
#                             'publish_time': detail_date,
#                             'item': item
#                         })
#                     break
#
#                 else:
#                     for detail in json_res['data']['list']:
#                         detail_date = re.findall(r'\d{4}-\d{2}-\d{2}', detail['sendTime'])[0]
#                         self.detail_requests_queue.put({
#                             'url': self.domain_name + detail['infourl'],
#                             'requests_type': 'get',
#                             'title': deep_clean_text(
#                                 re.sub(r'<font.*?</font>', '', detail['title'])
#                             ),
#                             'publish_time': detail_date,
#                             'item': item
#                         })
#
#                     post_data.update({
#                         'page': post_data['page'] + 1
#                     })
#
#         def detail_requests(item):
#             # https://ggjy.mianyang.cn/projectInfo.html?infoid=53e3d686-c8c3-48d5-b88f-6db297ed14a2&categorynum=001001
#             # infoid = re.findall(r'[?]infoid=([\w-]+)', item['url'])[0]
#             # url_prime = fr"https://ggjy.mianyang.cn/EpointWebBuilder/getinfobyrelationguidaction.action?cmd=getInfolistNew&infoid={infoid}"
#             # res_prime = self.crawler.get_response(
#             #     url=url_prime,
#             #     requests_type=item['requests_type'],
#             #     judgement=[]
#             # )
#             # json_res_prime = json.loads(json.loads(res_prime)['custom'])[0]
#             res = self.crawler.get_response(
#                 url=item['url'],  # self.domain_name + json_res_prime['urlpath'],
#                 requests_type=item['requests_type'],
#                 judgement=[]
#             )
#             # json_res = json.loads(res)
#             selector = parsel.Selector(res)
#             content = content_parser.replace_p_tag(
#                 html_content=selector.xpath('//*[@class="article-info article-content"]').get()
#             )
#
#             source = content_parser.normalize_xpath(
#                 selector, '//*[@class="article-sources"]/p[contains(text(), "信息来源")]')
#             source = re.findall(r'信息来源：(.*?)】', source)
#             source = source[0] if source else ''
#
#             data_out = {
#                 '标题': item['title'],
#                 '时间': item['publish_time'],
#                 '来源': source,
#                 '链接': item['url'],
#                 '所在网站': self.website_name,
#                 '正文': content,
#
#             }
#             self.details_queue.put(data_out)
#
#         # 启动线程池，根据模块、关键字搜索
#         logger.info('开始根据关键字搜索。。。')
#         with concurrent.futures.ThreadPoolExecutor(max_workers=self.thread_num) as executor:
#             futures = []
#             channel_list = [
#                 {
#                     'channel_name': '建设工程',
#                     'tradeType': '2'
#                 },
#                 {
#                     'channel_name': '政府采购',
#                     'tradeType': '3'
#                 }
#             ]
#             for search_args in channel_list:
#                 for s in self.key_words:
#                     future = executor.submit(
#                         key_word_search,
#                         s, search_args
#                     )
#                     futures.append(future)
#
#             # 等待所有任务完成
#             concurrent.futures.wait(futures)
#
#         # 启动线程池，详情页请求清洗
#         logger.info(f'开始请求详情页，total: {self.detail_requests_queue.qsize()}')
#         with concurrent.futures.ThreadPoolExecutor(max_workers=self.thread_num) as executor:
#             futures = []
#             duplicate_detail_list = []
#             while True:
#                 try:
#                     s = self.detail_requests_queue.get_nowait()
#                     if (s['url'] not in duplicate_detail_list) and [key_word for key_word in self.key_words if key_word in s['title']]:
#                         future = executor.submit(detail_requests, s)
#                         futures.append(future)
#                         duplicate_detail_list.append(s['url'])
#                 except queue.Empty:
#                     break
#             logger.info(f'去重后详情页，total: {len(duplicate_detail_list)}')
#             # 等待所有任务完成
#             concurrent.futures.wait(futures)
#
#         logger.info('开始导出数据。。。')
#         datas_list = []
#         while True:
#             try:
#                 datas_list.append(self.details_queue.get_nowait())
#             except queue.Empty:
#                 break
#
#         self.df = pd.DataFrame(datas_list)
        return self



# TODO 网站加载缓慢，且详情内容为PDF
class Spider28:
    def __init__(self,thread_num=3):
        """
        eg:
            start_time='2025-05-23'
            end_time='2025-08-20'
        """
        self.start_time = START_TIME
        self.end_time = END_TIME
        self.key_words = KeyWords
        self.thread_num = thread_num

        self.crawler = Crawler(crawler_type='requests')

        self.detail_requests_queue = queue.Queue()
        self.other_page_requests_queue = queue.Queue()
        self.details_queue = queue.Queue()

        self.domain_name = 'http://www.sntba.com/website/index.aspx'
        self.website_name = '陕西采购与招标网'
        self.fields = {
            'website_name': '',
            'url': '',
            'title': '',
            'publish_time': '',
            'source': '',
            'content': ''
        }
        self.df = None

    def master(self):
        def get_detail_requests_from_detail_list_res(detail_list_res):
            for detail in detail_list_res[1:]:
                """
                TODO:
                    是否记录列表页请求结果
                """

                detail_href = content_parser.normalize_xpath(
                    detail, './td[1]//a/@href'
                )
                detail_href = re.findall(r'http.*?html', detail_href)[0]

                self.detail_requests_queue.put({
                    'url': detail_href,
                    'requests_type': 'get',
                    'title': content_parser.normalize_xpath(
                        detail, './td[1]//a/@title'
                    ),
                    'publish_time': content_parser.normalize_xpath(
                        detail, './td[5]'
                    ),
                })

        def key_word_search(key_word, item):
            url = 'http://bulletin.sntba.com/xxfbcmses/search/bulletin.html'
            params = {
                'searchDate': '2000-09-04',
                'dates': '300',
                'categoryId': item['categoryId'],
                'industryName': '',
                'area': '',
                'status': '',
                'publishMedia': '',
                'sourceInfo': '',
                'showStatus': '',
                'word': key_word,
                'startcheckDate': self.start_time,
                'endcheckDate': self.end_time
            }
            res = self.crawler.get_response(
                url=url,
                requests_type='get',
                # judgement=[],
                params=params
            )
            selector = parsel.Selector(res)
            # json_res = json.loads(res)

            get_detail_requests_from_detail_list_res(
                selector.xpath('//table[@class="table_text"]//tr')
            )

            total_page = content_parser.normalize_xpath(
                selector, '//*[@class="pagination"]', text_join=''
            )
            if not total_page:
                return True
            total_page = int(re.findall(r'共(\d+)页', total_page)[0])
            if total_page > 1:
                for page_num in range(2, total_page + 1):
                    new_params = deepcopy(params)
                    new_params.update({
                        'page': page_num
                    })
                    self.other_page_requests_queue.put({
                        'url': url,
                        'requests_type': 'get',
                        # 'judgement': [],
                        'params': new_params
                    })

        def other_pages_requests(item):
            res = self.crawler.get_response(
                url=item['url'],
                requests_type=item['requests_type'],
                # judgement=item['judgement'],
                params=item['params']
            )
            selector = parsel.Selector(res)
            # json_res = json.loads(res)

            get_detail_requests_from_detail_list_res(
                selector.xpath('//table[@class="table_text"]//tr')
            )

        def detail_requests(item):
            res = self.crawler.get_response(
                url=item['url'],
                requests_type=item['requests_type']
            )
            selector = parsel.Selector(res)

            pdf_index = content_parser.normalize_xpath(
                selector, '//*[@class="mian_list_03"]/@index'
            )
            # try:
            #     key_res = self.crawler.get_response(
            #         url=r'http://39.107.102.206:8087/permission/getSecretKey',
            #         requests_type='post',  # post、get
            #         # post_data=encrypted_result,
            #         judgement=[],
            #     )
            #
            #     des_key = json.loads(decrypt_by_des(key_res, str_key()))['data']
            #
            #     url = fr'http://39.107.102.206:8087/bulletin/getBulletin/{des_key}/{pdf_index}'
            #
            #     pdf_res = self.crawler.get_response(
            #         url=url,
            #         requests_type='get',  # post、get
            #         # post_data=encrypted_result,
            #         judgement=[],
            #         save_as_b=True,
            #         stream=True
            #     )
            #
            #     content = ocr_content(pdf_res)
            # except Exception as e:
            #     # logger.error(e)
            #     content = ''
            content = ''
            source = content_parser.normalize_xpath(
                selector, '//*[@class="mian_list_02"]/p/span[contains(text(),  "发布媒介")]'
            )
            source = re.findall(r'发布媒介：(.*)', source)
            source = source[0] if source else ''
            data_out = {
                '标题': item['title'],
                '时间': item['publish_time'],
                '来源': source,
                '链接': item['url'],
                '所在网站': self.website_name,
                '正文': content,

            }
            self.details_queue.put(data_out)
            # time.sleep(random.randint(5, 10))

        # 启动线程池，根据模块、关键字搜索
        logger.info('开始根据关键字搜索。。。')
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.thread_num) as executor:
            futures = []
            channel_list = [
                {
                    'channel_name': '招标公告',
                    'categoryId': '88'
                },
            ]
            for search_args in channel_list:
                for s in self.key_words:
                    future = executor.submit(
                        key_word_search,
                        s, search_args
                    )
                    futures.append(future)

            # 等待所有任务完成
            concurrent.futures.wait(futures)

        # 启动线程池，分页请求
        logger.info(f'开始请求分页，total: {self.other_page_requests_queue.qsize()}')
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.thread_num) as executor:
            futures = []
            while True:
                try:
                    s = self.other_page_requests_queue.get_nowait()
                    future = executor.submit(other_pages_requests, s)
                    futures.append(future)
                except queue.Empty:
                    break
            # 等待所有任务完成
            concurrent.futures.wait(futures)

        # 启动线程池，详情页请求清洗
        logger.info(f'开始请求详情页，total: {self.detail_requests_queue.qsize()}')
        self.crawler.headers.update({
            'Accept': '*/*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Origin': 'http://bulletin.sntba.com',
            'Proxy-Connection': 'keep-alive',
            'Referer': 'http://bulletin.sntba.com/',
        })
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            futures = []
            duplicate_detail_list = []
            while True:
                try:
                    s = self.detail_requests_queue.get_nowait()
                    if s['url'] not in duplicate_detail_list:
                        future = executor.submit(detail_requests, s)
                        futures.append(future)
                        duplicate_detail_list.append(s['url'])
                except queue.Empty:
                    break
            # 等待所有任务完成
            concurrent.futures.wait(futures)

        logger.info('开始导出数据。。。')
        datas_list = []
        while True:
            try:
                datas_list.append(self.details_queue.get_nowait())
            except queue.Empty:
                break

        self.df = pd.DataFrame(datas_list)
        return self


# TODO SM2加密
class Spider29:
    def __init__(self, thread_num=3):
        """
        eg:
            start_time='2025-05-23'
            end_time='2025-08-20'
        """
        self.start_time = START_TIME
        self.end_time = END_TIME
        self.key_words = KeyWords
        self.thread_num = thread_num

        self.crawler = Crawler(crawler_type='requests')

        self.detail_requests_queue = queue.Queue()
        self.other_page_requests_queue = queue.Queue()
        self.details_queue = queue.Queue()

        self.domain_name = 'https://ggzyjy.gansu.gov.cn'
        self.website_name = '甘肃省公共资源交易网'
        self.fields = {
            'website_name': '',
            'url': '',
            'title': '',
            'publish_time': '',
            'source': '',
            'content': ''
        }
        self.df = None

    def master(self):
        def key_word_search(key_word, item):
            url = 'https://sjfz.ggzyjy.gansu.gov.cn:19002/api/renren-api/ESProjectList/searchByPage'
            post_data = {
                "platformCode": "",
                "noticeName": key_word,
                "tradeType": item['tradeType'],
                "link": "PROJECT",
                "pageSize": 10,
                "page": 1,
                "important": "",
                "remote": ""
            }

            while True:
                # selector = parsel.Selector(res)
                # max_date = content_parser.normalize_xpath(selector, '(//*[@class="right_new1"]//li[1]/a/span)[last()]')
                # min_date = content_parser.normalize_xpath(selector, '((//*[@class="right_new1"]//li)[last()]/a/span)[last()]')

                crypto = AccurateSM2Crypto()
                encrypted = crypto.get_encrypted(json.dumps(post_data, separators=(',', ':'), ensure_ascii=False))
                res = self.crawler.get_response(
                    url=url,
                    requests_type='post',
                    judgement=[],
                    post_data=encrypted
                )
                json_res = json.loads(res)

                max_date = re.findall(r'\d{4}-\d{2}-\d{2}', json_res['data']['list'][0]['sendTime'])[0]
                min_date = re.findall(r'\d{4}-\d{2}-\d{2}', json_res['data']['list'][-1]['sendTime'])[0]

                if (not max_date) or (not min_date):
                    break
                if datetime.strptime(max_date, '%Y-%m-%d') < datetime.strptime(self.start_time, '%Y-%m-%d'):
                    break
                elif datetime.strptime(min_date, '%Y-%m-%d') <= datetime.strptime(self.start_time, '%Y-%m-%d') < datetime.strptime(max_date, '%Y-%m-%d'):
                    for detail in json_res['data']['list']:
                        detail_date = re.findall(r'\d{4}-\d{2}-\d{2}', detail['sendTime'])[0]
                        if datetime.strptime(self.start_time, '%Y-%m-%d') > datetime.strptime(detail_date, '%Y-%m-%d'):
                            break

                        post_data = {
                            "projectType": detail['projectClassifyCode'],
                            "pubServicePlatCode": detail['pubServicePlatCode'],
                            "projectId": detail['tenderProjectId'],
                            "tableName": "TENDER_ANNOUNCEMENT"
                        }

                        self.detail_requests_queue.put({
                            'url': r'https://sjfz.ggzyjy.gansu.gov.cn:19002/api/renren-api/ESAnnouncement/getAnnouncementList',
                            'requests_type': 'post',
                            'post_data': post_data,
                            'title': deep_clean_text(detail['noticeName']),
                            'publish_time': detail_date,
                            'source': detail['platformName'],
                            'item': item
                        })
                    break

                else:
                    for detail in json_res['data']['list']:
                        detail_date = re.findall(r'\d{4}-\d{2}-\d{2}', detail['sendTime'])[0]
                        post_data = {
                            "projectType": detail['projectClassifyCode'],
                            "pubServicePlatCode": detail['pubServicePlatCode'],
                            "projectId": detail['tenderProjectId'],
                            "tableName": "TENDER_ANNOUNCEMENT"
                        }

                        self.detail_requests_queue.put({
                            'url': r'https://sjfz.ggzyjy.gansu.gov.cn:19002/api/renren-api/ESAnnouncement/getAnnouncementList',
                            'requests_type': 'post',
                            'post_data': post_data,
                            'title': deep_clean_text(detail['noticeName']),
                            'publish_time': detail_date,
                            'source': detail['platformName'],
                            'item': item
                        })

                    post_data.update({
                        'page': post_data['page'] + 1
                    })

        def detail_requests(item):
            crypto = AccurateSM2Crypto()
            encrypted = crypto.get_encrypted(json.dumps(item['post_data'], separators=(',', ':'), ensure_ascii=False))
            res = self.crawler.get_response(
                url=item['url'],  # self.domain_name + json_res_prime['urlpath'],
                requests_type=item['requests_type'],
                post_data=encrypted,
                judgement=[]
            )
            json_res = json.loads(res)['data'][0]
            if re.findall(r'^http.*?pdf$', json_res['noticeContent']):
                url = json_res['noticeContent']
                try:
                    pdf_res = self.crawler.get_response(
                        url=url,
                        requests_type='get',
                        save_as_b=True,
                        stream=True
                    )

                    content = ocr_content(pdf_res)
                except Exception as e:
                    logger.error(e)
                    content = ''
            else:
                url = json_res['url']
                selector = parsel.Selector(json_res['noticeContent'])
                content = content_parser.replace_p_tag(
                    html_content=selector.xpath('.').get()
                )

            data_out = {
                '标题': item['title'],
                '时间': item['publish_time'],
                '来源': item['source'],
                '链接': url,
                '所在网站': self.website_name,
                '正文': content,

            }
            self.details_queue.put(data_out)

        # 启动线程池，根据模块、关键字搜索
        logger.info('开始根据关键字搜索。。。')
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.thread_num) as executor:
            futures = []
            channel_list = [
                {
                    'channel_name': '建设工程',
                    'tradeType': '2',
                },
                {
                    'channel_name': '政府采购',
                    'tradeType': '3',
                }
            ]
            for search_args in channel_list:
                for s in self.key_words:
                    future = executor.submit(
                        key_word_search,
                        s, search_args
                    )
                    futures.append(future)

            # 等待所有任务完成
            concurrent.futures.wait(futures)

        # 启动线程池，详情页请求清洗
        logger.info(f'开始请求详情页，total: {self.detail_requests_queue.qsize()}')
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.thread_num) as executor:
            futures = []
            duplicate_detail_list = []
            while True:
                try:
                    s = self.detail_requests_queue.get_nowait()
                    if (s['title'] not in duplicate_detail_list) and [key_word for key_word in self.key_words if key_word in s['title']]:
                        future = executor.submit(detail_requests, s)
                        futures.append(future)
                        duplicate_detail_list.append(s['title'])
                except queue.Empty:
                    break
            logger.info(f'去重后详情页，total: {len(duplicate_detail_list)}')
            # 等待所有任务完成
            concurrent.futures.wait(futures)

        logger.info('开始导出数据。。。')
        datas_list = []
        while True:
            try:
                datas_list.append(self.details_queue.get_nowait())
            except queue.Empty:
                break

        self.df = pd.DataFrame(datas_list)

        return self



class Spider30:
    def __init__(self, thread_num=3):
        """
        eg:
            start_time='2025-05-23'
            end_time='2025-08-20'
        """
        self.start_time = START_TIME
        self.end_time = END_TIME
        self.key_words = KeyWords
        self.thread_num = thread_num

        self.crawler = Crawler(crawler_type='requests')

        self.detail_requests_queue = queue.Queue()
        self.other_page_requests_queue = queue.Queue()
        self.details_queue = queue.Queue()

        self.domain_name = 'https://www.qhggzyjy.gov.cn/ggzy'
        self.website_name = '青海省公共资源交易网'
        self.fields = {
            'website_name': '',
            'url': '',
            'title': '',
            'publish_time': '',
            'source': '',
            'content': ''
        }
        self.df = None

    def master(self):
        def get_detail_requests_from_detail_list_res(detail_list_res):
            for detail in detail_list_res['result']['records']:
                """
                TODO:
                    是否记录列表页请求结果
                """
                detail_href = detail['linkurl'].split('/')
                detail_href.pop(1)
                detail_href = '/'.join(detail_href)

                self.detail_requests_queue.put({
                    'url': self.domain_name + detail_href,
                    'requests_type': 'get',
                    'title': deep_clean_text(detail['title']),
                    'publish_time': re.findall(r'\d{4}-\d{2}-\d{2}', detail['showdate'].strip())[0]
                })

        def key_word_search(key_word, item):
            url = 'https://www.qhggzyjy.gov.cn/inteligentsearch/rest/inteligentSearch/getFullTextData'
            post_json = {
                "token": "",
                "pn": 0,
                "rn": 10, "sdt": "", "edt": "",
                "wd": key_word,
                "inc_wd": "", "exc_wd": "", "fields": "title", "cnum": "001;002;003;004;005;006;007;008;009;010",
                "sort": "{\"showdate\":\"0\"}",
                "ssort": "title", "cl": 200, "terminal": "",
                "condition": [{
                    "fieldName": "categorynum", "isLike": True, "likeType": 2,
                    "equal": item['post_data']['channelId']
                }],
                "time": [
                    {
                        "fieldName": "showdate",
                        "startTime": f"{self.start_time} 00:00:00",
                        "endTime": f"{self.end_time} 23:59:59"
                    }
                ],
                "highlights": "title", "statistics": None, "unionCondition": None,
                "accuracy": "100", "noParticiple": "0", "searchRange": None, "isBusiness": 1
            }
            res = self.crawler.get_response(
                url=url,
                requests_type='post',
                judgement=[],
                post_json=post_json
            )
            json_res = json.loads(res)

            get_detail_requests_from_detail_list_res(json_res)

            total_count = int(json_res['result']['totalcount'])
            each_page_num = 10
            if total_count > each_page_num:
                for page_num in range(1, math.ceil(total_count / each_page_num) + 1):
                    new_post_json = deepcopy(post_json)
                    new_post_json.update({
                        'pn': page_num * each_page_num
                    })
                    self.other_page_requests_queue.put({
                        'url': url,
                        'requests_type': 'post',
                        'judgement': [],
                        'post_json': new_post_json
                    })

        def other_pages_requests(item):
            res = self.crawler.get_response(
                url=item['url'],
                requests_type=item['requests_type'],
                judgement=item['judgement'],
                post_json=item['post_json']
            )
            json_res = json.loads(res)

            get_detail_requests_from_detail_list_res(json_res)

        def detail_requests(item):
            res = self.crawler.get_response(
                url=item['url'],
                requests_type=item['requests_type']
            )
            selector = parsel.Selector(res)
            content = content_parser.replace_p_tag(
                html_content=selector.xpath('//*[@class="info xiangxiyekuang"]').get()
            )

            data_out = {
                '标题': content_parser.normalize_xpath(parsel.Selector(item['title']), '.'),
                '时间': item['publish_time'],
                '来源': '',
                '链接': item['url'],
                '所在网站': self.website_name,
                '正文': content,

            }
            self.details_queue.put(data_out)

        # 启动线程池，根据模块、关键字搜索
        logger.info('开始根据关键字搜索。。。')
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.thread_num) as executor:
            futures = []
            channel_list = [
                {
                    'channel_name': '工程建设',
                    'post_data': {
                        "channelId": "001001001",
                    },
                },
                {
                    'channel_name': '政府采购',
                    'post_data': {
                        "channelId": "001002001",
                    },
                },
            ]
            for search_args in channel_list:
                for s in self.key_words:
                    future = executor.submit(
                        key_word_search,
                        s, search_args
                    )
                    futures.append(future)

            # 等待所有任务完成
            concurrent.futures.wait(futures)

        # 启动线程池，分页请求
        logger.info(f'开始请求分页，total: {self.other_page_requests_queue.qsize()}')
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.thread_num) as executor:
            futures = []
            while True:
                try:
                    s = self.other_page_requests_queue.get_nowait()
                    future = executor.submit(other_pages_requests, s)
                    futures.append(future)
                except queue.Empty:
                    break
            # 等待所有任务完成
            concurrent.futures.wait(futures)

        # 启动线程池，详情页请求清洗
        logger.info(f'开始请求详情页，total: {self.detail_requests_queue.qsize()}')
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.thread_num) as executor:
            futures = []
            duplicate_detail_list = []
            while True:
                try:
                    s = self.detail_requests_queue.get_nowait()
                    if s['url'] not in duplicate_detail_list:
                        future = executor.submit(detail_requests, s)
                        futures.append(future)
                        duplicate_detail_list.append(s['url'])
                except queue.Empty:
                    break
            # 等待所有任务完成
            concurrent.futures.wait(futures)

        logger.info('开始导出数据。。。')
        datas_list = []
        while True:
            try:
                datas_list.append(self.details_queue.get_nowait())
            except queue.Empty:
                break

        self.df = pd.DataFrame(datas_list)
        return self


class Spider31:
    def __init__(self, thread_num=3):
        """
        eg:
            start_time='2025-05-23'
            end_time='2025-08-20'
        """
        self.start_time = START_TIME
        self.end_time = END_TIME
        self.key_words = KeyWords
        self.thread_num = thread_num

        self.crawler = Crawler(crawler_type='requests')

        self.detail_requests_queue = queue.Queue()
        self.other_page_requests_queue = queue.Queue()
        self.details_queue = queue.Queue()

        self.domain_name = 'https://ggzyjy.fzggw.nx.gov.cn'
        self.website_name = '宁夏回族自治区公共资源交易网'
        self.fields = {
            'website_name': '',
            'url': '',
            'title': '',
            'publish_time': '',
            'source': '',
            'content': ''
        }
        self.df = None

    def master(self):
        def get_detail_requests_from_detail_list_res(detail_list_res):
            for detail in detail_list_res['result']['records']:
                """
                TODO:
                    是否记录列表页请求结果
                """
                self.detail_requests_queue.put({
                    'url': self.domain_name + detail['linkurl'],
                    'requests_type': 'get',
                })

        def key_word_search(key_word, item):
            url = 'https://ggzyjy.fzggw.nx.gov.cn/interface_wz/rest/esinteligentsearch/getFullTextDataNew'
            post_json = {
                "token": "",
                "pn": 0,
                "rn": 10,
                "sdt": "", "edt": "", "wd": "", "inc_wd": "", "exc_wd": "", "fields": "", "cnum": "",
                "sort": "{\"webdate\":\"0\",\"id\":\"0\"}",
                "ssort": "", "cl": 10000, "terminal": "",
                "condition": [
                    {
                        "fieldName": "categorynum",
                        "equal": item['post_data']['channelId'],
                        "notEqual": None,
                        "equalList": None,
                        "notEqualList": None,
                        "isLike": True,
                        "likeType": 2
                    },
                    {
                        "fieldName": "titlenew",
                        "equal": key_word,
                        "notEqual": None,
                        "equalList": None,
                        "notEqualList": None,
                        "isLike": True,
                        "likeType": 0
                    }
                ],
                "time": [
                    {
                        "fieldName": "webdate",
                        "startTime": f"{self.start_time} 00:00:00",
                        "endTime": f"{self.end_time} 23:59:59"
                    }
                ],
                "highlights": "",
                "statistics": None,
                "unionCondition": [],
                "accuracy": "",
                "noParticiple": "1",
                "searchRange": None,
                "noWd": True
            }
            res = self.crawler.get_response(
                url=url,
                requests_type='post',
                judgement=[],
                post_json=post_json
            )
            json_res = json.loads(res)

            get_detail_requests_from_detail_list_res(json_res)

            total_count = int(json_res['result']['totalcount'])
            each_page_num = 10
            if total_count > each_page_num:
                for page_num in range(1, math.ceil(total_count / each_page_num) + 1):
                    new_post_json = deepcopy(post_json)
                    new_post_json.update({
                        'pn': page_num * each_page_num
                    })
                    self.other_page_requests_queue.put({
                        'url': url,
                        'requests_type': 'post',
                        'judgement': [],
                        'post_json': new_post_json
                    })

        def other_pages_requests(item):
            res = self.crawler.get_response(
                url=item['url'],
                requests_type=item['requests_type'],
                judgement=item['judgement'],
                post_json=item['post_json']
            )
            json_res = json.loads(res)

            get_detail_requests_from_detail_list_res(json_res)

        def detail_requests(item):
            res = self.crawler.get_response(
                url=item['url'],
                requests_type=item['requests_type']
            )
            selector = parsel.Selector(res)
            content = content_parser.replace_p_tag(
                html_content=selector.xpath('//*[@class="particulars-article"]').get()
            )

            publish_time = content_parser.normalize_xpath(selector, '//*[@class="particulars-details"]/p[1]')
            publish_time = re.findall(r'\d{4}-\d{2}-\d{2}', publish_time, flags=re.S)[0]

            data_out = {
                '标题': content_parser.normalize_xpath(selector, '//h2'),
                '时间': publish_time,
                '来源': '',
                '链接': item['url'],
                '所在网站': self.website_name,
                '正文': content,

            }
            self.details_queue.put(data_out)

        # 启动线程池，根据模块、关键字搜索
        logger.info('开始根据关键字搜索。。。')
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.thread_num) as executor:
            futures = []
            channel_list = [
                {
                    'channel_name': '工程建设',
                    'post_data': {
                        "channelId": "001001001005",
                    },
                },
                {
                    'channel_name': '政府采购',
                    'post_data': {
                        "channelId": "001001002001",
                    },
                },
            ]
            for search_args in channel_list:
                for s in self.key_words:
                    future = executor.submit(
                        key_word_search,
                        s, search_args
                    )
                    futures.append(future)

            # 等待所有任务完成
            concurrent.futures.wait(futures)

        # 启动线程池，分页请求
        logger.info(f'开始请求分页，total: {self.other_page_requests_queue.qsize()}')
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.thread_num) as executor:
            futures = []
            while True:
                try:
                    s = self.other_page_requests_queue.get_nowait()
                    future = executor.submit(other_pages_requests, s)
                    futures.append(future)
                except queue.Empty:
                    break
            # 等待所有任务完成
            concurrent.futures.wait(futures)

        # 启动线程池，详情页请求清洗
        logger.info(f'开始请求详情页，total: {self.detail_requests_queue.qsize()}')
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.thread_num) as executor:
            futures = []
            duplicate_detail_list = []
            while True:
                try:
                    s = self.detail_requests_queue.get_nowait()
                    if s['url'] not in duplicate_detail_list:
                        future = executor.submit(detail_requests, s)
                        futures.append(future)
                        duplicate_detail_list.append(s['url'])
                except queue.Empty:
                    break
            # 等待所有任务完成
            concurrent.futures.wait(futures)

        logger.info('开始导出数据。。。')
        datas_list = []
        while True:
            try:
                datas_list.append(self.details_queue.get_nowait())
            except queue.Empty:
                break

        self.df = pd.DataFrame(datas_list)
        return self


class Spider32:
    def __init__(self, thread_num=3):
        """
        eg:
            start_time='2025-05-23'
            end_time='2025-08-20'
        """
        self.start_time = START_TIME
        self.end_time = END_TIME
        self.key_words = KeyWords
        self.thread_num = thread_num

        self.crawler = Crawler(crawler_type='requests')

        self.detail_requests_queue = queue.Queue()
        self.other_page_requests_queue = queue.Queue()
        self.details_queue = queue.Queue()

        self.domain_name = 'https://ggzy.xinjiang.gov.cn'
        self.website_name = '新疆公共资源交易网'
        self.fields = {
            'website_name': '',
            'url': '',
            'title': '',
            'publish_time': '',
            'source': '',
            'content': ''
        }
        self.df = None

    def master(self):
        def get_detail_requests_from_detail_list_res(detail_list_res):
            # logger.info(f"获取到detail数量：{len(detail_list_res['result']['records'])}")
            for detail in detail_list_res['result']['records']:
                """
                TODO:
                    是否记录列表页请求结果
                """
                self.detail_requests_queue.put({
                    'url': fr"{self.domain_name}/xinjiangggzy{detail['linkurl']}",
                    'requests_type': 'get',
                    'title': deep_clean_text(detail['projectname']),
                    'publish_time': re.findall(r'\d{4}-\d{2}-\d{2}', detail['webdate'], flags=re.S)[0]
                })

        def key_word_search(key_word, item):
            url = 'https://ggzy.xinjiang.gov.cn/inteligentsearchnew/rest/esinteligentsearch/getFullTextDataNew'
            post_json = {
                "token": "",
                "pn": 0,
                "rn": 10,
                "sdt": f"{self.start_time} 00:00:00",
                "edt": f"{self.end_time} 23:59:59",
                "wd": "",
                "inc_wd": "",
                "exc_wd": "",
                "fields": "title,projectnum,projectname",
                "cnum": "001",
                "sort": "{\"webdate\":\"0\"}",
                "ssort": "title",
                "cl": 200,
                "terminal": "",
                "condition": [
                    {
                        "fieldName": "categorynum",
                        "isLike": True,
                        "likeType": 2,
                        "equal": item['post_data']['channelId']
                    },
                    {
                        "fieldName": "projectname",
                        "isLike": True,
                        "likeType": 0,
                        "equal": key_word
                    }
                ],
                "time": None,
                "highlights": "title",
                "statistics": None,
                "unionCondition": [],
                "accuracy": "100",
                "noParticiple": "0",
                "searchRange": None,
                "isBusiness": 1
            }
            self.crawler.headers.update({
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            })
            res = self.crawler.get_response(
                url=url,
                requests_type='post',
                judgement=[],
                post_json=post_json
            )
            json_res = json.loads(res)

            get_detail_requests_from_detail_list_res(json_res)

            total_count = int(json_res['result']['totalcount'])
            each_page_num = 10
            if total_count > each_page_num:
                for page_num in range(1, math.ceil(total_count / each_page_num) + 1):
                    new_post_json = deepcopy(post_json)
                    new_post_json.update({
                        'pn': page_num * each_page_num
                    })
                    self.other_page_requests_queue.put({
                        'url': url,
                        'requests_type': 'post',
                        'judgement': [],
                        'post_json': new_post_json
                    })

        def other_pages_requests(item):
            res = self.crawler.get_response(
                url=item['url'],
                requests_type=item['requests_type'],
                judgement=item['judgement'],
                post_json=item['post_json']
            )
            json_res = json.loads(res)

            get_detail_requests_from_detail_list_res(json_res)

        def detail_requests(item):
            res = self.crawler.get_response(
                url=item['url'],
                requests_type=item['requests_type'],
                judgement=[]
            )
            selector = parsel.Selector(res)
            content = content_parser.replace_p_tag(
                html_content=selector.xpath('//*[@class="ewb-info-bd"]').get()
            )

            source = content_parser.normalize_xpath(
                selector,
                '//*[@class="ewb-info-intro"]/span[contains(text(), "信息来源：")]'
            )
            source = re.findall(r'信息来源：(.*)', source)[0].strip()

            data_out = {
                '标题': item['title'],
                '时间': item['publish_time'],
                '来源': source,
                '链接': item['url'],
                '所在网站': self.website_name,
                '正文': content,

            }
            self.details_queue.put(data_out)

        # 启动线程池，根据模块、关键字搜索
        logger.info('开始根据关键字搜索。。。')
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.thread_num) as executor:
            futures = []
            channel_list = [
                {
                    'channel_name': '房屋和市政工程',
                    'post_data': {
                        "channelId": "001001001",
                    },
                },
                {
                    'channel_name': '交通工程',
                    'post_data': {
                        "channelId": "001002001",
                    },
                },
                {
                    'channel_name': '水利工程',
                    'post_data': {
                        "channelId": "001003001",
                    },
                },
                {
                    'channel_name': '地质工程',
                    'post_data': {
                        "channelId": "001013001",
                    },
                },
                {
                    'channel_name': '政府采购',
                    'post_data': {
                        "channelId": "001004003",
                    },
                },
                {
                    'channel_name': '铁路工程',
                    'post_data': {
                        "channelId": "001009001",
                    },
                },
                {
                    'channel_name': '民航专业工程',
                    'post_data': {
                        "channelId": "001010001",
                    },
                },
            ]
            for search_args in channel_list:
                for s in self.key_words:
                    future = executor.submit(
                        key_word_search,
                        s, search_args
                    )
                    futures.append(future)

            # 等待所有任务完成
            concurrent.futures.wait(futures)

        # 启动线程池，分页请求
        logger.info(f'开始请求分页，total: {self.other_page_requests_queue.qsize()}')
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.thread_num) as executor:
            futures = []
            while True:
                try:
                    s = self.other_page_requests_queue.get_nowait()
                    future = executor.submit(other_pages_requests, s)
                    futures.append(future)
                except queue.Empty:
                    break
            # 等待所有任务完成
            concurrent.futures.wait(futures)

        # 启动线程池，详情页请求清洗
        logger.info(f'开始请求详情页，total: {self.detail_requests_queue.qsize()}')
        del self.crawler.headers['Content-Type']
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.thread_num) as executor:
            futures = []
            duplicate_detail_list = []
            while True:
                try:
                    s = self.detail_requests_queue.get_nowait()
                    if s['url'] not in duplicate_detail_list:
                        future = executor.submit(detail_requests, s)
                        futures.append(future)
                        duplicate_detail_list.append(s['url'])
                except queue.Empty:
                    break
            # 等待所有任务完成
            concurrent.futures.wait(futures)

        logger.info('开始导出数据。。。')
        datas_list = []
        while True:
            try:
                datas_list.append(self.details_queue.get_nowait())
            except queue.Empty:
                break

        self.df = pd.DataFrame(datas_list)
        return self


class Spider33:
    def __init__(self, thread_num=3):
        """
        eg:
            start_time='2025-05-23'
            end_time='2025-08-20'
        """
        self.start_time = START_TIME
        self.end_time = END_TIME
        self.key_words = KeyWords
        self.thread_num = thread_num

        self.crawler = Crawler(crawler_type='requests')

        self.detail_requests_queue = queue.Queue()
        self.other_page_requests_queue = queue.Queue()
        self.details_queue = queue.Queue()

        self.domain_name = 'https://www.cdggzy.com'
        self.website_name = '成都市公共资源交易服务中心'
        self.fields = {
            'website_name': '',
            'url': '',
            'title': '',
            'publish_time': '',
            'source': '',
            'content': ''
        }
        self.df = None

    def master(self):
        def get_detail_requests_from_detail_list_res(detail_list_res, item):
            # logger.info(f"获取到detail数量：{len(detail_list_res['result']['records'])}")
            for detail in detail_list_res:
                """
                TODO:
                    是否记录列表页请求结果
                    https://www.cdggzy.com/sitenew/notice/JSGC/NoticeContent.aspx?id=D68FE12129E64BD986B78B68970CAE9A
                    
                    swNoticeContent.aspx?id=E6022B501A0E472FAA2C34161F9802B4
                    
                    https://www.cdggzy.com/sitenew/notice/zfcg/swNoticeContent.aspx?id=E6022B501A0E472FAA2C34161F9802B4
                    https://www.cdggzy.com/site/Notice/ZFCG/swNoticeContentPage.aspx?id=E6022B501A0E472FAA2C34161F9802B4
                    https://www.cdggzy.com/site/Notice/ZFCG/NoticeContentPage.aspx?id=6169593_zcy
                """
                href = content_parser.normalize_xpath(detail, './div[2]//a/@href')
                if item['channel_name'] == '工程建设':
                    # real_url = href
                    pass
                else:
                    href = fr'https://www.cdggzy.com/sitenew/notice/zfcg/{href}'
                    # real_url = r'https://www.cdggzy.com/site/Notice/ZFCG/swNoticeContentPage.aspx?id={}'.format(
                    #     href.split('?id=')[-1]
                    # )

                self.detail_requests_queue.put({
                    'url': href,
                    # 'real_url': real_url,
                    'requests_type': 'get',
                    'title': content_parser.normalize_xpath(detail, './div[2]/@title'),
                    'publish_time': content_parser.normalize_xpath(detail, '(./div)[last()]')
                })

        def key_word_search(item):
            url = item['search_url']
            post_data = {
                '__EVENTTARGET': '',
                '__EVENTARGUMENT': '',
                'displaytypeval': '1',
                'displaystateval': '0',
                'dealaddressval': '0',
                'divpudate': '5',
                'inputTime1': self.start_time,
                'inputTime2': self.end_time,
                'hidCount': '',
                'hidCrunt': '1',
                'hidLimit': '10',
                'hidReload': 'false',
                '__ASYNCPOST': 'true',  # false
                # 'btnCgSearch': '查询',  # 分页事件
            }
            post_data.update({
                item['search_filed']: '查询'
            })
            post_data.update(item['post_data'])
            # self.crawler.headers.update({
            #     'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            # })

            res = self.crawler.get_response(
                url=url,
                requests_type='post',
                judgement=[],
                post_data=post_data
            )
            selector = parsel.Selector(res)

            get_detail_requests_from_detail_list_res(
                selector.xpath('//*[@id="contentlist"]//*[@class="list-row"]'), item
            )

            total_count = int(content_parser.normalize_xpath(selector, '//*[@id="hidCount"]/@value'))
            each_page_num = 10
            if total_count > each_page_num:
                for page_num in range(2, math.ceil(total_count / each_page_num) + 1):
                    new_post_data = deepcopy(post_data)
                    new_post_data.update({
                        'ScriptManager1': 'UpdatePanel1|btnChangePage',
                        '__ASYNCPOST': 'false',
                        item['search_filed']: '分页事件',
                        'hidCrunt': page_num
                    })
                    self.other_page_requests_queue.put({
                        'url': url,
                        'requests_type': 'post',
                        'judgement': [],
                        'post_data': new_post_data,
                        'item': item
                    })

        def other_pages_requests(item):
            res = self.crawler.get_response(
                url=item['url'],
                requests_type=item['requests_type'],
                judgement=item['judgement'],
                post_data=item['post_data']
            )
            json_res = json.loads(res)

            get_detail_requests_from_detail_list_res(json_res, item['item'])

        def detail_requests(item):
            res = self.crawler.get_response(
                url=item.get('real_url', item.get('url')),
                requests_type=item['requests_type'],
                judgement=[]
            )
            selector = parsel.Selector(res)

            iframe_tag = selector.xpath('//iframe')
            if iframe_tag:
                href = content_parser.normalize_xpath(iframe_tag, './@src')
                url = self.domain_name + '/' + '/'.join(href.split('/')[3:])
                res = self.crawler.get_response(
                    url=url,
                    requests_type=item['requests_type'],
                    judgement=[]
                )
                selector = parsel.Selector(res)
                content = content_parser.replace_p_tag(
                    html_content=selector.xpath('//*[@id="noticeArea"]').get()
                )
            else:
                content = content_parser.replace_p_tag(
                    html_content=selector.xpath('//*[@class="right-content"]').get()
                )

            data_out = {
                '标题': item['title'],
                '时间': item['publish_time'],
                '来源': '',
                '链接': item['url'],
                '所在网站': self.website_name,
                '正文': content,

            }
            self.details_queue.put(data_out)

        # 启动线程池，根据模块、关键字搜索
        logger.info('开始根据关键字搜索。。。')
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.thread_num) as executor:
            futures = []
            channel_list = [
                {
                    'channel_name': '工程建设',
                    'search_url': r'https://www.cdggzy.com/sitenew/notice/JSGC/List.aspx',
                    'search_filed': 'btnGcSearch',
                    'post_data': {
                        'ScriptManager1': 'UpdatePanel1|btnGcSearch',  # UpdatePanel1|btnChangePage
                        '__VIEWSTATEGENERATOR': 'A9DF1CDD',
                        'txt_keyword': '关键词',
                    },
                },
                {
                    'channel_name': '政府采购',
                    'search_url': r'https://www.cdggzy.com/sitenew/notice/zfcg/List.aspx',
                    'search_filed': 'btnCgSearch',
                    'post_data': {
                        'ScriptManager1': 'UpdatePanel1|btnCgSearch',  # UpdatePanel1|btnChangePage
                        '__VIEWSTATEGENERATOR': '10E748F1',
                        'announcemenSearchInput': '关键词',
                    },
                },
            ]
            for search_args in channel_list:
                for s in self.key_words:
                    new_search_args = deepcopy(search_args)
                    if new_search_args['post_data'].get('txt_keyword'):
                        new_search_args['post_data']['txt_keyword'] = s
                    else:
                        new_search_args['post_data']['announcemenSearchInput'] = s
                    future = executor.submit(
                        key_word_search,
                        new_search_args
                    )
                    futures.append(future)

            # 等待所有任务完成
            concurrent.futures.wait(futures)

        # 启动线程池，分页请求
        logger.info(f'开始请求分页，total: {self.other_page_requests_queue.qsize()}')
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.thread_num) as executor:
            futures = []
            while True:
                try:
                    s = self.other_page_requests_queue.get_nowait()
                    future = executor.submit(other_pages_requests, s)
                    futures.append(future)
                except queue.Empty:
                    break
            # 等待所有任务完成
            concurrent.futures.wait(futures)

        # 启动线程池，详情页请求清洗
        logger.info(f'开始请求详情页，total: {self.detail_requests_queue.qsize()}')
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.thread_num) as executor:
            futures = []
            duplicate_detail_list = []
            while True:
                try:
                    s = self.detail_requests_queue.get_nowait()
                    if s['url'] not in duplicate_detail_list:
                        future = executor.submit(detail_requests, s)
                        futures.append(future)
                        duplicate_detail_list.append(s['url'])
                except queue.Empty:
                    break
            # 等待所有任务完成
            logger.info(f'去重后详情页，total: {len(duplicate_detail_list)}')
            concurrent.futures.wait(futures)

        logger.info('开始导出数据。。。')
        datas_list = []
        while True:
            try:
                datas_list.append(self.details_queue.get_nowait())
            except queue.Empty:
                break

        self.df = pd.DataFrame(datas_list)
        return self


class Spider34:
    def __init__(self, thread_num=3):
        """
        eg:
            start_time='2025-05-23'
            end_time='2025-08-20'
        """
        self.start_time = START_TIME
        self.end_time = END_TIME
        self.key_words = KeyWords
        self.thread_num = thread_num

        self.crawler = Crawler(crawler_type='requests')

        self.detail_requests_queue = queue.Queue()
        self.other_page_requests_queue = queue.Queue()
        self.details_queue = queue.Queue()

        self.domain_name = 'http://61.157.185.14'
        self.website_name = '自贡市公共资源交易服务中心'
        self.fields = {
            'website_name': '',
            'url': '',
            'title': '',
            'publish_time': '',
            'source': '',
            'content': ''
        }
        self.df = None

    def master(self):
        def get_detail_requests_from_detail_list_res(detail_list_res):
            for detail in detail_list_res['Table']:
                """
                TODO:
                    是否记录列表页请求结果
                """
                self.detail_requests_queue.put({
                    'url': fr"http://61.157.185.14/EpointWebBuilder_zgzfcg/ggSearchAction.action?cmd=pageRedirect&categorynum={detail['categorynum']}&infoid={detail['infoid']}",
                    'requests_type': 'get',
                    'title': deep_clean_text(detail['title']),
                    'publish_time': detail['infodate']
                })

        def key_word_search(key_word, item):
            url = 'http://61.157.185.14/EpointWebBuilder_zgzfcg/ggSearchAction.action'
            params = {
                'cmd': 'getList',
                'xiaqucode': '',
                'title': key_word,  # key_word
                'siteGuid': '3395566b-59cf-475e-bfab-0911b0e517aa',
                'categorynum': item['params']['channelId'],
                'datestart': self.start_time,
                'dateend': self.end_time,
                'pageIndex': '0',
                'pageSize': '10',
                'verificationGuid': '',
                'verificationCode': '',
            }
            res = self.crawler.get_response(
                url=url,
                requests_type='get',
                judgement=[],
                params=params
            )
            json_res = json.loads(json.loads(res)['custom'])

            get_detail_requests_from_detail_list_res(json_res)

            total_count = int(json_res['RowCount'])
            each_page_num = 10
            if total_count > each_page_num:
                for page_num in range(1, math.ceil(total_count / each_page_num) + 1):
                    new_params = deepcopy(params)
                    new_params.update({
                        'pageIndex': str(page_num)
                    })
                    self.other_page_requests_queue.put({
                        'url': url,
                        'requests_type': 'get',
                        'judgement': [],
                        'params': new_params
                    })

        def other_pages_requests(item):
            res = self.crawler.get_response(
                url=item['url'],
                requests_type=item['requests_type'],
                judgement=item['judgement'],
                params=item['params']
            )
            json_res = json.loads(json.loads(res)['custom'])

            get_detail_requests_from_detail_list_res(json_res)

        def detail_requests(item):
            res_prime = self.crawler.get_response(
                url=item['url'],
                requests_type=item['requests_type'],
                judgement=[],
            )
            json_res_prime = json.loads(res_prime)

            real_url = self.domain_name + json_res_prime['custom']
            res = self.crawler.get_response(
                url=real_url,
                requests_type='get',
            )
            # print(1)
            selector = parsel.Selector(res)
            content = content_parser.replace_p_tag(
                html_content=selector.xpath('//*[@class="ewb-com ewb-article"]').get()
            )
            data_out = {
                '标题': item['title'],
                '时间': item['publish_time'],
                '来源': '',
                '链接': real_url,
                '所在网站': self.website_name,
                '正文': content,

            }
            self.details_queue.put(data_out)

        # 启动线程池，根据模块、关键字搜索
        logger.info('开始根据关键字搜索。。。')
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.thread_num) as executor:
            futures = []
            channel_list = [
                {
                    'channel_name': '工程建设',
                    'params': {
                        "channelId": "003001001",
                    },
                },
                {
                    'channel_name': '政府采购',
                    'params': {
                        "channelId": "003002001",
                    },
                },
            ]
            for search_args in channel_list:
                for s in self.key_words:
                    future = executor.submit(
                        key_word_search,
                        s, search_args
                    )
                    futures.append(future)

            # 等待所有任务完成
            concurrent.futures.wait(futures)

        # 启动线程池，分页请求
        logger.info(f'开始请求分页，total: {self.other_page_requests_queue.qsize()}')
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.thread_num) as executor:
            futures = []
            while True:
                try:
                    s = self.other_page_requests_queue.get_nowait()
                    future = executor.submit(other_pages_requests, s)
                    futures.append(future)
                except queue.Empty:
                    break
            # 等待所有任务完成
            concurrent.futures.wait(futures)

        # 启动线程池，详情页请求清洗
        logger.info(f'开始请求详情页，total: {self.detail_requests_queue.qsize()}')

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.thread_num) as executor:
            futures = []
            duplicate_detail_list = []
            while True:
                try:
                    s = self.detail_requests_queue.get_nowait()
                    if s['url'] not in duplicate_detail_list:
                        future = executor.submit(detail_requests, s)
                        futures.append(future)
                        duplicate_detail_list.append(s['url'])
                except queue.Empty:
                    break
            # 等待所有任务完成
            concurrent.futures.wait(futures)

        logger.info('开始导出数据。。。')
        datas_list = []
        while True:
            try:
                datas_list.append(self.details_queue.get_nowait())
            except queue.Empty:
                break

        self.df = pd.DataFrame(datas_list)
        return self


class Spider35:
    def __init__(self, thread_num=3):
        """
        eg:
            start_time='2025-05-23'
            end_time='2025-08-20'
        """
        self.start_time = START_TIME
        self.end_time = END_TIME
        self.key_words = KeyWords
        self.thread_num = thread_num

        self.crawler = Crawler(crawler_type='requests')

        self.detail_requests_queue = queue.Queue()
        self.other_page_requests_queue = queue.Queue()
        self.details_queue = queue.Queue()

        self.domain_name = 'http://www.pzhggzy.cn'
        self.website_name = '攀枝花市公共资源交易服务中心'
        self.fields = {
            'website_name': '',
            'url': '',
            'title': '',
            'publish_time': '',
            'source': '',
            'content': ''
        }

        self.get_sub_parts = get_sub_parts
        self.df = None

    def master(self):
        def get_detail_requests_from_detail_list_res(detail_list_res):
            for detail in detail_list_res:
                """
                TODO:
                    是否记录列表页请求结果
                """
                self.detail_requests_queue.put({
                    'url': self.domain_name + content_parser.normalize_xpath(
                        detail, './/a/@href'
                    ),
                    'requests_type': 'get',
                    # 'title': deep_clean_text(detail['title']),
                    # 'publish_time': detail['infodate']
                })

        def key_word_search(key_word, item):
            url = 'http://www.pzhggzy.cn/searchJyxx/list'
            post_data = {
                'sousuo_title': key_word,
                'ywlx': '',
                'xxlx': '',
                'jyptid': '',
                'timeid': 'no',
                'startData': self.start_time,
                'endData': self.end_time,
                'currentPage': '1',
                'type': '1',
            }
            post_data.update(item['post_data'])
            res = self.crawler.get_response(
                url=url,
                requests_type='post',
                post_data=post_data
            )

            selector = parsel.Selector(res)

            get_detail_requests_from_detail_list_res(
                selector.xpath('//*[@class="jyxx_table"]/ul//li')
            )  # [div[2]/div[contains(text(), "招标公告") or contains(text(), "采购公告")]]

            total_page = int(re.findall(r'class="dian">共(\d+)页', res, flags=re.S)[0])
            if total_page > 1:
                for page_num in range(2, total_page + 1):
                    new_post_data = deepcopy(post_data)
                    new_post_data.update({
                        'currentPage': page_num
                    })
                    self.other_page_requests_queue.put({
                        'url': url,
                        'requests_type': 'post',
                        'post_data': new_post_data
                    })

        def other_pages_requests(item):
            res = self.crawler.get_response(
                url=item['url'],
                requests_type=item['requests_type'],
                post_data=item['post_data']
            )

            get_detail_requests_from_detail_list_res(
                parsel.Selector(res).xpath(
                    '//*[@class="jyxx_table"]/ul//li'
                )  # [div[2]/div[contains(text(), "招标公告") or contains(text(), "采购公告")]]
            )

        def detail_requests(item):
            res = self.crawler.get_response(
                url=item['url'],
                requests_type=item['requests_type'],
            )
            selector = parsel.Selector(res)
            content = content_parser.replace_p_tag(
                html_content=selector.xpath('//*[@id="jyxxDetail"]').get()
            )

            source_part, publish_time_part = self.get_sub_parts(
                r'发布时间[:：].*', '',
                content_parser.normalize_xpath(selector, '//*[@class="context_title"]/div[2]/span[1]', text_join='')
            )
            source = deep_clean_text(re.findall(r'来源[:：](.*)', source_part)[0])
            publish_time = deep_clean_text(re.findall(r'发布时间[:：](.*)', publish_time_part[0])[0])

            data_out = {
                '标题': content_parser.normalize_xpath(selector, '//*[@class="context_title"]/div[1]'),
                '时间': publish_time,
                '来源': source,
                '链接': item['url'],
                '所在网站': self.website_name,
                '正文': content,

            }
            self.details_queue.put(data_out)

        # 启动线程池，根据模块、关键字搜索
        logger.info('开始根据关键字搜索。。。')
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.thread_num) as executor:
            futures = []
            channel_list = [
                {
                    'channel_name': '工程建设',
                    'post_data': {
                        "ywlx": "gcjs",
                        "xxlx": "zbgg",
                        "type": "2",
                    },
                },
                {
                    'channel_name': '政府采购',
                    'post_data': {
                        "ywlx": "zfcg",
                        "xxlx": "zbgg",
                        "type": "3",
                    },
                },
            ]
            for search_args in channel_list:
                for s in self.key_words:
                    future = executor.submit(
                        key_word_search,
                        s, search_args
                    )
                    futures.append(future)

            # 等待所有任务完成
            concurrent.futures.wait(futures)

        # 启动线程池，分页请求
        logger.info(f'开始请求分页，total: {self.other_page_requests_queue.qsize()}')
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.thread_num) as executor:
            futures = []
            while True:
                try:
                    s = self.other_page_requests_queue.get_nowait()
                    future = executor.submit(other_pages_requests, s)
                    futures.append(future)
                except queue.Empty:
                    break
            # 等待所有任务完成
            concurrent.futures.wait(futures)

        # 启动线程池，详情页请求清洗
        logger.info(f'开始请求详情页，total: {self.detail_requests_queue.qsize()}')

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.thread_num) as executor:
            futures = []
            duplicate_detail_list = []
            while True:
                try:
                    s = self.detail_requests_queue.get_nowait()
                    if s['url'] not in duplicate_detail_list:
                        future = executor.submit(detail_requests, s)
                        futures.append(future)
                        duplicate_detail_list.append(s['url'])
                except queue.Empty:
                    break
            # 等待所有任务完成
            concurrent.futures.wait(futures)

        logger.info('开始导出数据。。。')
        datas_list = []
        while True:
            try:
                datas_list.append(self.details_queue.get_nowait())
            except queue.Empty:
                break

        self.df = pd.DataFrame(datas_list)
        return self


class Spider36:
    def __init__(self, thread_num=3):
        """
        eg:
            start_time='2025-05-23'
            end_time='2025-08-20'
        """
        self.start_time = START_TIME
        self.end_time = END_TIME
        self.key_words = KeyWords
        self.thread_num = thread_num

        self.crawler = Crawler(crawler_type='requests')

        self.detail_requests_queue = queue.Queue()
        self.other_page_requests_queue = queue.Queue()
        self.details_queue = queue.Queue()

        self.domain_name = 'https://www.lzsggzy.com'
        self.website_name = '泸州市公共资源交易平台'
        self.fields = {
            'title': '',
            'publish_time': '',
            'source': '',
            'url': '',
            'website_name': '',
            'content': ''
        }

        self.df = None

    def master(self):
        def get_detail_requests_from_detail_list_res(detail_list_res):
            for detail in detail_list_res['result']['records']:
                """
                TODO:
                    是否记录列表页请求结果
                """
                self.detail_requests_queue.put({
                    'url': self.domain_name + detail['linkurl'],
                    'requests_type': 'get',
                    'title': deep_clean_text(detail['title']),
                    'publish_time': re.findall(r'\d{4}-\d{2}-\d{2}', detail['webdate'], flags=re.S)[0]
                })

        def key_word_search(key_word, item):
            url = 'https://www.lzsggzy.com/inteligentsearchlz/rest/esinteligentsearch/getFullTextDataNew'
            post_json = {
                "token": "",
                "pn": 0,
                "rn": "10",
                "sdt": f"{self.start_time} 00:00:00",
                "edt": f"{self.end_time} 23:59:59",
                "wd": " ",
                "inc_wd": "",
                "exc_wd": "",
                "fields": "title",
                "cnum": "006",
                "sort": "{\"webdate\":0}",
                "ssort": "title",
                "cl": 500,
                "terminal": "",
                "condition": [
                    {
                        "fieldName": "categorynum",
                        "equal": item['post_json']['channelId'],
                        "notEqual": None,
                        "equalList": None,
                        "notEqualList": None,
                        "isLike": True,
                        "likeType": 2
                    },
                    {
                        "fieldName": "titlenew",
                        "equal": key_word,  # item['key_word'],
                        "notEqual": None,
                        "equalList": None,
                        "notEqualList": None,
                        "isLike": True,
                        "likeType": 0
                    },
                ],
                "time": None,
                "highlights": "title",
                "statistics": None,
                "unionCondition": None,
                "accuracy": "",
                "noParticiple": "0",
                "searchRange": None,
                "isBusiness": "1"
            }
            res = self.crawler.get_response(
                url=url,
                requests_type='post',
                judgement=[],
                post_json=post_json,
            )
            json_res = json.loads(json.loads(res)['content'])

            get_detail_requests_from_detail_list_res(json_res)

            total_count = int(json_res['result']['totalcount'])
            each_page_num = 10
            if total_count > each_page_num:
                for page_num in range(1, math.ceil(total_count / each_page_num) + 1):
                    new_post_json = deepcopy(post_json)
                    new_post_json.update({
                        'pn': page_num * each_page_num
                    })
                    self.other_page_requests_queue.put({
                        'url': url,
                        'requests_type': 'post',
                        'judgement': [],
                        'post_json': new_post_json
                    })

        def other_pages_requests(item):
            res = self.crawler.get_response(
                url=item['url'],
                requests_type=item['requests_type'],
                judgement=item['judgement'],
                post_json=item['post_json']
            )

            json_res = json.loads(json.loads(res)['content'])

            get_detail_requests_from_detail_list_res(json_res)

        def detail_requests(item):
            res = self.crawler.get_response(
                url=item['url'],
                requests_type=item['requests_type'],
            )
            selector = parsel.Selector(res)
            content = content_parser.replace_p_tag(
                html_content=selector.xpath('//*[@class="ewb-results-content"]').get()
            )
            data_out = {
                '标题': item['title'],
                '时间': item['publish_time'],
                '来源': '',
                '链接': item['url'],
                '所在网站': self.website_name,
                '正文': content.lstrip('中华人民共和国').strip(),
            }
            self.details_queue.put(data_out)

        # 启动线程池，根据模块、关键字搜索
        logger.info('开始根据关键字搜索。。。')
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.thread_num) as executor:
            futures = []
            channel_list = [
                {
                    'channel_name': '工程建设',
                    'post_json': {
                        "channelId": "004001001"
                    },
                },
                {
                    'channel_name': '政府采购',
                    'post_json': {
                        "channelId": "005001001"
                    },
                },
            ]
            for search_args in channel_list:
                for s in self.key_words:
                    # search_args['key_word'] = s
                    future = executor.submit(
                        key_word_search,
                        s, search_args
                    )
                    futures.append(future)

            # 等待所有任务完成
            concurrent.futures.wait(futures)

        # 启动线程池，分页请求
        logger.info(f'开始请求分页，total: {self.other_page_requests_queue.qsize()}')
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.thread_num) as executor:
            futures = []
            while True:
                try:
                    s = self.other_page_requests_queue.get_nowait()
                    future = executor.submit(other_pages_requests, s)
                    futures.append(future)
                except queue.Empty:
                    break
            # 等待所有任务完成
            concurrent.futures.wait(futures)

        # 启动线程池，详情页请求清洗
        logger.info(f'开始请求详情页，total: {self.detail_requests_queue.qsize()}')
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.thread_num) as executor:
            futures = []
            duplicate_detail_list = []
            while True:
                try:
                    s = self.detail_requests_queue.get_nowait()
                    if s['url'] not in duplicate_detail_list:
                        future = executor.submit(detail_requests, s)
                        futures.append(future)
                        duplicate_detail_list.append(s['url'])
                except queue.Empty:
                    break
            # 等待所有任务完成
            concurrent.futures.wait(futures)

        logger.info('开始导出数据。。。')
        datas_list = []
        while True:
            try:
                datas_list.append(self.details_queue.get_nowait())
            except queue.Empty:
                break

        self.df = pd.DataFrame(datas_list)
        return self


# TODO content清洗需优化
class Spider37:
    def __init__(self, thread_num=3):
        """
        eg:
            start_time='2025-05-23'
            end_time='2025-08-20'
        """
        self.start_time = START_TIME
        self.end_time = END_TIME
        self.key_words = KeyWords
        self.thread_num = thread_num

        self.crawler = Crawler(crawler_type='requests')

        self.detail_requests_queue = queue.Queue()
        self.other_page_requests_queue = queue.Queue()
        self.details_queue = queue.Queue()

        self.domain_name = 'https://www.dyggzy.com'
        self.website_name = '德阳市公共资源交易平台'
        self.fields = {
            'website_name': '',
            'url': '',
            'title': '',
            'publish_time': '',
            'source': '',
            'content': ''
        }

        self.df = None

    def master(self):
        def get_detail_requests_from_detail_list_res(detail_list_res, item):
            for detail in detail_list_res['data']:
                """
                TODO:
                    是否记录列表页请求结果
                """
                self.detail_requests_queue.put({
                    'url': fr"{self.domain_name}/commonDetail?id={detail['id']}&type={item['params']['menuCode']}&name={detail['busname']}",
                    'real_url': r"https://www.dyggzy.com/api/portal/firstDetail/" + detail['id'] + r'?_={}&id=' +
                                detail['id'],
                    'requests_type': 'get',
                })

        def key_word_search(key_word, item):
            url = fr"https://www.dyggzy.com/api/portal/pub/showJyxxContent/{item['params']['menuCode']}"
            params = {
                '_': get_now_time(),
                'areaCodeFlag': '1',
                'page': '0',
                'pageSize': '10',
                'keyname': key_word,
                'startTime': self.start_time,
                'endTime': self.end_time,
            }
            params.update(item['params'])
            res = self.crawler.get_response(
                url=url,
                requests_type='get',
                judgement=[],
                params=params,
            )

            json_res = json.loads(res)

            get_detail_requests_from_detail_list_res(json_res, item)

            total_count = int(json_res['count'])
            each_page_num = 10
            if total_count > each_page_num:
                for page_num in range(1, math.ceil(total_count / each_page_num) + 1):
                    new_params = deepcopy(params)
                    new_params.update({
                        'page': page_num
                    })
                    self.other_page_requests_queue.put({
                        'url': url,
                        'requests_type': 'get',
                        'judgement': [],
                        'params': new_params,
                        'item': item
                    })

        def other_pages_requests(item):
            item['params'].update({
                '_': get_now_time(),
            })
            res = self.crawler.get_response(
                url=item['url'],
                requests_type=item['requests_type'],
                judgement=item['judgement'],
                params=item['params']
            )

            json_res = json.loads(json.loads(res)['content'])

            get_detail_requests_from_detail_list_res(json_res, item['item'])

        def detail_requests(item):
            res = self.crawler.get_response(
                url=item['real_url'].format(get_now_time()),
                requests_type=item['requests_type'],
                judgement=[]
            )
            json_res = json.loads(res)

            content = content_parser.replace_p_tag(
                html_content=json_res['data']['content']
            )

            title = deep_clean_text(json_res['data']['title'])
            source = deep_clean_text(json_res['data']['source'])

            publish_time = json_res['data']['time']
            publish_time = re.findall(r'\d{4}-\d{2}-\d{2}', publish_time)[0]

            data_out = {
                '标题': title,
                '时间': publish_time,
                '来源': source,
                '链接': item['url'],
                '所在网站': self.website_name,
                '正文': content,

            }
            self.details_queue.put(data_out)

        # 启动线程池，根据模块、关键字搜索
        logger.info('开始根据关键字搜索。。。')
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.thread_num) as executor:
            futures = []
            channel_list = [
                {
                    'channel_name': '工程建设',
                    'params': {
                        'menuTypeCode': 'JYGCJSZB',
                        'messageType': 'ZBGG',
                        'menuCode': 'JYGCJS',
                    },
                },
                {
                    'channel_name': '政府采购',
                    'params': {
                        'messageType': 'CGGG',
                        'menuCode': 'JYCG',
                    },
                },
            ]
            for search_args in channel_list:
                for s in self.key_words:
                    # search_args['key_word'] = s
                    future = executor.submit(
                        key_word_search,
                        s, search_args
                    )
                    futures.append(future)

            # 等待所有任务完成
            concurrent.futures.wait(futures)

        # 启动线程池，分页请求
        logger.info(f'开始请求分页，total: {self.other_page_requests_queue.qsize()}')
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.thread_num) as executor:
            futures = []
            while True:
                try:
                    s = self.other_page_requests_queue.get_nowait()
                    future = executor.submit(other_pages_requests, s)
                    futures.append(future)
                except queue.Empty:
                    break
            # 等待所有任务完成
            concurrent.futures.wait(futures)

        # 启动线程池，详情页请求清洗
        logger.info(f'开始请求详情页，total: {self.detail_requests_queue.qsize()}')
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.thread_num) as executor:
            futures = []
            duplicate_detail_list = []
            while True:
                try:
                    s = self.detail_requests_queue.get_nowait()
                    if s['url'] not in duplicate_detail_list:
                        future = executor.submit(detail_requests, s)
                        futures.append(future)
                        duplicate_detail_list.append(s['url'])
                except queue.Empty:
                    break
            # 等待所有任务完成
            concurrent.futures.wait(futures)

        logger.info('开始导出数据。。。')
        datas_list = []
        while True:
            try:
                datas_list.append(self.details_queue.get_nowait())
            except queue.Empty:
                break

        self.df = pd.DataFrame(datas_list)
        return self


# TODO 列表页非post请求，需根据每一页日期判断是否继续下一页请求
class Spider38:
    def __init__(self, thread_num=3):
        """
        eg:
            start_time='2025-05-23'
            end_time='2025-08-20'
        """
        self.start_time = START_TIME
        self.end_time = END_TIME
        self.key_words = KeyWords
        self.thread_num = thread_num

        self.crawler = Crawler(crawler_type='requests')

        self.detail_requests_queue = queue.Queue()
        self.other_page_requests_queue = queue.Queue()
        self.details_queue = queue.Queue()

        self.domain_name = 'https://ggjy.mianyang.cn'
        self.website_name = '绵阳市公共资源交易服务中心'
        self.fields = {
            'website_name': '',
            'url': '',
            'title': '',
            'publish_time': '',
            'source': '',
            'content': ''
        }

        self.df = None

    def master(self):
        """
        无日期筛选的表单请求：
            1.线程池启动 关键词搜索
            2.获取表单中 max_date、min_date
            3.判断执行：
                无 max_date、min_date: 无所需数据
                if max_date < self.start_time: 无所需数据
                elif min_date <= self.start_time < max_date: 获取到第一个  self.start_time < 的表单数据为止
                else: 记录当前页数据，下一页请求加入队列
        """

        def key_word_search(item):
            url = fr"{self.domain_name}/{item['channel_code']}/{item['channel_id']}/moreinfojyxx.html"
            while True:
                res = self.crawler.get_response(
                    url=url,
                    requests_type='get',
                )
                selector = parsel.Selector(res)
                max_date = content_parser.normalize_xpath(selector, '//*[@class="infor-ul"]//li[1]//a/span')
                min_date = content_parser.normalize_xpath(selector, '(//*[@class="infor-ul"]//li)[last()]//a/span')
                if (not max_date) or (not min_date):
                    break
                if datetime.strptime(max_date, '%Y-%m-%d') < datetime.strptime(self.start_time, '%Y-%m-%d'):
                    break
                elif datetime.strptime(min_date, '%Y-%m-%d') <= datetime.strptime(self.start_time,
                                                                                  '%Y-%m-%d') < datetime.strptime(
                        max_date, '%Y-%m-%d'):
                    for detail in selector.xpath('//*[@class="infor-ul"]//li'):
                        detail_date = content_parser.normalize_xpath(detail, './/a/span')
                        if datetime.strptime(self.start_time, '%Y-%m-%d') > datetime.strptime(detail_date, '%Y-%m-%d'):
                            break

                        self.detail_requests_queue.put({
                            'url': self.domain_name + content_parser.normalize_xpath(detail, './/a/@href'),
                            'requests_type': 'get',
                            'title': deep_clean_text(detail.xpath('.//a/p/text()').get('')),
                            'publish_time': detail_date
                        })
                    break

                else:
                    for detail in selector.xpath('//*[@class="infor-ul"]//li'):
                        self.detail_requests_queue.put({
                            'url': self.domain_name + content_parser.normalize_xpath(detail, './/a/@href'),
                            'requests_type': 'get',
                            'title': deep_clean_text(detail.xpath('.//a/p/text()').get('')),
                            'publish_time': content_parser.normalize_xpath(detail, './/a/span')
                        })
                    next_page_href = content_parser.normalize_xpath(selector,
                                                                    '//*[@class="wb-page-li wb-page-item wb-page-next wb-page-family wb-page-fs12"][2]//a/@href')
                    url = self.domain_name + next_page_href

        def detail_requests(item):
            # https://ggjy.mianyang.cn/projectInfo.html?infoid=53e3d686-c8c3-48d5-b88f-6db297ed14a2&categorynum=001001
            infoid = re.findall(r'[?]infoid=([\w-]+)', item['url'])[0]
            url_prime = fr"https://ggjy.mianyang.cn/EpointWebBuilder/getinfobyrelationguidaction.action?cmd=getInfolistNew&infoid={infoid}"
            res_prime = self.crawler.get_response(
                url=url_prime,
                requests_type=item['requests_type'],
                judgement=[]
            )
            json_res_prime = json.loads(json.loads(res_prime)['custom'])[0]
            res = self.crawler.get_response(
                url=self.domain_name + json_res_prime['urlpath'],
                requests_type=item['requests_type'],
                judgement=[]
            )
            # json_res = json.loads(res)
            selector = parsel.Selector(res)

            content = content_parser.replace_p_tag(
                html_content=selector.xpath('//*[@class="infor-con ewb-article-info"]').get()
            )

            source = content_parser.normalize_xpath(selector, '//*[@class="tip-text max text-overflow"]')
            source = re.findall(r'信息来源：(.*)', source)
            source = source[0] if source else ''

            data_out = {
                '标题': item['title'],
                '时间': item['publish_time'],
                '来源': source,
                '链接': item['url'],
                '所在网站': self.website_name,
                '正文': content,

            }
            self.details_queue.put(data_out)

        # 启动线程池，根据模块、关键字搜索
        logger.info('开始根据关键字搜索。。。')
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.thread_num) as executor:
            futures = []
            channel_list = [
                {
                    'channel_name': '工程建设',
                    'channel_code': 'jsgc',
                    'channel_id': '001001',
                }
            ]
            for search_args in channel_list:
                future = executor.submit(
                    key_word_search,
                    search_args
                )
                futures.append(future)

            # 等待所有任务完成
            concurrent.futures.wait(futures)

        # 启动线程池，详情页请求清洗
        logger.info(f'开始请求详情页，total: {self.detail_requests_queue.qsize()}')
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.thread_num) as executor:
            futures = []
            duplicate_detail_list = []
            while True:
                try:
                    s = self.detail_requests_queue.get_nowait()
                    if (s['url'] not in duplicate_detail_list) and [key_word for key_word in self.key_words if
                                                                    key_word in s['title']]:
                        future = executor.submit(detail_requests, s)
                        futures.append(future)
                        duplicate_detail_list.append(s['url'])
                except queue.Empty:
                    break
            logger.info(f'去重后详情页，total: {len(duplicate_detail_list)}')
            # 等待所有任务完成
            concurrent.futures.wait(futures)

        logger.info('开始导出数据。。。')
        datas_list = []
        while True:
            try:
                datas_list.append(self.details_queue.get_nowait())
            except queue.Empty:
                break

        self.df = pd.DataFrame(datas_list)
        return self


# TODO 列表页非post请求，需根据每一页日期判断是否继续下一页请求
class Spider39:
    def __init__(self, thread_num=3):
        """
        eg:
            start_time='2025-05-23'
            end_time='2025-08-20'
        """
        self.start_time = START_TIME
        self.end_time = END_TIME
        self.key_words = KeyWords
        self.thread_num = thread_num

        self.crawler = Crawler(crawler_type='requests')

        self.detail_requests_queue = queue.Queue()
        self.other_page_requests_queue = queue.Queue()
        self.details_queue = queue.Queue()

        self.domain_name = 'https://www.gyggzyjy.cn'
        self.website_name = '广元市公共资源交易信息中心网站'
        self.fields = {
            'website_name': '',
            'url': '',
            'title': '',
            'publish_time': '',
            'source': '',
            'content': ''
        }

        self.df = None

    def master(self):
        """
        无日期筛选的表单请求：
            1.线程池启动 关键词搜索
            2.获取表单中 max_date、min_date
            3.判断执行：
                无 max_date、min_date: 无所需数据
                if max_date < self.start_time: 无所需数据
                elif min_date <= self.start_time < max_date: 获取到第一个  self.start_time < 的表单数据为止
                else: 记录当前页数据，下一页请求加入队列
        """

        def key_word_search(item):
            url = fr"{self.domain_name}/ggfwpt/012001/{item['search_url']}/about.html"
            while True:
                res = self.crawler.get_response(
                    url=url,
                    requests_type='get',
                )
                selector = parsel.Selector(res)
                max_date = content_parser.normalize_xpath(selector, '//*[@class="wb-data-item"]//li[1]/span')
                min_date = content_parser.normalize_xpath(selector, '(//*[@class="wb-data-item"]//li)[last()]/span')
                if (not max_date) or (not min_date):
                    break
                if datetime.strptime(max_date, '%Y-%m-%d') < datetime.strptime(self.start_time, '%Y-%m-%d'):
                    break
                elif datetime.strptime(min_date, '%Y-%m-%d') <= datetime.strptime(self.start_time,
                                                                                  '%Y-%m-%d') < datetime.strptime(
                        max_date, '%Y-%m-%d'):
                    for detail in selector.xpath('//*[@class="wb-data-item"]//li'):
                        detail_date = content_parser.normalize_xpath(detail, './span')
                        if datetime.strptime(self.start_time, '%Y-%m-%d') > datetime.strptime(detail_date, '%Y-%m-%d'):
                            break

                        self.detail_requests_queue.put({
                            'url': self.domain_name + content_parser.normalize_xpath(detail, './/a/@href'),
                            'requests_type': 'get',
                            'title': deep_clean_text(detail.xpath('.//a/@title').get('')),
                            'publish_time': detail_date
                        })
                    break

                else:
                    for detail in selector.xpath('//*[@class="wb-data-item"]//li'):
                        detail_date = content_parser.normalize_xpath(detail, './span')
                        self.detail_requests_queue.put({
                            'url': self.domain_name + content_parser.normalize_xpath(detail, './/a/@href'),
                            'requests_type': 'get',
                            'title': deep_clean_text(detail.xpath('.//a/@title').get('')),
                            'publish_time': detail_date
                        })
                    next_page_href = content_parser.normalize_xpath(selector,
                                                                    '//*[@class="ewb-page-li ewb-page-hover"][2]//a/@href')
                    url = self.domain_name + next_page_href

        def detail_requests(item):
            # https://ggjy.mianyang.cn/projectInfo.html?infoid=53e3d686-c8c3-48d5-b88f-6db297ed14a2&categorynum=001001
            # infoid = re.findall(r'[?]infoid=([\w-]+)', item['url'])[0]
            # url_prime = fr"https://ggjy.mianyang.cn/EpointWebBuilder/getinfobyrelationguidaction.action?cmd=getInfolistNew&infoid={infoid}"
            # res_prime = self.crawler.get_response(
            #     url=url_prime,
            #     requests_type=item['requests_type'],
            #     judgement=[]
            # )
            # json_res_prime = json.loads(json.loads(res_prime)['custom'])[0]
            res = self.crawler.get_response(
                url=item['url'],  # self.domain_name + json_res_prime['urlpath'],
                requests_type=item['requests_type'],
                judgement=[]
            )
            # json_res = json.loads(res)
            selector = parsel.Selector(res)

            content = content_parser.replace_p_tag(
                html_content=selector.xpath('//*[@class="ewb-con-bd"]').get()
            )

            # source = content_parser.normalize_xpath(selector, '//*[@class="tip-text max text-overflow"]')
            # source = re.findall(r'信息来源：(.*)', source)
            # source = source[0] if source else ''

            data_out = {
                '标题': item['title'],
                '时间': item['publish_time'],
                '来源': '',
                '链接': item['url'],
                '所在网站': self.website_name,
                '正文': content,

            }
            self.details_queue.put(data_out)

        # 启动线程池，根据模块、关键字搜索
        logger.info('开始根据关键字搜索。。。')
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.thread_num) as executor:
            futures = []
            channel_list = [
                {
                    'channel_name': '建设工程',
                    'search_url': '012001001/012001001001',
                },
                {
                    'channel_name': '国企采购',
                    'search_url': '012001016/012001016001',
                }
            ]
            for search_args in channel_list:
                future = executor.submit(
                    key_word_search,
                    search_args
                )
                futures.append(future)

            # 等待所有任务完成
            concurrent.futures.wait(futures)

        # 启动线程池，详情页请求清洗
        logger.info(f'开始请求详情页，total: {self.detail_requests_queue.qsize()}')
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.thread_num) as executor:
            futures = []
            duplicate_detail_list = []
            while True:
                try:
                    s = self.detail_requests_queue.get_nowait()
                    if (s['url'] not in duplicate_detail_list) and [key_word for key_word in self.key_words if
                                                                    key_word in s['title']]:
                        future = executor.submit(detail_requests, s)
                        futures.append(future)
                        duplicate_detail_list.append(s['url'])
                except queue.Empty:
                    break
            logger.info(f'去重后详情页，total: {len(duplicate_detail_list)}')
            # 等待所有任务完成
            concurrent.futures.wait(futures)

        logger.info('开始导出数据。。。')
        datas_list = []
        while True:
            try:
                datas_list.append(self.details_queue.get_nowait())
            except queue.Empty:
                break

        self.df = pd.DataFrame(datas_list)
        return self


# TODO 列表页非post请求，需根据每一页日期判断是否继续下一页请求
class Spider40:
    def __init__(self, thread_num=3):
        """
        eg:
            start_time='2025-05-23'
            end_time='2025-08-20'
        """
        self.start_time = START_TIME
        self.end_time = END_TIME
        self.key_words = KeyWords
        self.thread_num = thread_num

        self.crawler = Crawler(crawler_type='requests')

        self.detail_requests_queue = queue.Queue()
        self.other_page_requests_queue = queue.Queue()
        self.details_queue = queue.Queue()

        self.domain_name = 'http://www.snsggzy.com'
        self.website_name = '遂宁市公共资源交易网'
        self.fields = {
            'website_name': '',
            'url': '',
            'title': '',
            'publish_time': '',
            'source': '',
            'content': ''
        }

        self.df = None

    def master(self):
        """
        无日期筛选的表单请求：
            1.线程池启动 关键词搜索
            2.获取表单中 max_date、min_date
            3.判断执行：
                无 max_date、min_date: 无所需数据
                if max_date < self.start_time: 无所需数据
                elif min_date <= self.start_time < max_date: 获取到第一个  self.start_time < 的表单数据为止
                else: 记录当前页数据，下一页请求加入队列
        """

        def key_word_search(key_word, item):
            url = fr"http://www.snsggzy.com/JyWeb/JYXX/List_{item['search_url']}"
            params = {
                'searchText': key_word,
                'pageIndex': 1,
                'pageSize': '15',
            }
            params.update(item['params'])
            while True:
                res = self.crawler.get_response(
                    url=url,
                    requests_type='get',
                    params=params,
                    judgement=[],
                )

                selector = parsel.Selector(res)
                max_date = content_parser.normalize_xpath(selector, '(//*[@class="right_new1"]//li[1]/a/span)[last()]')
                min_date = content_parser.normalize_xpath(selector,
                                                          '((//*[@class="right_new1"]//li)[last()]/a/span)[last()]')
                if (not max_date) or (not min_date):
                    break
                if datetime.strptime(max_date, '%Y-%m-%d') < datetime.strptime(self.start_time, '%Y-%m-%d'):
                    break
                elif datetime.strptime(min_date, '%Y-%m-%d') <= datetime.strptime(self.start_time,
                                                                                  '%Y-%m-%d') < datetime.strptime(
                        max_date, '%Y-%m-%d'):
                    for detail in selector.xpath('//*[@class="right_new1"]//li'):
                        detail_date = content_parser.normalize_xpath(detail, '(./a/span)[last()]')
                        if datetime.strptime(self.start_time, '%Y-%m-%d') > datetime.strptime(detail_date, '%Y-%m-%d'):
                            break

                        self.detail_requests_queue.put({
                            'url': self.domain_name + content_parser.normalize_xpath(detail, './/a/@href'),
                            'requests_type': 'get',
                            'title': deep_clean_text(detail.xpath('.//a/@title').get('')),
                            'publish_time': detail_date
                        })
                    break

                else:
                    for detail in selector.xpath('//*[@class="right_new1"]//li'):
                        detail_date = content_parser.normalize_xpath(detail, '(./a/span)[last()]')
                        self.detail_requests_queue.put({
                            'url': self.domain_name + content_parser.normalize_xpath(detail, './/a/@href'),
                            'requests_type': 'get',
                            'title': deep_clean_text(detail.xpath('.//a/@title').get('')),
                            'publish_time': detail_date
                        })

                    params.update({
                        'pageIndex': params['pageIndex'] + 1
                    })

        def detail_requests(item):
            # https://ggjy.mianyang.cn/projectInfo.html?infoid=53e3d686-c8c3-48d5-b88f-6db297ed14a2&categorynum=001001
            # infoid = re.findall(r'[?]infoid=([\w-]+)', item['url'])[0]
            # url_prime = fr"https://ggjy.mianyang.cn/EpointWebBuilder/getinfobyrelationguidaction.action?cmd=getInfolistNew&infoid={infoid}"
            # res_prime = self.crawler.get_response(
            #     url=url_prime,
            #     requests_type=item['requests_type'],
            #     judgement=[]
            # )
            # json_res_prime = json.loads(json.loads(res_prime)['custom'])[0]
            res = self.crawler.get_response(
                url=item['url'],  # self.domain_name + json_res_prime['urlpath'],
                requests_type=item['requests_type'],
                judgement=[]
            )
            # json_res = json.loads(res)
            selector = parsel.Selector(res)

            content = content_parser.replace_p_tag(
                html_content=selector.xpath('//*[@class="news_nr"]').get()
            )

            # source = content_parser.normalize_xpath(selector, '//*[@class="tip-text max text-overflow"]')
            # source = re.findall(r'信息来源：(.*)', source)
            # source = source[0] if source else ''

            data_out = {
                '标题': item['title'],
                '时间': item['publish_time'],
                '来源': '',
                '链接': item['url'],
                '所在网站': self.website_name,
                '正文': content,

            }
            self.details_queue.put(data_out)

        # 启动线程池，根据模块、关键字搜索
        logger.info('开始根据关键字搜索。。。')
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.thread_num) as executor:
            futures = []
            channel_list = [
                {
                    'channel_name': '建设工程',
                    'search_url': 'JSGC',
                    'params': {
                        'subtype': '210',
                        'subtype2': '210010',
                    }
                },
                {
                    'channel_name': '政府采购',
                    'search_url': 'ZFCG',
                    'params': {
                        'subtype': '210',
                        'subtype2': '210010',
                    }
                }
            ]
            for search_args in channel_list:
                for s in self.key_words:
                    future = executor.submit(
                        key_word_search,
                        s, search_args
                    )
                    futures.append(future)

            # 等待所有任务完成
            concurrent.futures.wait(futures)

        # 启动线程池，详情页请求清洗
        logger.info(f'开始请求详情页，total: {self.detail_requests_queue.qsize()}')
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.thread_num) as executor:
            futures = []
            duplicate_detail_list = []
            while True:
                try:
                    s = self.detail_requests_queue.get_nowait()
                    if (s['url'] not in duplicate_detail_list) and [key_word for key_word in self.key_words if
                                                                    key_word in s['title']]:
                        future = executor.submit(detail_requests, s)
                        futures.append(future)
                        duplicate_detail_list.append(s['url'])
                except queue.Empty:
                    break
            logger.info(f'去重后详情页，total: {len(duplicate_detail_list)}')
            # 等待所有任务完成
            concurrent.futures.wait(futures)

        logger.info('开始导出数据。。。')
        datas_list = []
        while True:
            try:
                datas_list.append(self.details_queue.get_nowait())
            except queue.Empty:
                break

        self.df = pd.DataFrame(datas_list)
        return self


class Spider41:
    def __init__(self, thread_num=3):
        """
        eg:
            start_time='2025-05-23'
            end_time='2025-08-20'
        """
        self.start_time = START_TIME
        self.end_time = END_TIME
        self.key_words = KeyWords
        self.thread_num = thread_num

        self.crawler = Crawler(crawler_type='requests')

        self.detail_requests_queue = queue.Queue()
        self.other_page_requests_queue = queue.Queue()
        self.details_queue = queue.Queue()

        self.domain_name = 'http://www.njsggzy.cn:180'
        self.website_name = '内江市公共资源交易平台'
        self.fields = {
            'website_name': '',
            'url': '',
            'title': '',
            'publish_time': '',
            'source': '',
            'content': ''
        }
        self.df = None

    def master(self):
        def get_detail_requests_from_detail_list_res(detail_list_res):
            for detail in detail_list_res['records']:
                """
                TODO:
                    是否记录列表页请求结果
                """
                self.detail_requests_queue.put({
                    'url': self.domain_name + detail['href'],
                    'requests_type': 'get',
                    'title': deep_clean_text(detail['title']),
                    'publish_time': detail['infodate']
                })

        def key_word_search(key_word, item):
            url = 'http://www.njsggzy.cn:180/EpointWebBuilder/tradeInfoSearchAction.action'
            params = {
                'cmd': 'getList',
                'xiaqucode': '',
                'siteguid': '7eb5f7f1-9041-43ad-8e13-8fcb82ea831a',
                'categorynum': item['params']['channelId'],
                'wd': key_word,
                'sdt': self.start_time,
                'edt': self.end_time,
                'pageIndex': '1',
                'pageSize': '15',
            }
            res = self.crawler.get_response(
                url=url,
                requests_type='get',
                judgement=[],
                params=params
            )

            json_res = json.loads(json.loads(res)['custom'])

            get_detail_requests_from_detail_list_res(json_res)

            total_count = int(json_res['totalcount'])
            each_page_num = 15
            if total_count > each_page_num:
                for page_num in range(2, math.ceil(total_count / each_page_num) + 1):
                    new_params = deepcopy(params)
                    new_params.update({
                        'pageIndex': str(page_num)
                    })
                    self.other_page_requests_queue.put({
                        'url': url,
                        'requests_type': 'get',
                        'judgement': [],
                        'params': new_params
                    })

        def other_pages_requests(item):
            res = self.crawler.get_response(
                url=item['url'],
                requests_type=item['requests_type'],
                judgement=item['judgement'],
                params=item['params']
            )
            json_res = json.loads(json.loads(res)['custom'])

            get_detail_requests_from_detail_list_res(json_res)

        def detail_requests(item):
            res = self.crawler.get_response(
                url=item['url'],
                requests_type=item['requests_type'],
            )

            selector = parsel.Selector(res)
            content = content_parser.replace_p_tag(
                html_content=selector.xpath('//*[@id="news_content"]').get()
            )
            data_out = {
                '标题': item['title'],
                '时间': item['publish_time'],
                '来源': '',
                '链接': item['url'],
                '所在网站': self.website_name,
                '正文': content,

            }
            self.details_queue.put(data_out)

        # 启动线程池，根据模块、关键字搜索
        logger.info('开始根据关键字搜索。。。')
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.thread_num) as executor:
            futures = []
            channel_list = [
                {
                    'channel_name': '工程建设',
                    'params': {
                        "channelId": "006001001",
                    },
                },
                {
                    'channel_name': '其他项目交易',
                    'params': {
                        "channelId": "006002001",
                    },
                },
                {
                    'channel_name': '政府采购（进场交易）',
                    'params': {
                        "channelId": "006003001",
                    },
                },
                {
                    'channel_name': '政府采购(网上竞价和商城/场直购)',
                    'params': {
                        "channelId": "006004001",
                    },
                },
            ]
            for search_args in channel_list:
                for s in self.key_words:
                    future = executor.submit(
                        key_word_search,
                        s, search_args
                    )
                    futures.append(future)

            # 等待所有任务完成
            concurrent.futures.wait(futures)

        # 启动线程池，分页请求
        logger.info(f'开始请求分页，total: {self.other_page_requests_queue.qsize()}')
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.thread_num) as executor:
            futures = []
            while True:
                try:
                    s = self.other_page_requests_queue.get_nowait()
                    future = executor.submit(other_pages_requests, s)
                    futures.append(future)
                except queue.Empty:
                    break
            # 等待所有任务完成
            concurrent.futures.wait(futures)

        # 启动线程池，详情页请求清洗
        logger.info(f'开始请求详情页，total: {self.detail_requests_queue.qsize()}')

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.thread_num) as executor:
            futures = []
            duplicate_detail_list = []
            while True:
                try:
                    s = self.detail_requests_queue.get_nowait()
                    if s['url'] not in duplicate_detail_list:
                        future = executor.submit(detail_requests, s)
                        futures.append(future)
                        duplicate_detail_list.append(s['url'])
                except queue.Empty:
                    break
            # 等待所有任务完成
            concurrent.futures.wait(futures)

        logger.info('开始导出数据。。。')
        datas_list = []
        while True:
            try:
                datas_list.append(self.details_queue.get_nowait())
            except queue.Empty:
                break

        self.df = pd.DataFrame(datas_list)
        return self


class Spider42:
    def __init__(self, thread_num=3):
        """
        eg:
            start_time='2025-05-23'
            end_time='2025-08-20'
        """
        self.start_time = START_TIME
        self.end_time = END_TIME
        self.key_words = KeyWords
        self.thread_num = thread_num

        self.crawler = Crawler(crawler_type='requests')

        self.detail_requests_queue = queue.Queue()
        self.other_page_requests_queue = queue.Queue()
        self.details_queue = queue.Queue()

        self.domain_name = 'https://www.lsggzy.com.cn'
        self.website_name = '乐山公共资源交易平台'
        self.fields = {
            'website_name': '',
            'url': '',
            'title': '',
            'publish_time': '',
            'source': '',
            'content': ''
        }

        self.df = None

    def master(self):
        def get_detail_requests_from_detail_list_res(detail_list_res):
            for detail in detail_list_res:
                """
                TODO:
                    是否记录列表页请求结果
                """
                self.detail_requests_queue.put({
                    'url': self.domain_name + content_parser.normalize_xpath(detail, './/a/@href'),
                    'requests_type': 'get',
                    'publish_time': content_parser.normalize_xpath(detail, './/a/span[1]'),
                })

        def key_word_search(key_word, item):
            url = r"https://www.lsggzy.com.cn/pub/infoSearch"
            post_data = {
                'rootCode': 'jyxx',
                'areaCode': '',
                'page': '',
                'title': key_word,
                'pubStime': self.start_time,
                'pubEtime': self.end_time,
                '_csrf': '98ea466e-aafa-4b34-9e4c-57bc5ae421f7',
            }
            post_data.update(item['post_data'])
            res = self.crawler.get_response(
                url=url,
                requests_type='post',
                judgement=[],
                post_data=post_data,
            )
            selector = parsel.Selector(res)

            get_detail_requests_from_detail_list_res(
                selector.xpath('//*[@class="MainUl"]//li')
            )

            page_judgement = selector.xpath('//*[@class="MainPage"]/button[contains(text(), "下一页")]')
            if page_judgement:
                end_page = content_parser.normalize_xpath(
                    selector,
                    '//*[@class="MainPage"]/button[contains(text(), "尾页")]/@onclick'
                )
                if not end_page:
                    end_page = content_parser.normalize_xpath(
                        selector,
                        '(//*[@class="MainPage"]//li)[last()]//button/@onclick'
                    )
                end_page_num = int(re.findall(r'\d+', end_page)[0])
                for page_num in range(1, end_page_num + 1):
                    new_post_data = deepcopy(post_data)
                    new_post_data.update({
                        'page': page_num
                    })
                    self.other_page_requests_queue.put({
                        'url': url,
                        'requests_type': 'post',
                        'judgement': [],
                        'post_data': new_post_data,
                        'item': item
                    })

        def other_pages_requests(item):
            res = self.crawler.get_response(
                url=item['url'],
                requests_type=item['requests_type'],
                judgement=item['judgement'],
                post_data=item['post_data']
            )

            selector = parsel.Selector(res)

            get_detail_requests_from_detail_list_res(
                selector.xpath('//*[@class="MainUl"]//li')
            )

        def detail_requests(item):
            res = self.crawler.get_response(
                url=item['url'],
                requests_type=item['requests_type'],
                judgement=[]
            )
            selector = parsel.Selector(res)

            content = content_parser.replace_p_tag(
                html_content=selector.xpath('//*[@class="Detail-text"]').get()
            )

            title = content_parser.normalize_xpath(selector, '//*[@name="ArticleTitle"]/@content')

            # source = deep_clean_text(json_res['data']['source'])

            # publish_time = json_res['data']['time']
            # publish_time = re.findall(r'\d{4}-\d{2}-\d{2}', publish_time)[0]

            data_out = {
                '标题': title,
                '时间': item['publish_time'],
                '来源': '',
                '链接': item['url'],
                '所在网站': self.website_name,
                '正文': content,

            }
            self.details_queue.put(data_out)

        # 启动线程池，根据模块、关键字搜索
        logger.info('开始根据关键字搜索。。。')
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.thread_num) as executor:
            futures = []
            channel_list = [
                {
                    'channel_name': '工程建设',
                    'post_data': {
                        'menuCode': 'JYGCJS',
                        'typeCode': 'ZBGG',
                    },
                },
                {
                    'channel_name': '政府采购',
                    'post_data': {
                        'messageType': 'JYZFCG',
                        'menuCode': 'CGGG',
                    },
                },
                {
                    'channel_name': '国企阳光采购',
                    'post_data': {
                        'messageType': 'GQYGCG',
                        'menuCode': 'ZBGG',
                    },
                },
            ]
            for search_args in channel_list:
                for s in self.key_words:
                    # search_args['key_word'] = s
                    future = executor.submit(
                        key_word_search,
                        s, search_args
                    )
                    futures.append(future)

            # 等待所有任务完成
            concurrent.futures.wait(futures)

        # 启动线程池，分页请求
        logger.info(f'开始请求分页，total: {self.other_page_requests_queue.qsize()}')
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.thread_num) as executor:
            futures = []
            while True:
                try:
                    s = self.other_page_requests_queue.get_nowait()
                    future = executor.submit(other_pages_requests, s)
                    futures.append(future)
                except queue.Empty:
                    break
            # 等待所有任务完成
            concurrent.futures.wait(futures)

        # 启动线程池，详情页请求清洗
        logger.info(f'开始请求详情页，total: {self.detail_requests_queue.qsize()}')
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.thread_num) as executor:
            futures = []
            duplicate_detail_list = []
            while True:
                try:
                    s = self.detail_requests_queue.get_nowait()
                    if s['url'] not in duplicate_detail_list:
                        future = executor.submit(detail_requests, s)
                        futures.append(future)
                        duplicate_detail_list.append(s['url'])
                except queue.Empty:
                    break
            # 等待所有任务完成
            concurrent.futures.wait(futures)

        logger.info('开始导出数据。。。')
        datas_list = []
        while True:
            try:
                datas_list.append(self.details_queue.get_nowait())
            except queue.Empty:
                break

        self.df = pd.DataFrame(datas_list)
        return self


class Spider43:
    def __init__(self, thread_num=3):
        """
        eg:
            start_time='2025-05-23'
            end_time='2025-08-20'
        """
        self.start_time = START_TIME
        self.end_time = END_TIME
        self.key_words = KeyWords
        self.thread_num = thread_num

        self.crawler = Crawler(crawler_type='requests')

        self.detail_requests_queue = queue.Queue()
        self.other_page_requests_queue = queue.Queue()
        self.details_queue = queue.Queue()

        self.domain_name = 'https://www.scncggzy.com.cn'
        self.website_name = '南充公共资源交易中心'
        self.fields = {
            'website_name': '',
            'url': '',
            'title': '',
            'publish_time': '',
            'source': '',
            'content': ''
        }

        self.df = None

    def master(self):
        def get_detail_requests_from_detail_list_res(detail_list_res):
            for detail in detail_list_res['result']['records']:
                """
                TODO:
                    是否记录列表页请求结果
                """
                self.detail_requests_queue.put({
                    'url': self.domain_name + detail['linkurl'],
                    'requests_type': 'get',
                    'title': deep_clean_text(detail['title']),
                    'publish_time': re.findall(r'\d{4}-\d{2}-\d{2}', detail['webdate'], flags=re.S)[0]
                })

        def key_word_search(key_word, item):
            url = 'https://www.scncggzy.com.cn/inteligentsearch/rest/esinteligentsearch/getFullTextDataNew'
            post_json = {
                "token": "",
                "pn": 0,
                "rn": 15,
                "sdt": "",
                "edt": "",
                "wd": key_word,
                "inc_wd": "",
                "exc_wd": "",
                "fields": "title",
                "cnum": "003",
                "sort": "{\"webdate\":\"0\"}",
                "ssort": "title",
                "cl": 500,
                "terminal": "",
                "condition": [
                    {
                        "fieldName": "categorynum",
                        "equal": item['post_json']['channelId'],
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
                        "startTime": f"{self.start_time} 00:00:00",
                        "endTime": f"{self.end_time} 23:59:59"
                    }
                ],
                "highlights": "citycode",
                "statistics": None,
                "unionCondition": None,
                "accuracy": "",
                "noParticiple": "0",
                "searchRange": None,
                "isBusiness": "1"
            }

            # self.crawler.headers.update({
            #     'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            # })

            res = self.crawler.get_response(
                url=url,
                requests_type='post',
                judgement=[],
                post_json=post_json
                # post_data=json.dumps(post_data),
            )
            json_res = json.loads(res)

            get_detail_requests_from_detail_list_res(json_res)

            total_count = int(json_res['result']['totalcount'])
            each_page_num = 15
            if total_count > each_page_num:
                for page_num in range(1, math.ceil(total_count / each_page_num) + 1):
                    new_post_json = deepcopy(post_json)
                    new_post_json.update({
                        'pn': page_num * each_page_num
                    })
                    self.other_page_requests_queue.put({
                        'url': url,
                        'requests_type': 'post',
                        'judgement': [],
                        'post_json': new_post_json
                    })

        def other_pages_requests(item):
            res = self.crawler.get_response(
                url=item['url'],
                requests_type=item['requests_type'],
                judgement=item['judgement'],
                post_json=item['post_json']
            )

            json_res = json.loads(res)

            get_detail_requests_from_detail_list_res(json_res)

        def detail_requests(item):
            res = self.crawler.get_response(
                url=item['url'],
                requests_type=item['requests_type'],
            )
            selector = parsel.Selector(res)

            extra_remove_targets = {
                'class': ["news-article-info", "news-article-tt"]
            }
            content = content_parser.replace_p_tag(
                html_content=selector.xpath('//*[@class="news-article"]').get(),
                extra_remove_targets=extra_remove_targets
            )

            # title = content_parser.normalize_xpath(selector, '//*[@name="ArticleTitle"]/@content')
            source = content_parser.normalize_xpath(selector, '//*[@id="zhuanzaicss"]')
            source = re.findall(r'【来源：(.*?)】', source)
            source = source[0].strip() if source else ''

            # publish_time = json_res['data']['time']
            # publish_time = re.findall(r'\d{4}-\d{2}-\d{2}', publish_time)[0]

            data_out = {
                '标题': item['title'],
                '时间': item['publish_time'],
                '来源': source,
                '链接': item['url'],
                '所在网站': self.website_name,
                '正文': content,

            }
            self.details_queue.put(data_out)

        # 启动线程池，根据模块、关键字搜索
        logger.info('开始根据关键字搜索。。。')
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.thread_num) as executor:
            futures = []
            channel_list = [
                {
                    'channel_name': '工程建设',
                    'post_json': {
                        "channelId": "001002001"
                    },
                },
                {
                    'channel_name': '政府采购',
                    'post_json': {
                        "channelId": "001001002"
                    },
                },
            ]
            for search_args in channel_list:
                for s in self.key_words:
                    # search_args['key_word'] = s
                    future = executor.submit(
                        key_word_search,
                        s, search_args
                    )
                    futures.append(future)

            # 等待所有任务完成
            concurrent.futures.wait(futures)

        # 启动线程池，分页请求
        logger.info(f'开始请求分页，total: {self.other_page_requests_queue.qsize()}')
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.thread_num) as executor:
            futures = []
            while True:
                try:
                    s = self.other_page_requests_queue.get_nowait()
                    future = executor.submit(other_pages_requests, s)
                    futures.append(future)
                except queue.Empty:
                    break
            # 等待所有任务完成
            concurrent.futures.wait(futures)

        # 启动线程池，详情页请求清洗
        logger.info(f'开始请求详情页，total: {self.detail_requests_queue.qsize()}')
        # del self.crawler.headers['Content-Type']
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.thread_num) as executor:
            futures = []
            duplicate_detail_list = []
            while True:
                try:
                    s = self.detail_requests_queue.get_nowait()
                    if s['url'] not in duplicate_detail_list:
                        future = executor.submit(detail_requests, s)
                        futures.append(future)
                        duplicate_detail_list.append(s['url'])
                except queue.Empty:
                    break
            # 等待所有任务完成
            concurrent.futures.wait(futures)

        logger.info('开始导出数据。。。')
        datas_list = []
        while True:
            try:
                datas_list.append(self.details_queue.get_nowait())
            except queue.Empty:
                break

        self.df = pd.DataFrame(datas_list)
        return self


# TODO 列表页，需根据每一页日期判断是否继续下一页请求
class Spider44:
    def __init__(self, thread_num=3):
        """
        eg:
            start_time='2025-05-23'
            end_time='2025-08-20'
        """
        self.start_time = START_TIME
        self.end_time = END_TIME
        self.key_words = KeyWords
        self.thread_num = thread_num

        self.crawler = Crawler(crawler_type='requests')

        self.detail_requests_queue = queue.Queue()
        self.other_page_requests_queue = queue.Queue()
        self.details_queue = queue.Queue()

        self.domain_name = 'https://ggzy.yibin.gov.cn/#/home'
        self.website_name = '宜宾市公共资源交易信息网'
        self.fields = {
            'website_name': '',
            'url': '',
            'title': '',
            'publish_time': '',
            'source': '',
            'content': ''
        }

        self.df = None

    def master(self):
        """
        无日期筛选的表单请求：
            1.线程池启动 关键词搜索
            2.获取表单中 max_date、min_date
            3.判断执行：
                无 max_date、min_date: 无所需数据
                if max_date < self.start_time: 无所需数据
                elif min_date <= self.start_time < max_date: 获取到第一个  self.start_time < 的表单数据为止
                else: 记录当前页数据，下一页请求加入队列
        """

        def key_word_search(key_word, item):
            url = "https://ggzy.yibin.gov.cn/ggfwptwebapi/Web/service"
            post_json = {
                "action": "pageTongYong_SouSuo",
                "pageIndex": 1,
                "pageSize": 10,
                "xiangMu_LeiXing": None,
                "xinXi_LeiXing": item['channel_id'],
                "title": key_word
            }
            # params.update(item['params'])
            while True:
                res = self.crawler.get_response(
                    url=url,
                    requests_type='post',
                    # params=params,
                    post_json=post_json,
                    judgement=[],
                )

                # selector = parsel.Selector(res)
                # max_date = content_parser.normalize_xpath(selector, '(//*[@class="right_new1"]//li[1]/a/span)[last()]')
                # min_date = content_parser.normalize_xpath(selector, '((//*[@class="right_new1"]//li)[last()]/a/span)[last()]')

                json_res = json.loads(res)
                max_date = re.findall(r'\d{4}-\d{2}-\d{2}', json_res['data'][0]['publish_StartTime'])[0]
                min_date = re.findall(r'\d{4}-\d{2}-\d{2}', json_res['data'][-1]['publish_StartTime'])[0]

                if (not max_date) or (not min_date):
                    break
                if datetime.strptime(max_date, '%Y-%m-%d') < datetime.strptime(self.start_time, '%Y-%m-%d'):
                    break
                elif datetime.strptime(min_date, '%Y-%m-%d') <= datetime.strptime(self.start_time,
                                                                                  '%Y-%m-%d') < datetime.strptime(
                        max_date, '%Y-%m-%d'):
                    for detail in json_res['data']:
                        detail_date = re.findall(r'\d{4}-\d{2}-\d{2}', detail['publish_StartTime'])[0]
                        if datetime.strptime(self.start_time, '%Y-%m-%d') > datetime.strptime(detail_date, '%Y-%m-%d'):
                            break
                        # https://ggzy.yibin.gov.cn/#/transactionListDetail?guid=ede7de24-8c39-4ccc-8978-923db4f72119&leiXing=102&ziLeiXing=undefined&xinXi_LaiYuan=2
                        # https://ggzy.yibin.gov.cn/#/transactionListDetail?guid=8a69cc1a98e94bf10198eac9f6cd7ad1&leiXing=201&ziLeiXing=undefined&xinXi_LaiYuan=9
                        self.detail_requests_queue.put({
                            'url': fr"https://ggzy.yibin.gov.cn/#/transactionListDetail?guid={detail['guid']}&leiXing={item['channel_id']}&ziLeiXing=undefined&xinXi_LaiYuan={detail['xinXi_LaiYuan']}",
                            'real_url': r'https://ggzy.yibin.gov.cn/ggfwptwebapi/Web/service',
                            'requests_type': 'post',
                            'post_json': {
                                'action': item['detail_action'],
                                'guid': detail['guid']
                            },
                            'title': deep_clean_text(
                                detail.get('zhaoBiao_XiangMu_Name', detail.get('xiangMu_Name'))
                            ),
                            'publish_time': detail_date,
                            'item': item
                        })
                    break

                else:
                    for detail in json_res['data']:
                        detail_date = re.findall(r'\d{4}-\d{2}-\d{2}', detail['publish_StartTime'])[0]
                        self.detail_requests_queue.put({
                            'url': fr"https://ggzy.yibin.gov.cn/#/transactionListDetail?guid={detail['guid']}&leiXing={item['channel_id']}&ziLeiXing=undefined&xinXi_LaiYuan={detail['xinXi_LaiYuan']}",
                            'real_url': r'https://ggzy.yibin.gov.cn/ggfwptwebapi/Web/service',
                            'requests_type': 'post',
                            'post_json': {
                                'action': item['detail_action'],
                                'guid': detail['guid']
                            },
                            'title': deep_clean_text(
                                detail.get('zhaoBiao_XiangMu_Name', detail.get('xiangMu_Name'))
                            ),
                            'publish_time': detail_date,
                            'item': item
                        })

                    post_json.update({
                        'pageIndex': post_json['pageIndex'] + 1
                    })

        def detail_requests(item):
            res = self.crawler.get_response(
                url=item.get('real_url', item.get('url')),  # self.domain_name + json_res_prime['urlpath'],
                requests_type=item['requests_type'],
                post_json=item['post_json'],
                judgement=[]
            )
            json_res = json.loads(res)['data']

            if item['item']['channel_name'] == '建设工程':
                json_res = json_res['zhaoBiao_GongGao']
                content_field = {
                    '1.招标条件：': json_res['ZhaoBiao_TiaoJian'].replace('\n', '\n\t'),
                    '2.项目概况与招标范围：': json_res['ZhaoBiao_FanWei'].replace('\n', '\n\t'),
                    '3.投标人资格要求：': json_res['ZiGe_YaoQiu'].replace('\n', '\n\t'),
                    '4.招标文件的获取：': fr"4.1 凡有意参加投标者，请于 {json_res['Publish_StartTime']} 至 {json_res['Publish_EndTime']} （电子招标文件的获取，不受获取截止时间限制，任何时间段均可获取），登录宜宾市公共资源交易信息网（https://ggzy.yibin.gov.cn/），凭数字证书和密码获取招标文件及其它招标资料。另，可通过本项目招标公告附件，免费获取招标文件。\n\t4.2 招标人不提供邮购招标文件服务。",
                    '5.投标文件的递交：': f"5.1 投标文件递交的截止时间（投标截止时间，下同）为 {json_res['TouBiao_EndTime']}。\n\t5.2 {json_res['DiJiao_DiDian']}\n\t5.3 逾期递交的或者未按指定方式递交或未送达指定地点的投标文件，招标人不予受理。",
                    '6.发布公告的媒介：': json_res['GongGao_MeiJie'].replace('\n', '\n\t')
                }
                content = '\n'.join([f"{key}\n\t{value}" for key, value in content_field.items()])
            elif json_res.get('shengPingTai_GongGao'):
                selector = parsel.Selector(json_res['shengPingTai_GongGao']['content'])

                content = content_parser.replace_p_tag(
                    html_content=selector.xpath('.').get()
                )
            else:
                json_res = json_res['zfcg_CaiGou_GongGao']
                # is_union = '是' if json_res['Is_Union'] else '否'
                # announcement_period = 5 if (json_res['CGFS'] in [1] or json_res['ZSType'] == 2) else 3
                # content_field = {
                #     # '': json_res['GongGao_Title'],
                #     '项目概况：': json_res['XiangMu_GaiKuang'].replace('\n', '\n\t'),
                #     '一、项目基本情况': f"项目编号：{json_res['XiangMu_No']}\t项目名称：{json_res['XiangMu_Name']}\n\t采购方式：{json_res['GongGao_LeiXing'].replace('采购公告', '')}\t预算金额：{json_res['YuSuan_JinE']}万元\n\t最高限价：{json_res['ZuiGao_XianJia']}万元\t采购需求：{json_res['CaiGou_XuQiu']}\n\t合同履行期限：{json_res['GongQi']}\t本项目是否接受联合体投标：{is_union}",
                #     '二、申请人资格要求': f"1. 满足《中华人民共和国政府采购法》第二十二条规定；\n\t2. 落实政府采购政策需满足的资格要求：{json_res['GongYingShang_ZiGe']}\n\t3. 本项目的特定资格要求：{json_res['TeDing_ZiGe_YaoQiu']}",
                #     '三、获取采购文件': f"获取时间：{json_res['BMKSSJ']}至{json_res['BMJSSJ']}，采购文件获取时间，以{json_res['HuoQu_PingTai']}记录的时间为准（下同）\n\t获取方式及地点：{json_res['HuoQu_FangShi']}采购文件只在网上发布，不再提供其他发布方式n\t售价：0元",
                #     '四、响应文件提交': f"（一）.递交投标文件（响应文件）截止时间和开标时间：{json_res['TouBiao_EndTime']}，开标地址：{json_res['KaiBiao_DiDian']}\n\t（二）.递交方式:以该项目采购文件要求为准+\n\t（三）.本次政府采购不接受邮寄的投标文件（响应文件）",
                #     '五、开启': f"时间：{json_res['TouBiao_EndTime']}\t地点：{json_res['KaiBiao_DiDian']}",
                #     '六、公告期限': f"自本公告发布之日起至少 {announcement_period} 个工作日",
                #     '七、其他补充事宜': json_res['XinXi_NeiRong'].replace('\n', '\n\t'),
                #     '八、对本次招标提出询问，请按以下方式联系': f"1.采购人信息\n\t\t名称：{json_res['CaiGouRen']}\t地址：{json_res['CaiGou_DiZhi']}\n\t\t联系人：{json_res['CaiGou_LianXiRen']}\t联系方式：{json_res['CaiGou_LianXi_FangShi']}\n\t2. 采购代理机构信息\n\t\t名称：{json_res['CaiGou_DaiLi']}\t地址：{json_res['CaiGou_DaiLi_DiZhi']}\n\t\t联系人：{json_res['CaiGou_DaiLi_LianXiRen']}\t联系方式：{json_res['CaiGou_DaiLi_LianXi_FangShi']}"
                # }
                #
                # content = '\n'.join([f"{key}\n\t{value}" for key, value in content_field.items()])
                announcement = ProcurementAnnouncement(json_res)
                content_dict = announcement.generate_content_dict()
                content = '\n'.join([f"{key}\n\t{value}" for key, value in content_dict.items()])

            # source = content_parser.normalize_xpath(selector, '//*[@class="tip-text max text-overflow"]')
            # source = re.findall(r'信息来源：(.*)', source)
            # source = source[0] if source else ''

            data_out = {
                '标题': item['title'],
                '时间': item['publish_time'],
                '来源': '',
                '链接': item['url'],
                '所在网站': self.website_name,
                '正文': content,

            }
            self.details_queue.put(data_out)

        # 启动线程池，根据模块、关键字搜索
        logger.info('开始根据关键字搜索。。。')
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.thread_num) as executor:
            futures = []
            channel_list = [
                {
                    'channel_name': '建设工程',
                    'channel_id': '102',
                    'detail_action': 'getGCJS_ZhaoBiao_GongGao'
                },
                {
                    'channel_name': '政府采购',
                    'channel_id': '201',
                    'detail_action': 'getZFCG_CaiGou_GongGao'
                }
            ]
            for search_args in channel_list:
                for s in self.key_words:
                    future = executor.submit(
                        key_word_search,
                        s, search_args
                    )
                    futures.append(future)

            # 等待所有任务完成
            concurrent.futures.wait(futures)

        # 启动线程池，详情页请求清洗
        logger.info(f'开始请求详情页，total: {self.detail_requests_queue.qsize()}')
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.thread_num) as executor:
            futures = []
            duplicate_detail_list = []
            while True:
                try:
                    s = self.detail_requests_queue.get_nowait()
                    if (s['url'] not in duplicate_detail_list) and [key_word for key_word in self.key_words if
                                                                    key_word in s['title']]:
                        future = executor.submit(detail_requests, s)
                        futures.append(future)
                        duplicate_detail_list.append(s['url'])
                except queue.Empty:
                    break
            logger.info(f'去重后详情页，total: {len(duplicate_detail_list)}')
            # 等待所有任务完成
            concurrent.futures.wait(futures)

        logger.info('开始导出数据。。。')
        datas_list = []
        while True:
            try:
                datas_list.append(self.details_queue.get_nowait())
            except queue.Empty:
                break

        self.df = pd.DataFrame(datas_list)
        return self


# TODO 列表页非post请求，需根据每一页日期判断是否继续下一页请求
class Spider45:
    def __init__(self, thread_num=3):
        """
        eg:
            start_time='2025-05-23'
            end_time='2025-08-20'
        """
        self.start_time = START_TIME
        self.end_time = END_TIME
        self.key_words = KeyWords
        self.thread_num = thread_num

        self.crawler = Crawler(crawler_type='requests')

        self.detail_requests_queue = queue.Queue()
        self.other_page_requests_queue = queue.Queue()
        self.details_queue = queue.Queue()

        self.domain_name = 'https://gasggzy.cn'
        self.website_name = '广安市公共资源交易网'
        self.fields = {
            'website_name': '',
            'url': '',
            'title': '',
            'publish_time': '',
            'source': '',
            'content': ''
        }

        self.df = None

    def master(self):
        """
        无日期筛选的表单请求：
            1.线程池启动 关键词搜索
            2.获取表单中 max_date、min_date
            3.判断执行：
                无 max_date、min_date: 无所需数据
                if max_date < self.start_time: 无所需数据
                elif min_date <= self.start_time < max_date: 获取到第一个  self.start_time < 的表单数据为止
                else: 记录当前页数据，下一页请求加入队列
        """

        def key_word_search(key_word, item):
            url = r'https://gasggzy.cn/EWB-FRONT/rest/searchaction/getlistjyxx'
            post_data = {
                'title': key_word,
                'pageIndex': 1,
                'pageSize': '15',
                'siteguid': '7eb5f7f1-9041-43ad-8e13-8fcb82ea831a',
                'categorynum': item['channel_id'],
            }
            while True:
                res = self.crawler.get_response(
                    url=url,
                    requests_type='post',
                    post_data=post_data,
                    judgement=[],
                )

                # selector = parsel.Selector(res)
                # max_date = content_parser.normalize_xpath(selector, '(//*[@class="right_new1"]//li[1]/a/span)[last()]')
                # min_date = content_parser.normalize_xpath(selector, '((//*[@class="right_new1"]//li)[last()]/a/span)[last()]')

                json_res = json.loads(res)
                max_date = json_res['infodata'][0]['infodate']
                min_date = json_res['infodata'][-1]['infodate']

                if (not max_date) or (not min_date):
                    break
                if datetime.strptime(max_date, '%Y-%m-%d') < datetime.strptime(self.start_time, '%Y-%m-%d'):
                    break
                elif datetime.strptime(min_date, '%Y-%m-%d') <= datetime.strptime(self.start_time,
                                                                                  '%Y-%m-%d') < datetime.strptime(
                        max_date, '%Y-%m-%d'):
                    for detail in json_res['infodata']:
                        detail_date = detail['infodate']
                        if datetime.strptime(self.start_time, '%Y-%m-%d') > datetime.strptime(detail_date, '%Y-%m-%d'):
                            break

                        self.detail_requests_queue.put({
                            'url': self.domain_name + detail['infourl'],
                            'requests_type': 'get',
                            'title': deep_clean_text(detail['title']),
                            'publish_time': detail_date
                        })
                    break

                else:
                    for detail in json_res['infodata']:
                        detail_date = detail['infodate']
                        self.detail_requests_queue.put({
                            'url': self.domain_name + detail['infourl'],
                            'requests_type': 'get',
                            'title': deep_clean_text(detail['title']),
                            'publish_time': detail_date
                        })

                    post_data.update({
                        'pageIndex': post_data['pageIndex'] + 1
                    })

        def detail_requests(item):
            # https://ggjy.mianyang.cn/projectInfo.html?infoid=53e3d686-c8c3-48d5-b88f-6db297ed14a2&categorynum=001001
            # infoid = re.findall(r'[?]infoid=([\w-]+)', item['url'])[0]
            # url_prime = fr"https://ggjy.mianyang.cn/EpointWebBuilder/getinfobyrelationguidaction.action?cmd=getInfolistNew&infoid={infoid}"
            # res_prime = self.crawler.get_response(
            #     url=url_prime,
            #     requests_type=item['requests_type'],
            #     judgement=[]
            # )
            # json_res_prime = json.loads(json.loads(res_prime)['custom'])[0]
            res = self.crawler.get_response(
                url=item['url'],  # self.domain_name + json_res_prime['urlpath'],
                requests_type=item['requests_type'],
                judgement=[]
            )
            # json_res = json.loads(res)
            selector = parsel.Selector(res)

            content = content_parser.replace_p_tag(
                html_content=selector.xpath('//*[@class="ewb-article-info"]').get()
            )

            source = content_parser.normalize_xpath(
                selector, '//*[@class="ewb-article-sources"]/p[contains(text(), "信息来源")]')
            source = re.findall(r'信息来源：(.*)', source)
            source = source[0] if source else ''

            data_out = {
                '标题': item['title'],
                '时间': item['publish_time'],
                '来源': source,
                '链接': item['url'],
                '所在网站': self.website_name,
                '正文': content,

            }
            self.details_queue.put(data_out)

        # 启动线程池，根据模块、关键字搜索
        logger.info('开始根据关键字搜索。。。')
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.thread_num) as executor:
            futures = []
            channel_list = [
                {
                    'channel_name': '建设工程',
                    'channel_id': '002001001'
                },
                {
                    'channel_name': '政府采购',
                    'channel_id': '002002001'
                }
            ]
            for search_args in channel_list:
                for s in self.key_words:
                    future = executor.submit(
                        key_word_search,
                        s, search_args
                    )
                    futures.append(future)

            # 等待所有任务完成
            concurrent.futures.wait(futures)

        # 启动线程池，详情页请求清洗
        logger.info(f'开始请求详情页，total: {self.detail_requests_queue.qsize()}')
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.thread_num) as executor:
            futures = []
            duplicate_detail_list = []
            while True:
                try:
                    s = self.detail_requests_queue.get_nowait()
                    if (s['url'] not in duplicate_detail_list) and [key_word for key_word in self.key_words if
                                                                    key_word in s['title']]:
                        future = executor.submit(detail_requests, s)
                        futures.append(future)
                        duplicate_detail_list.append(s['url'])
                except queue.Empty:
                    break
            logger.info(f'去重后详情页，total: {len(duplicate_detail_list)}')
            # 等待所有任务完成
            concurrent.futures.wait(futures)

        logger.info('开始导出数据。。。')
        datas_list = []
        while True:
            try:
                datas_list.append(self.details_queue.get_nowait())
            except queue.Empty:
                break

        self.df = pd.DataFrame(datas_list)
        return self


# TODO 列表页非post请求，需根据每一页日期判断是否继续下一页请求
class Spider46:
    def __init__(self, thread_num=3):
        """
        eg:
            start_time='2025-05-23'
            end_time='2025-08-20'
        """
        self.start_time = START_TIME
        self.end_time = END_TIME
        self.key_words = KeyWords
        self.thread_num = thread_num

        self.crawler = Crawler(crawler_type='requests')

        self.detail_requests_queue = queue.Queue()
        self.other_page_requests_queue = queue.Queue()
        self.details_queue = queue.Queue()

        self.domain_name = 'https://www.dzggzy.cn'
        self.website_name = '达州市公共资源交易中心'
        self.fields = {
            'website_name': '',
            'url': '',
            'title': '',
            'publish_time': '',
            'source': '',
            'content': ''
        }

        self.df = None

    def master(self):
        """
        无日期筛选的表单请求：
            1.线程池启动 关键词搜索
            2.获取表单中 max_date、min_date
            3.判断执行：
                无 max_date、min_date: 无所需数据
                if max_date < self.start_time: 无所需数据
                elif min_date <= self.start_time < max_date: 获取到第一个  self.start_time < 的表单数据为止
                else: 记录当前页数据，下一页请求加入队列
        """

        def key_word_search(key_word, item):
            url = r'https://www.dzggzy.cn/EpointWebBuilder/rest/secaction/getSecInfoListYzm'
            post_data = {
                'content': key_word,
                'pageIndex': 0,
                'pageSize': '20',
                'siteGuid': '7eb5f7f1-9041-43ad-8e13-8fcb82ea831a',
                'categoryNum': item['channel_id'],
            }
            while True:
                res = self.crawler.get_response(
                    url=url,
                    requests_type='post',
                    post_data=post_data,
                    judgement=[],
                )

                # selector = parsel.Selector(res)
                # max_date = content_parser.normalize_xpath(selector, '(//*[@class="right_new1"]//li[1]/a/span)[last()]')
                # min_date = content_parser.normalize_xpath(selector, '((//*[@class="right_new1"]//li)[last()]/a/span)[last()]')

                json_res = json.loads(res)

                max_date = re.findall(r'\d{4}-\d{2}-\d{2}', json_res['custom']['infodata'][0]['infodate'])[0]
                min_date = re.findall(r'\d{4}-\d{2}-\d{2}', json_res['custom']['infodata'][-1]['infodate'])[0]

                if (not max_date) or (not min_date):
                    break
                if datetime.strptime(max_date, '%Y-%m-%d') < datetime.strptime(self.start_time, '%Y-%m-%d'):
                    break
                elif datetime.strptime(min_date, '%Y-%m-%d') <= datetime.strptime(self.start_time,
                                                                                  '%Y-%m-%d') < datetime.strptime(
                        max_date, '%Y-%m-%d'):
                    for detail in json_res['custom']['infodata']:
                        detail_date = re.findall(r'\d{4}-\d{2}-\d{2}', detail['infodate'])[0]
                        if datetime.strptime(self.start_time, '%Y-%m-%d') > datetime.strptime(detail_date, '%Y-%m-%d'):
                            break

                        self.detail_requests_queue.put({
                            'url': self.domain_name + detail['infourl'],
                            'requests_type': 'get',
                            'title': deep_clean_text(
                                re.sub(r'<font.*?</font>', '', detail['title'])
                            ),
                            'publish_time': detail_date,
                            'item': item
                        })
                    break

                else:
                    for detail in json_res['custom']['infodata']:
                        detail_date = re.findall(r'\d{4}-\d{2}-\d{2}', detail['infodate'])[0]
                        self.detail_requests_queue.put({
                            'url': self.domain_name + detail['infourl'],
                            'requests_type': 'get',
                            'title': deep_clean_text(
                                re.sub(r'<font.*?</font>', '', detail['title'])
                            ),
                            'publish_time': detail_date,
                            'item': item
                        })

                    post_data.update({
                        'pageIndex': post_data['pageIndex'] + 1
                    })

        def detail_requests(item):
            # https://ggjy.mianyang.cn/projectInfo.html?infoid=53e3d686-c8c3-48d5-b88f-6db297ed14a2&categorynum=001001
            # infoid = re.findall(r'[?]infoid=([\w-]+)', item['url'])[0]
            # url_prime = fr"https://ggjy.mianyang.cn/EpointWebBuilder/getinfobyrelationguidaction.action?cmd=getInfolistNew&infoid={infoid}"
            # res_prime = self.crawler.get_response(
            #     url=url_prime,
            #     requests_type=item['requests_type'],
            #     judgement=[]
            # )
            # json_res_prime = json.loads(json.loads(res_prime)['custom'])[0]
            res = self.crawler.get_response(
                url=item['url'],  # self.domain_name + json_res_prime['urlpath'],
                requests_type=item['requests_type'],
                judgement=[]
            )
            # json_res = json.loads(res)
            selector = parsel.Selector(res)
            content = content_parser.replace_p_tag(
                html_content=selector.xpath('//*[@class="article-info article-content"]').get()
            )

            source = content_parser.normalize_xpath(
                selector, '//*[@class="article-sources"]/p[contains(text(), "信息来源")]')
            source = re.findall(r'信息来源：(.*?)】', source)
            source = source[0] if source else ''

            data_out = {
                '标题': item['title'],
                '时间': item['publish_time'],
                '来源': source,
                '链接': item['url'],
                '所在网站': self.website_name,
                '正文': content,

            }
            self.details_queue.put(data_out)

        # 启动线程池，根据模块、关键字搜索
        logger.info('开始根据关键字搜索。。。')
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.thread_num) as executor:
            futures = []
            channel_list = [
                {
                    'channel_name': '建设工程',
                    'channel_id': '004001002'
                },
                {
                    'channel_name': '政府采购',
                    'channel_id': '004002001'
                }
            ]
            for search_args in channel_list:
                for s in self.key_words:
                    future = executor.submit(
                        key_word_search,
                        s, search_args
                    )
                    futures.append(future)

            # 等待所有任务完成
            concurrent.futures.wait(futures)

        # 启动线程池，详情页请求清洗
        logger.info(f'开始请求详情页，total: {self.detail_requests_queue.qsize()}')
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.thread_num) as executor:
            futures = []
            duplicate_detail_list = []
            while True:
                try:
                    s = self.detail_requests_queue.get_nowait()
                    if (s['url'] not in duplicate_detail_list) and [key_word for key_word in self.key_words if
                                                                    key_word in s['title']]:
                        future = executor.submit(detail_requests, s)
                        futures.append(future)
                        duplicate_detail_list.append(s['url'])
                except queue.Empty:
                    break
            logger.info(f'去重后详情页，total: {len(duplicate_detail_list)}')
            # 等待所有任务完成
            concurrent.futures.wait(futures)

        logger.info('开始导出数据。。。')
        datas_list = []
        while True:
            try:
                datas_list.append(self.details_queue.get_nowait())
            except queue.Empty:
                break

        self.df = pd.DataFrame(datas_list)
        return self


if __name__ == '__main__':
    start = Spider46()
    start.master()
    # start.normalize_date('2025-08-12')
    print(1)
    """
    卫星、遥感、实景三维、智慧城市、低空经济、人工智能、机器人
    43	四川省内各市级	南充公共资源交易中心	https://www.scncggzy.com.cn
    44	四川省内各市级	宜宾市公共资源交易信息网	https://ggzy.yibin.gov.cn/#/home
    45	四川省内各市级	广安市公共资源交易网	https://gasggzy.cn
    46	四川省内各市级	达州市公共资源交易中心	https://www.dzggzy.cn
    47	四川省内各市级	雅安市公共资源交易平台	https://www.yaggzy.org.cn
    48	四川省内各市级	眉山市政务服务和公共资源交易服务中心	https://www.msggzy.org.cn/front
    
    pip install -U "urllib3<1.25"
    pip install onnxruntime cnocr pillow PyMuPDF opencv-python
    pip install gmssl

    对于每一个网站：
        1.使用多线程进行关键字搜索
        2.将上述中有翻页的情况集中再进行多线程请求
        3.从1中无翻页的res，以及2中的res中提取detail_url
        4.多线程请求detail_url，并清洗res
    """
