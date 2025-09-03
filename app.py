# development time: 2025-08-20  15:09
# developer: 元英

from concurrent.futures import ThreadPoolExecutor
from spiders import spiders
from util.tool import summary_df,send_163_email,clean_old_data
import warnings
from urllib3.exceptions import InsecureRequestWarning
from apscheduler.schedulers.blocking import BlockingScheduler
from util.deduplicate import deduplication


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



# 定时任务调度

# sched = BlockingScheduler()
#
#
# # 3. 添加任务：用 cron 触发器，指定每天凌晨1点
# sched.add_job(
#     func=task,
#     trigger='cron',
#     hour=1,
#     minute=0,
#     second=24
# )
#
# sched.start()




# 来自 Spider11（吉林省公共资源交易中心） 类的方法 clean_detail 执行出错: list index out of range
# 来自 Spider7（河北省招标投标公共服务平台） 类的方法 clean_url 执行出错: 'NoneType' object is not subscriptable
# 来自 Spider7（河北省招标投标公共服务平台） 类的方法 process 执行出错: 'NoneType' object is not iterable