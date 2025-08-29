from curl_cffi import requests

import requests


headers = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "Pragma": "no-cache",
    "Referer": "https://search.ccgp.gov.cn/bxsearch?searchtype=1&page_index=1&bidSort=0&buyerName=&projectId=&pinMu=0&bidType=0&dbselect=bidx&kw=%E5%8D%AB%E6%98%9F&start_time=2025%3A06%3A01&end_time=2025%3A08%3A29&timeType=6&displayZone=&zoneId=&pppStatus=0&agentName=",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36 Edg/139.0.0.0",
    "sec-ch-ua": "\"Not;A=Brand\";v=\"99\", \"Microsoft Edge\";v=\"139\", \"Chromium\";v=\"139\"",
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": "\"Windows\""
}
url = "https://search.ccgp.gov.cn/bxsearch"
params = {
    "searchtype": "1",
    "page_index": "2",
    "bidSort": "0",
    "buyerName": "",
    "projectId": "",
    "pinMu": "0",
    "bidType": "0",
    "dbselect": "bidx",
    "kw": "卫星",
    "start_time": "2025:06:01",
    "end_time": "2025:08:29",
    "timeType": "6",
    "displayZone": "",
    "zoneId": "",
    "pppStatus": "0",
    "agentName": ""
}
response = requests.get(url, headers=headers, params=params)

print(response.text)
print(response)