# development time: 2025-08-20  14:47
# developer: 元英

import json
import pandas as pd
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
                      "leitiancai@adaspace.com",
                      "439993015@qq.com"]
# default_recipients = ["2673137332@qq.com","yanxinyu@adaspace.com"]
# 附件
attachment_paths = ["./all_data.xlsx"]



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


""" 这是项目的配置模块 """



def find_max_time_in_excel(file_path):
    """
    提取Excel表格中以"时间"为表头的列，并找出其中的最大时间

    参数:
        file_path: Excel文件的路径

    返回:
        最大的时间值，如果没有找到时间列则返回None
    """
    try:
        # 读取Excel文件
        df = pd.read_excel(file_path)

        # 查找表头为"时间"的列
        time_column = None
        for column in df.columns:
            if str(column).strip() == "时间":
                time_column = column
                break

        if time_column is None:
            print("未找到表头为'时间'的列")
            return None

        # 提取时间列数据
        time_series = df[time_column]

        # 尝试将数据转换为 datetime 类型
        try:
            time_series = pd.to_datetime(time_series, errors='coerce')
        except Exception as e:
            print(f"转换时间格式时出错: {e}")
            return None

        # 去除空值
        valid_times = time_series.dropna()

        if valid_times.empty:
            print("时间列中没有有效的时间数据")
            return None

        # 找到最大时间
        max_time = valid_times.max()

        print(f"时间列中的最大时间是: {max_time.strftime('%Y-%m-%d')}")
        return max_time.to_pydatetime()

    except FileNotFoundError:
        print(f"错误: 找不到文件 {file_path}")
        return None
    except Exception as e:
        print(f"处理文件时出错: {e}")
        return None


def get_target_time() -> tuple[str, str]:
    """
    :return: 格式化的时间字符串，格式为"YYYY-MM-DD HH:MM:SS"
    """
    # 获取当前时间
    current_time = datetime.now()

    # 从all_data.xlsx中提取最大时间
    max_time = find_max_time_in_excel(file_path='./all_data.xlsx')

    # 获取开始采集时间
    if max_time and (max_time > current_time - timedelta(days=7)):
        target_time = max_time + timedelta(days=1)
    else:
        target_time = current_time - timedelta(days=7)

    end_time = current_time - timedelta(days=1)

    start_time = target_time.strftime("%Y-%m-%d")
    end_time = end_time.strftime("%Y-%m-%d")
    return start_time, end_time

# 初始化时间参数
first = is_first()
if first:
    print("第一次运行程序...")


