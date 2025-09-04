import requests
import json


def ai_filter(info):
    # 定义 API 地址
    url = "http://192.168.128.34:8000/v1/chat/completions"

    # 招标信息
    # info = """"""

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
    如果属于，请只回答“True”，如果不含有，请只回答“False”，不要给出任何解释和原因。"""
    # ，非卫星地面站接收设备采购，非卫星通信类采购，非卫星零部件采购
    # ，非智慧城市硬件设备类采购
    # ，非机器人硬件类采购

    data = {
        "model": "qwen",
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt}
        ]
    }

    # 发送 POST 请求
    response = requests.post(url, headers=headers, data=json.dumps(data))

    # 检查响应状态并输出结果
    if response.status_code == 200:
        result = response.json()
        # 提取模型回复内容
        assistant_reply = result['choices'][0]['message']['content']
        print("Assistant: ", assistant_reply)
    else:
        print("Error:", response.status_code)
        print("Response:", response.text)


if __name__ == '__main__':
    ai_filter('四川省广安友谊中学智能交互一体机（智慧黑板）设备采购询价公告')