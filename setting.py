# development time: 2025-08-20  14:47
# developer: 元英

import json
from datetime import datetime,timedelta


# START_TIME = "2025-08-31"
# END_TIME = "2025-09-02"
KEYS = [
    "卫星",
    "机器人", "人工智能",
    "遥感",
    "智慧城市",
    "实景三维", "低空经济"]
FILTER_TITLE = ["结果", "更正", "中标", "成交", "定标", "验收", "开标", "候选人", "卫星村", "卫星路", "卫星小区"]
FILTER_CONTENT = ["开标记录", "中标金额", "中标候选人资格审查结果", "挂牌日期", "成交日期"]
# FILTER = ["结果", "更正", "中标公告", "成交", "定标", "验收", "开标记录"]
LOG_FILE = "./logs/log.txt"
LOG_FILE_MAX = 124
LOG_FILE_BACKUP_COUNT = 7
is_first_file="./first_status.json"
# 发送邮箱（163邮箱）
sender_email = "pc_adaspace@163.com"
# 163邮箱SMTP授权码
sender_auth_code = "TRbBL8gzW2PtHq4e"
# 收件人
default_recipients = ["2673137332@qq.com",
                      # "leitiancai@adaspace.com",
                      "439993015@qq.com"]
# default_recipients = ["2673137332@qq.com","yanxinyu@adaspace.com"]
# 附件
attachment_paths=["./AI_fiter_data_deduplicated.xlsx"]




def is_first():
    """ 判断是否第一次抓取 """

    with open(is_first_file,"r",encoding="utf8") as f:
        data = json.load(f)

    # 如果是第一次，则修改为否（马上会进行第一次抓取）
    if data["first"]:

        with open(is_first_file,"w",encoding="utf8") as file:
            json.dump(
                {
                    "first":False
                },
                fp=file,
                indent=4,  # 关键：缩进美化，可读性更强
            )

    return data["first"]


def get_target_time(first: bool) -> tuple[str, str]:
    """
    根据first变量的值，返回对应的时间（包含年月日时分秒）

    :param first: 布尔值，True则返回一周前的时间，False则返回昨天的时间
    :return: 格式化的时间字符串，格式为"YYYY-MM-DD HH:MM:SS"
    """
    # 获取当前时间
    current_time = datetime.now()

    # 根据first的值判断需要计算几天前的时间
    if first:
        # first为True，计算一周前（7天前）的时间
        target_time = current_time - timedelta(days=7)

        start_time = target_time.strftime("%Y-%m-%d")
        end_time = current_time.strftime("%Y-%m-%d")
    else:
        # first为False，计算昨天（1天前）的时间
        target_time = current_time - timedelta(days=1)

        start_time = end_time = target_time.strftime("%Y-%m-%d")

    return start_time, end_time


""" 这是项目的配置模块 """

# 初始化时间参数
first = is_first()
if first:
    print("第一次运行程序...")
START_TIME,END_TIME = get_target_time(first)

