import urllib.request
import json
import sys

def get_categories(cid):
    url = 'https://datalab.naver.com/shoppingInsight/getCategory.naver'
    data = f'cid={cid}'.encode('utf-8')
    req = urllib.request.Request(url, data=data, headers={'Referer': 'https://datalab.naver.com/'})
    with urllib.request.urlopen(req) as res:
        data = json.loads(res.read().decode('utf-8'))
        return data

if __name__ == '__main__':
    # 식품 50000006
    child = get_categories('50000006')
    for c in child.get('childList', []):
        if '과자' in c['name'] or '스낵' in c['name'] or '베이커리' in c['name']:
            print(f"Found: {c['name']} ({c['cid']})")
            subchild = get_categories(c['cid'])
            for sc in subchild.get('childList', []):
                if '과자' in sc['name'] or '스낵' in sc['name']:
                    print(f"  -> Found: {sc['name']} ({sc['cid']})")
