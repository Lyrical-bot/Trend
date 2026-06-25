import requests
import json
url = 'https://datalab.naver.com/shoppingInsight/getCategoryKeywordRank.naver'
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Referer': 'https://datalab.naver.com/shoppingInsight/sCategory.naver',
    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
    'X-Requested-With': 'XMLHttpRequest'
}
data = 'cid=50022619&timeUnit=date&startDate=2026-05-24&endDate=2026-06-24&age=&gender=&device=&page=1&count=20'

res = requests.post(url, headers=headers, data=data)
try:
    with open('rank_out.txt', 'w', encoding='utf-8') as f:
        f.write(json.dumps(res.json(), ensure_ascii=False))
except Exception as e:
    with open('rank_out.txt', 'w', encoding='utf-8') as f:
        f.write(str(e) + "\n" + res.text)
