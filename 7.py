

# from curl_cffi import requests
import requests


headers = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "Pragma": "no-cache",
    "Referer": "https://www.cdggzy.com/sitenew/notice/JSGC/List.aspx",
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
    "ASP.NET_SessionId": "xwnwikb0n0xecxwslkjkgjhq",
    "Hm_lvt_0404e8a4e2a4fb574bf8dc18126db6a8": "1755657450,1756797462,1756969667",
    "Hm_lpvt_0404e8a4e2a4fb574bf8dc18126db6a8": "1756969667",
    "HMACCOUNT": "D27C4E3B98E4AC0E"
}
url = "https://www.cdggzy.com/sitenew/notice/JSGC/NoticeContent.aspx"
params = {
    "id": "2F8B2C7149A749BE8DE853C557A4E1A4"
}
response = requests.get(url, headers=headers, cookies=cookies, params=params)

print(response.text)
print(response)



