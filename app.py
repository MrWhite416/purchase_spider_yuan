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
    for i in range(1,21):

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


