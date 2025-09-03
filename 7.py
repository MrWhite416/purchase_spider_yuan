import pandas as pd


# ----------------------
# 2. 追加写入：向已有文件的工作表末尾添加新数据
# ----------------------
def append_to_excel(file_path, sheet_name, new_data):
    """
    追加数据到 Excel 工作表末尾
    :param file_path: 已有 Excel 文件路径
    :param sheet_name: 目标工作表名称（需与文件中一致）
    :param new_data: 新数据（pd.DataFrame，列名需与原有工作表一致）
    """




if __name__ == "__main__":
    excel_path = "招标数据.xlsx"
    sheet_name = "项目列表"

    # 1. 首次初始化（若文件不存在）
    init_excel(excel_path, sheet_name)

    # 2. 模拟第一批新数据（列名需与初始化时一致）
    new_data1 = pd.DataFrame({
        "标题": ["德阳市大数据产业园项目", "宿州工业机器人实验室项目"],
        "发布时间": ["2025-07-28", "2025-09-01"],
        "来源": ["德阳公共资源交易网", "宿州公共资源交易网"],
        "文本": ["设计施工总承包...", "实验室设备采购..."],
        "链接": ["http://xxx1.com", "http://xxx2.com"]
    })
    append_to_excel(excel_path, sheet_name, new_data1)

    # 3. 模拟第二批新数据（后续追加，自动添加到末尾）
    new_data2 = pd.DataFrame({
        "标题": ["龙岗区具身智能机器人项目"],
        "发布时间": ["2025-08-09"],
        "来源": ["深圳公共资源交易网"],
        "文本": ["创新平台建设..."],
        "链接": ["http://xxx3.com"]
    })
    append_to_excel(excel_path, sheet_name, new_data2)