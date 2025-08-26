import sys, os, re

code_path = os.path.abspath(__file__)

sys.path.append(re.findall('.*?code_py', fr'{code_path}', flags=re.S)[0])

from used_code.other_code.demo_MQCrawler import MainCrawl

from tool.log import get_logger, normal_logger

error_logger = get_logger(code_path)

from used_code.other_code.demo_crawler import Crawler

import pymongo
from used_code.database import local_mongo

connect = pymongo.MongoClient(local_mongo)
db_chengyan = connect['chengyan']

import parsel
from used_code.my_public import ziduan, others
from copy import deepcopy
import itertools
import concurrent.futures
import time
import random
from tqdm import tqdm


class Start(MainCrawl):
    def __init__(self, db, task_name, thread_num=3, task_stop_num=None):
        super().__init__(db, task_name, error_logger, thread_num, task_stop_num)
        self.domain_name = r'https://www.zuowen.com'

        self.crawler = Crawler(crawler_type='requests', proxies_type='local')

        self.total_tasks = 0

    def level_1th(self, item, html_content=None):
        if not html_content:
            url = item['url']
            html_content = self.crawler.get_response(requests_type='get', url=url)
        if not html_content:
            normal_logger.info(f'请求无响应：{str(item)}')
            return False
        selector = parsel.Selector(html_content)

        detail_tags = selector.xpath('//*[@class="artbox_l"]')
        if not detail_tags.get():
            normal_logger.info(f'请求异常：{str(item)}')
            return False

        if item.get('_id'):
            del item['_id']

        for detail_tag in detail_tags:
            item_detail = deepcopy(item)

            try:
                detail_url = ziduan.normalize_xpath(detail_tag, './div[1]/a/@href')
                self.duplicate_col.insert_one({'_id': detail_url})

                item_detail.update({
                    'level': 'detail',
                    'url': detail_url,
                    'title': ziduan.normalize_xpath(detail_tag, './div[1]/a')
                })
                self.detail_col.insert_one(item_detail)
                # self.rabbit.producer(self.task_name, item_detail, 1)
            except:
                pass

        return {'consume': True}

    def level_detail(self, item):
        url = item['url']

        html_content = self.crawler.get_response(requests_type='get', url=url)
        if not html_content:
            normal_logger.info(f'请求无响应：{str(item)}')
            return False
        selector = parsel.Selector(html_content)

        if not selector.xpath('//*[@class="con_content"]').get():
            normal_logger.info(f'请求异常：{str(item)}')
            return False

        detail_item = {
            'html_content': html_content
        }
        detail_item.update({
            'text_prime': selector.xpath('//*[@class="con_content"]').get(),
        })
        self.detail_col.update_one({'_id': item['_id']}, {'$set': detail_item})

        return {'consume': True}

    def start_method(self):
        url = r'https://www.zuowen.com/yuanchuangzq/zhuanjiadianping/index.shtml'
        html_content = self.crawler.get_response(requests_type='get', url=url)

        if not html_content:
            normal_logger.info(f'请求无响应：{url}')
            return False

        selector = parsel.Selector(html_content)

        # 列表第一页先进行详情页获取
        item_1th = {
            'level': 'level_1th'
        }

        self.related_col.insert_one(item_1th)
        [item_1th.pop(s) for s in ['_id']]  # , 'done'

        self.level_1th(item_1th, html_content)

        # 判断页数
        last_page = int(selector.xpath('//*[@class="artpage"]/a/text()').getall()[-2].strip())

        if last_page == 1:
            pass
        else:
            for page_num in range(2, last_page + 1):
                item_1th_next = deepcopy(item_1th)
                item_1th_next.update({
                    'url': f'https://www.zuowen.com/yuanchuangzq/zhuanjiadianping/index_{page_num}.shtml'
                })
                self.related_col.insert_one(item_1th_next)
                self.rabbit.producer(self.task_name, item_1th_next, 2)
        return {'consume': True}

    def do_with_thread(self):
        def each_thread(find1):
            if find1['level'] == 'detail':
                consume_res = self.level_detail(find1)
            else:
                raise Exception(f'缺少解析方法：{find1["level"]}')

            if not consume_res or consume_res.get('consume') is not True:
                pass
            else:
                if find1['level'] == 'detail':
                    pass
                else:
                    self.related_col.update_one({'_id': find1['_id']}, {'$set': {'done': 1}})

            # 计算剩余任务数量

            with self.semaphore:
                self.total_tasks -= 1
                normal_logger.info(f'Remaining Tasks: {self.total_tasks}===id: {find1["_id"]}===Task Done===')

        search_way_detail = {
            'html_content': None
        }
        self.total_tasks = self.detail_col.count_documents(search_way_detail)
        normal_logger.info(f'总任务数量: {self.total_tasks}')

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.thread_num) as executor:
            futures = []
            for find_1 in self.detail_col.find(search_way_detail, no_cursor_timeout=True, batch_size=1000):
                future = executor.submit(each_thread, find_1)
                futures.append(future)

            # 等待所有任务完成
            concurrent.futures.wait(futures)

    def __del__(self):
        pass


if __name__ == '__main__':
    custom_task_name = code_path.split('\\')[-2]
    from tool.rabbitmq.tools.rabbitmq import RabbitMqApi
    [RabbitMqApi(queue_name).delete_queue() for queue_name in [
        custom_task_name,
        f'{custom_task_name}_error'
    ]]

    start = Start(db=db_chengyan, task_name=custom_task_name, thread_num=3)
    # start.consuming_error()
    # start.run()

    start.do_with_thread()

connect.close()
