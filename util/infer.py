import requests
import json
import pandas
from util import log

# 定义 API 地址
url = "http://192.168.128.34:8000/v1/chat/completions"

def filter(info:str):
    # 构建请求头
    headers = {
        "Content-Type": "application/json"
    }

    # 构建请求体
    prompt = \
    f"""{info}\n\n根据上面的招标信息，判断是否含有下面的任一关键词：
    "卫星"，"遥感"，"实景三维"，"智慧城市"，"低空经济"，"人工智能"，"机器人"。
    如果含有，再从招标信息的语义角度分析是否属于这些细分的类：
    卫星：卫星整星制造；
    遥感：卫星遥感数据采购，遥感服务平台建设，遥感应用类（农业、林业、地物识别、土地变更调查等）；
    实景三维：实景三维建设，实景三维成果采购；
    智慧城市：智慧城市平台建设；
    低空经济：低空经济类服务平台建设，可包含硬件和软件平台同时采购的招标公告；
    机器人：具身智能训练平台采购，机器人训练应用场景建设类。
    如果属于，请只回答“True”，如果不属于，请只回答“False”，不要给出任何解释和原因。"""

    data = {
        "model": "qwen",
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt}
        ]
    }

    # 发送 POST 请求
    response = requests.post(url, headers=headers, data=json.dumps(data),timeout=30)

    # 检查响应状态并输出结果
    if response.status_code == 200:
        result = response.json()
        # 提取模型回复内容
        assistant_reply = result['choices'][0]['message']['content']
        return eval(assistant_reply)
    else:
        print("Error:", response.status_code)
        print("Response:", response.text)
        raise

def AI_filter(df:str|pandas.DataFrame):
    logger = log.logger
    logger.info("AI过滤中... ...")

    if isinstance(df, str):
        df = pandas.read_excel("../all_data.xlsx")
    # 替换df中所有空值
    df = df.fillna("无数据")

    # 2. 对“正文”列每条数据执行AI_filter，生成过滤掩码（True=保留，False=剔除）
    # apply()会逐行将“正文”列的值传入AI_filter，返回每行的过滤结果
    filter_mask = df["正文"].apply(filter)

    # 3. 用掩码筛选DataFrame，保留mask为True的整行数据
    df_reserved = df[filter_mask]


    return df_reserved


