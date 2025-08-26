import requests
import json


headers = {'Accept': '*/*', 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36 Edg/139.0.0.0'}
url = "https://haiyun.jl.gov.cn/irs/front/search"
data = {
    "code": "1892dd01822",
    "searchWord": "人工智能",
    "orderBy": "time",
    "dataTypeId": "501",
    "searchBy": "all",
    "pageNo": 1,
    "pageSize": 10,
    "granularity": "ALL",
    "beginDateTime": "",
    "endDateTime": "",
    "isSearchForced": 0,
    "customFilter": {
        "operator": "and",
        "properties": [
            {
                "property": "channel_id",
                "operator": "eq",
                "value": "69308",
                "weight": 100
            }
        ]
    }
}
data = json.dumps(data, separators=(',', ':'))
response = requests.post(url, headers=headers, data=data)
data = response.json()
print(data)

for d in data["data"]["middle"]["listAndBox"]:
    print(d["data"]["table-4"])

import datetime

t = datetime.datetime.strptime("2025-02-07 00:00:00", "%Y-%m-%d %H:%M:%S").date()
print(datetime.datetime.strptime("2025-02-07","%Y-%m-%d"))

print(response)