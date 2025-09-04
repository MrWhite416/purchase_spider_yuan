# development time: 2025-08-20  15:09
# developer: 元英

from concurrent.futures import ThreadPoolExecutor
from spiders import spiders
from util.tool import summary_df,send_163_email,clean_old_data
import warnings
from urllib3.exceptions import InsecureRequestWarning
from apscheduler.schedulers.blocking import BlockingScheduler
from util.deduplicate import deduplication
from spiders import crawler
from datetime import datetime


# 禁用 "Unverified HTTPS request" 警告
warnings.filterwarnings("ignore", category=InsecureRequestWarning)

def task():


    def ck_tasks():
        tasks = []

        for i in list(range(1,24))+[51,49,48,47]:

            example = getattr(spiders,f"Spider{i}")()
            if example.run_flag:
                tasks.append(example.master)

        for i in [24,25,26,27]+list(range(30,47)):
            example = getattr(crawler,f"Spider{i}")()

            tasks.append(example.master)


        return tasks

    def execute(task):
        return task()


    with ThreadPoolExecutor(max_workers=8) as pool:
        res = pool.map(execute,ck_tasks())
        dfs = [example.df for example in res]

        summary_df("./all_data.xlsx",dfs)


    # 爬虫任务结束，数据存储之后的一些处理
    # 如数据去重，旧数据删除，邮件推送等
    deduplication("./all_data.xlsx")  # 去重

    clean_old_data("./all_data.xlsx")  # 删除旧数据

    email_content = """请查收附件"""
    send_163_email("招标公告推送",email_content)  # 发送邮件

# task()


# 定时任务调度

sched = BlockingScheduler()


# 3. 添加任务：用 cron 触发器，指定每天凌晨1点
# sched.add_job(
#     func=task,
#     trigger='cron',
#     # hour=1,
#     minute=35,
#     second=24
# )

# 每隔10分钟执行一次（从启动时间开始计算，每次执行后间隔10分钟）
sched.add_job(
    func=task,
    trigger='interval',
    minutes=10,  # 关键：间隔10分钟
    # 可选：设置首次执行延迟（如启动后立即执行，不加则默认等待10分钟）
    next_run_time=datetime.now()
)

sched.start()

