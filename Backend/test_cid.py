import urllib.request
import json
def get_categories(cid):
    url = 'https://datalab.naver.com/shoppingInsight/getCategory.naver'
    data = f'cid={cid}'.encode('utf-8')
    req = urllib.request.Request(url, data=data, headers={'Referer': 'https://datalab.naver.com/'})
    with urllib.request.urlopen(req) as res:
        data = json.loads(res.read().decode('utf-8'))
        return data

with open('output.txt', 'w', encoding='utf-8') as f:
    child = get_categories('50000006') # 식품
    for c in child.get('childList', []):
        if '과자' in c['name'] or '스낵' in c['name'] or '베이커리' in c['name']:
            f.write(f"Found: {c['name']} ({c['cid']})\n")
            subchild = get_categories(c['cid'])
            for sc in subchild.get('childList', []):
                if '과자' in sc['name'] or '스낵' in sc['name']:
                    f.write(f"  -> Found: {sc['name']} ({sc['cid']})\n")
