# development time: 2025-08-20  14:47
# developer: 元英

""" 这是项目的配置模块 """

START_TIME = "2025-04-27"
END_TIME = "2025-09-02"
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
# 发送邮箱（163邮箱）
sender_email = "pc_adaspace@163.com"
# 163邮箱SMTP授权码
sender_auth_code = "TRbBL8gzW2PtHq4e"
# 收件人
default_recipients = ["2673137332@qq.com"]
# 附件
attachment_paths=["./AI_fiter_data_deduplicated.xlsx"]

