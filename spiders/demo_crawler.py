import sys,os, re

code_path = os.path.abspath(__file__)

# sys.path.append(re.findall('.*?code_py', fr'{code_path}', flags=re.S)[0])

import parsel


from threading import Semaphore

import requests
import my_fake_useragent as ua

from loguru import logger

ip_url = '127.0.0.1:10809'  # 127.0.0.1:10809
# local_proxies = {
#     'http': ip_url,
#     'https': ip_url
# }

local_proxies = None

# 隧道域名:端口号
tunnel = "n472.kdltpspro.com:15818"

# 用户名密码方式
username = "t14090173076516"
password = "ndtal8yr"
tunnel_proxies = {
    "http": "http://%(user)s:%(pwd)s@%(proxy)s/" % {"user": username, "pwd": password, "proxy": tunnel},
    "https": "http://%(user)s:%(pwd)s@%(proxy)s/" % {"user": username, "pwd": password, "proxy": tunnel}
}


# ye = YryEncrpytion()


class Crawler:
    semaphore = Semaphore(value=1)
    timeout = 20
    update_count = 10
    del_cookie_count = 5
    custom_update_cookie = None

    def __init__(self, crawler_type='session', port_num=9527, domain_name=None, proxies_type='local', cookie_arr=None):
        """
        crawler_type: "requests", "session", "selenium", "curl_requests"
        """
        self.crawler_type = crawler_type
        self.port_num = port_num
        self.domain_name = domain_name
        self.session = requests.Session()

        self.headers = {}
        self.user_agent = self.update_ua()

        self.proxies_type = proxies_type
        self.proxies = None


    def update_ua(self):
        user_agent = ua.UserAgent(family='Chrome', phone=False).random()
        self.headers.update({
            'User-Agent': user_agent
        })
        return user_agent

    def update_headers(self):
        self.update_count -= 1
        with self.semaphore:
            if self.update_count <= 0:
                self.update_ua()
                self.update_count = 10

    def get_response(self, url, requests_type, **kwargs):
        """
        requests_type: "get", "post", "session_get", "session_post"
        judgement默认为['</html>'],可支持以f'By_xpath{}'方式检查
        """
        judgement = kwargs.get('judgement', None)
        save_as_b = kwargs.get('save_as_b', False)
        params = kwargs.get('params', None)
        post_data = kwargs.get('post_data', None)
        post_json = kwargs.get('post_json', None)
        retry_num = kwargs.get('retry_num', 5)
        return_all_res = kwargs.get('return_all_res', False)
        stream = kwargs.get('stream', False)

        errors_ignore = kwargs.get('errors_ignore', 'strict')

        # session 第一次请求时，获取cookie
        if self.update_count == 0:
            if self.domain_name == '':
                self.domain_name = re.findall('(.*?://.*?)/', url)[0]
            if self.headers.get('Cookie'):
                # custom_cookie
                self.update_count = 10
            else:
                self.update_headers()

        # 代理设置
        if self.proxies_type == 'domestic':
            proxies = self.proxies
        elif self.proxies_type == 'tunnel_proxies':
            proxies = tunnel_proxies
        else:
            proxies = local_proxies

        def res_judgement():
            """判断请求是否完整"""
            nonlocal judgement

            def each_judgement():
                if each.startswith('By_xpath'):
                    xpath_str = each.replace('By_xpath', '')
                    if not parsel.Selector(response).xpath(f'normalize-space({xpath_str})').get():
                        logger.info(f'Not xpath-matching: "{each}", Retry request...')
                        self.update_headers()
                        return False
                else:
                    if each == '</html>':
                        if not response.strip().endswith(each):
                            logger.error(f'不以</html>结尾：{response[-10:]}===：{url}')
                            return False
                    else:
                        if each not in response:
                            logger.error(f'Not contains: "{each}", Retry request...')
                            return False
            judgement = ['</html>'] if judgement is None else judgement
            for each in judgement:
                if each_judgement() is False:
                    return False
            return True

        for _ in range(retry_num):
            try:
                if requests_type == 'get':
                    response = requests.get(url=url,
                                            params=params,
                                            headers=self.headers,
                                            proxies=proxies,
                                            timeout=self.timeout,
                                            stream=stream)
                elif requests_type == 'post':
                    response = requests.post(url=url,
                                             data=post_data,
                                             json=post_json,
                                             headers=self.headers,
                                             proxies=proxies,
                                             timeout=self.timeout)
                elif requests_type == 'session_get':
                    response = self.session.get(url=url,
                                                params=params,
                                                headers=self.headers,
                                                proxies=proxies,
                                                timeout=self.timeout)
                elif requests_type == 'session_post':
                    response = self.session.post(url=url,
                                                 data=post_data,
                                                 json=post_json,
                                                 headers=self.headers,
                                                 proxies=proxies,
                                                 timeout=self.timeout)
                else:
                    logger.error(f'参数requests_type错误：{requests_type}')
                    return ''
                # if response.history and 'mainContent_lblSearchCriteria' not in response.text:
                #     print("发生了重定向！")
                #     # 如果发生了重定向，可以打印重定向历史
                #     for resp in response.history:
                #         print(f"重定向状态码：{resp.status_code}，重定向目标：{resp.url}")
                #     continue

                if response.status_code == 200:
                    if return_all_res:
                        return response
                    if save_as_b:
                        response = response.content
                    else:
                        # 假设 response 是你获取到的 HTTP 响应
                        raw_content = response.content

                        # # 自动检测编码
                        # detected_encoding = chardet.detect(raw_content)['encoding']
                        # if detected_encoding not in ['GB2312', 'utf-8']:
                        #     raise Exception(f"确认编码格式：{detected_encoding}")

                        # 根据检测到的编码进行解码
                        try:
                            response = raw_content.decode('utf-8')
                        except:
                            response = raw_content.decode('GB18030', errors=errors_ignore)  # GB2312

                        # response = html.unescape(response.content.decode('utf-8'))
                    if save_as_b or res_judgement():
                        return response
                elif re.match(r'4\d{2}', str(response.status_code)):
                    logger.error(f'客户端错误：{response.status_code}===：{url}\n------')
                    self.update_headers()
                elif re.match(r'5\d{2}', str(response.status_code)):
                    logger.error(f'服务器错误：{response.status_code}===：{url}\n------')
                    self.update_headers()
                else:
                    logger.error(f'{url}：{response.status_code}===:\n更新代理\n------')
                    self.update_headers()
            except Exception as e:
                logger.info(f'{url}：访问详情页失败==>{e}')
                self.update_count = 0
                self.update_headers()

        return ''

    def download_file(self, url, file_path):
        """
        通过content_length来判断请求是否完整
        requests.head()返回的header的json数据，检查是否存在Accept-Ranges以支持断点续传
        """

        def calc_divisional_range(filesize, chuck=10):
            step = filesize // chuck
            arr = list(range(0, filesize + 1, step))
            result = []
            for i in range(len(arr) - 1):
                s_pos, e_pos = arr[i], arr[i + 1] - 1
                # e_pos = filesize-1 if i == len(arr)-2 else e_pos
                result.append([s_pos, e_pos])
            result[-1][-1] = filesize - 1
            return result

        if self.proxies_type == 'domestic':
            proxies = self.proxies
        else:
            proxies = local_proxies

        local_filename = url.split('/')[-1]

        # 注意传入参数 stream=True
        with requests.get(url, stream=True, proxies=proxies) as r:
            r.raise_for_status()
            with open(os.path.join(file_path, local_filename), 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        return local_filename


if __name__ == '__main__':
    print(1)
