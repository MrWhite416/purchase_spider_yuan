from curl_cffi import requests


headers = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "Content-Type": "application/x-www-form-urlencoded",
    "Origin": "https://ggzyjy.shandong.gov.cn",
    "Pragma": "no-cache",
    "Referer": "https://ggzyjy.shandong.gov.cn/queryContent-jyxxgk.jspx",
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
cookies = {
    "clientlanguage": "zh_CN",
    "JSESSIONID": "DF7B686AB7FD82EF0E9A821061A35326"
}
url = "https://ggzyjy.shandong.gov.cn/queryContent-jyxxgk.jspx"
data = {
    "title": "卫星",
    "origin": "",
    "inDates": "300",
    "channelId": "151",
    "ext": ""
}
response = requests.post(url, headers=headers, cookies=cookies, data=data)
import datetime
print(response.text)
print(response)
print(abs((datetime.datetime.strptime("2025-07-22","%Y-%m-%d").date() - datetime.datetime.now().date()).days))