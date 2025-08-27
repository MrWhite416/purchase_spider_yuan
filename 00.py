# import requests
import json
from curl_cffi import requests


headers = {
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Origin": "https://ggzyjyw.hlj.gov.cn",
    "Pragma": "no-cache",
    "Referer": "https://ggzyjyw.hlj.gov.cn/searchResult.html?wd=%E5%8D%AB%E6%98%9F",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36 Edg/139.0.0.0",
    "X-Requested-With": "XMLHttpRequest",
    "sec-ch-ua": "\"Not;A=Brand\";v=\"99\", \"Microsoft Edge\";v=\"139\", \"Chromium\";v=\"139\"",
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": "\"Windows\""
}
cookies = {
    "oauthClientId": "demoClient",
    "oauthPath": "http://127.0.0.1:8080/EpointWebBuilder",
    "oauthLoginUrl": "http://127.0.0.1:8080/EpointWebBuilder/rest/oauth2/authorize?client_id=demoClient&state=a&response_type=code&scope=user&redirect_uri=",
    "oauthLogoutUrl": "http://127.0.0.1:8080/EpointWebBuilder/rest/oauth2/logout?redirect_uri=",
    "noOauthRefreshToken": "224e16674daa31077ab663d514e17e50",
    "noOauthAccessToken": "a64674a342d0c2bdebe6ca6aee4675e3",
    "Secure": ""
}
url = "https://ggzyjyw.hlj.gov.cn/inteligentsearch/rest/esinteligentsearch/getFullTextDataNew"
data = {
    "token": "",
    "pn": 10,
    "rn": 10,
    "sdt": "",
    "edt": "",
    "wd": "卫星",
    "inc_wd": "",
    "exc_wd": "",
    "fields": "title",
    "cnum": "012;013",
    "sort": "{\"webdate\":\"0\",\"id\":\"0\"}",
    "ssort": "",
    "cl": 500,
    "terminal": "",
    "condition": [],
    "time": [
        {
            "fieldName": "webdate",
            "startTime": "2025-04-01 00:00:00",
            "endTime": "2025-08-20 23:59:59"
        }
    ],
    "highlights": "title;searchtitle;content",
    "statistics": None,
    "unionCondition": [],
    "accuracy": "",
    "noParticiple": "1",
    "searchRange": None,
    "noWd": True
}
data = json.dumps(data)
response = requests.post(url, headers=headers, cookies=cookies,data=data)

print(response.text)
print(response)