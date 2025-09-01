from curl_cffi import requests

def a():
    try:
        print()
        1/0
        return 1
    except Exception as ee:
        print(ee)


print(a())