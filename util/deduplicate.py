import pandas as pd
from util.log import logger

def deduplication(data: str | pd.DataFrame):
    logger.info("去重中... ...")

    if isinstance(data,str):
        # 读取 Excel 文件
        excel_path = data
        df = pd.read_excel(excel_path)
    else:
        df = data

    # 指定需要去重的列
    columns_to_deduplicate = ['标题', '时间', '来源', '链接', '所在网站']

    # 去重：仅当这5列完全相同时才视为重复
    df_deduplicated = df.drop_duplicates(subset=columns_to_deduplicate, keep='first')

    # 保存到新的 Excel 文件
    df_deduplicated.to_excel('all_data.xlsx', index=False)

    print("去重完成，已保存为 all_data.xlsx")
