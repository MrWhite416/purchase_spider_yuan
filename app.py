# development time: 2025-08-20  15:09
# developer: 元英

from concurrent.futures import ThreadPoolExecutor
from spiders import spiders
from util.tool import summary_df
import warnings
from urllib3.exceptions import InsecureRequestWarning

# 禁用 "Unverified HTTPS request" 警告
warnings.filterwarnings("ignore", category=InsecureRequestWarning)

def ck_tasks():
    tasks = []
    for i in list(range(1,24))+[51,49,48,47]:

        example = getattr(spiders,f"Spider{i}")()
        if example.run_flag:
            tasks.append(example.master)


    return tasks

def execute(task):
    return task()

ck_tasks()


with ThreadPoolExecutor(max_workers=8) as pool:
    res = pool.map(execute,ck_tasks())
    dfs = [example.df for example in res]

    summary_df(dfs)


# 16:45:40

# 2025-09-01 16:46:11,716 | ERROR | ThreadPoolExecutor-0_4:27952 | spiders.py:1347 | clean_urls | 黑龙江公共资源交易网 | 出错：'titlenew' | 错误行号：1333
# 2025-09-01 16:46:11,723 | ERROR | ThreadPoolExecutor-0_4:27952 | spiders.py:1326 | process | 黑龙江公共资源交易网 | 出错 | 'NoneType' object is not iterable | 错误行号：1320
