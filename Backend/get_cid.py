import requests
url = 'https://datalab.naver.com/shoppingInsight/getCategory.naver'
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Referer': 'https://datalab.naver.com/shoppingInsight/sCategory.naver'
}
data = {'cid': '50000006'}
res = requests.post(url, headers=headers, data=data)
try:
    with open('cat_out.txt', 'w', encoding='utf-8') as f:
        for c in res.json()['childList']:
            if '과자' in c['name'] or '스낵' in c['name'] or '베이커리' in c['name']:
                f.write(f"{c['name']} ({c['cid']})\n")
                data2 = {'cid': c['cid']}
                res2 = requests.post(url, headers=headers, data=data2)
                for sc in res2.json().get('childList', []):
                    if '과자' in sc['name'] or '스낵' in sc['name']:
                        f.write(f"  -> {sc['name']} ({sc['cid']})\n")
except Exception as e:
    print(e)
