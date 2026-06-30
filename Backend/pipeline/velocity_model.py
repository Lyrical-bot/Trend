import os
import pandas as pd
from datetime import datetime

# 데이터셋 경로 설정 (이전 단계에서 수집한 CSV 파일)
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
dataset_path = os.path.join(parent_dir, "datasets", "historical_fb_data.csv")

def run_velocity_model():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 가속도(Velocity) 기반 선행 지표 감지 분석 시작...\n")
    
    if not os.path.exists(dataset_path):
        print(f"데이터 파일을 찾을 수 없습니다. 터미널에서 먼저 'python pipeline/data_collector.py'를 실행해주세요.\n경로: {dataset_path}")
        return

    # 데이터 로드
    df = pd.read_csv(dataset_path)
    df['date'] = pd.to_datetime(df['date'])
    
    results = []
    
    # 키워드별 그룹화 후 가속도 계산 로직 진행
    for keyword, group in df.groupby('keyword'):
        # 날짜순으로 정렬
        group = group.sort_values(by='date').reset_index(drop=True)
        
        if len(group) < 14:
            continue # 분석을 하려면 최소 14일치(2주)의 데이터는 필요함
            
        # 1. 최근 3일치 데이터 (현재 얼마나 터지고 있는가?)
        recent_3 = group.tail(3)
        # 2. 그 직전 7일치 데이터 (과거 평균 평소 검색량 기준점, Baseline)
        prev_7 = group.iloc[-10:-3]
        
        # 0으로 나누는 에러(ZeroDivisionError) 방지를 위해 아주 작은 값(1)을 더해줌
        avg_recent_3 = recent_3['search_volume_est'].mean() + 1
        avg_prev_7 = prev_7['search_volume_est'].mean() + 1
        
        # 💡 핵심 가속도(Velocity) 공식: ((최근 3일 평균 - 이전 7일 평균) / 이전 7일 평균) * 100
        velocity_score = ((avg_recent_3 - avg_prev_7) / avg_prev_7) * 100
        
        results.append({
            "keyword": keyword,
            "avg_recent_3": round(avg_recent_3 - 1, 0), # 화면에 보여줄 땐 1을 뺌
            "avg_prev_7": round(avg_prev_7 - 1, 0),
            "velocity_score": round(velocity_score, 1)
        })
        
    if not results:
        print("분석할 충분한 데이터가 없습니다.")
        return
        
    # 데이터프레임 변환 후 가속도 점수(velocity_score) 기준 내림차순 정렬
    res_df = pd.DataFrame(results)
    res_df = res_df.sort_values(by="velocity_score", ascending=False).reset_index(drop=True)
    
    # 터미널 리포트 출력
    print("[최근 3일 기준] 가속도(Velocity) 폭발 라이징 랭킹 Top 10")
    print("-" * 75)
    print(f"{'순위':<3} | {'식재료/음식명':<15} | {'평소 검색량(직전 7일)':<17} | {'최근 검색량(최근 3일)':<17} | {'가속도(증가율)'}")
    print("-" * 75)
    
    for i in range(min(10, len(res_df))):
        row = res_df.iloc[i]
        
        # 기호 추가 (폭등: ++, 상승: +, 하락: -)
        if row['velocity_score'] > 50:
            symbol = "++ "
        elif row['velocity_score'] > 0:
            symbol = "+ "
        else:
            symbol = "- "
            
        print(f"{i+1:<4} | {row['keyword']:<15} | {int(row['avg_prev_7']):<20} | {int(row['avg_recent_3']):<20} | {symbol}{row['velocity_score']}%")
        
    print("-" * 75)
    print("팁: '평소 검색량' 절대치가 낮아도 '가속도'가 높다면(Micro-spike), 그것이 바로 '선행 지표'입니다!")

def get_velocity_ranking(start_date_str=None, end_date_str=None):
    """
    메인 웹서버(FastAPI)에서 호출하여 가속도 랭킹 10위까지의 데이터를 JSON 형태로 반환받기 위한 함수입니다.
    사용자가 선택한 기간(start_date ~ end_date)과, 동일한 일수만큼의 과거(Baseline)를 비교합니다.
    """
    if not os.path.exists(dataset_path):
        return {"error": "데이터가 없습니다. 수집기를 먼저 실행해주세요."}

    df = pd.read_csv(dataset_path)
    df['date'] = pd.to_datetime(df['date'])
    
    # 기본값 처리 (날짜가 주어지지 않으면 최근 3일 기준)
    if not start_date_str or not end_date_str:
        end_dt = df['date'].max()
        start_dt = end_dt - pd.Timedelta(days=2)
    else:
        start_dt = pd.to_datetime(start_date_str)
        end_dt = pd.to_datetime(end_date_str)
        
    delta_days = (end_dt - start_dt).days + 1
    if delta_days <= 0:
        return {"error": "조회 시작일이 종료일보다 늦을 수 없습니다."}
        
    baseline_end = start_dt - pd.Timedelta(days=1)
    baseline_start = baseline_end - pd.Timedelta(days=delta_days - 1)
    
    results = []
    
    for keyword, group in df.groupby('keyword'):
        # Target 기간 (사용자 선택 기간)
        recent = group[(group['date'] >= start_dt) & (group['date'] <= end_dt)]
        # Baseline 기간 (직전 동일 일수)
        prev = group[(group['date'] >= baseline_start) & (group['date'] <= baseline_end)]
        
        if len(recent) == 0 or len(prev) == 0:
            continue
            
        avg_recent = recent['search_volume_est'].mean() + 1
        avg_prev = prev['search_volume_est'].mean() + 1
        
        velocity_score = ((avg_recent - avg_prev) / avg_prev) * 100
        
        results.append({
            "keyword": keyword,
            "avg_recent_3": int(round(avg_recent - 1, 0)),
            "avg_prev_7": int(round(avg_prev - 1, 0)),
            "velocity_score": round(velocity_score, 1)
        })
        
    if not results:
        return {"error": "선택하신 기간에 분석할 데이터가 부족합니다."}
        
    res_df = pd.DataFrame(results)
    res_df = res_df.sort_values(by="velocity_score", ascending=False).reset_index(drop=True)
    
    # Top 10 반환
    return {"data": res_df.head(10).to_dict(orient="records")}

async def get_velocity_ranking_live(keywords: list[str], start_date_str=None, end_date_str=None):
    from naver_api import fetch_naver_trend
    from naver_ad_api import fetch_search_ad_volume
    import pandas as pd
    from datetime import datetime, timedelta
    
    # 1. Determine dates
    if not start_date_str or not end_date_str:
        end_dt = pd.to_datetime((datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d"))
        start_dt = end_dt - pd.Timedelta(days=2) # Recent 3 days
    else:
        start_dt = pd.to_datetime(start_date_str)
        end_dt = pd.to_datetime(end_date_str)
        
    delta_days = (end_dt - start_dt).days + 1
    if delta_days <= 0:
        return {"error": "조회 시작일이 종료일보다 늦을 수 없습니다."}
        
    baseline_end = start_dt - pd.Timedelta(days=1)
    baseline_start = baseline_end - pd.Timedelta(days=delta_days)
    
    fetch_start_str = baseline_start.strftime("%Y-%m-%d")
    fetch_end_str = end_dt.strftime("%Y-%m-%d")
    
    # 2. Fetch Search Ad Volume
    ad_volumes = await fetch_search_ad_volume(keywords)
    
    # 3. Chunk keywords for Datalab API
    chunk_size = 5
    results = []
    
    for i in range(0, len(keywords), chunk_size):
        chunk = keywords[i:i+chunk_size]
        keyword_groups = [{"groupName": kw, "keywords": [kw]} for kw in chunk]
        
        try:
            naver_response = await fetch_naver_trend(
                start_date=fetch_start_str,
                end_date=fetch_end_str,
                time_unit="date",
                keyword_groups=keyword_groups
            )
            
            datalab_results = naver_response.get("results", [])
            for group in datalab_results:
                kw = group.get("title")
                data = group.get("data", [])
                
                # Scale
                group_monthly_volume = ad_volumes.get(kw, 0.0)
                df_data = []
                
                if group_monthly_volume > 0 and len(data) > 0:
                    total_ratio = sum(item["ratio"] for item in data)
                    days_queried = len(data)
                    estimated_monthly_ratio_sum = (total_ratio / days_queried) * 30
                    if estimated_monthly_ratio_sum > 0:
                        multiplier = group_monthly_volume / estimated_monthly_ratio_sum
                        for item in data:
                            df_data.append({
                                "date": pd.to_datetime(item["period"]),
                                "search_volume_est": item["ratio"] * multiplier
                            })
                    else:
                        for item in data:
                            df_data.append({"date": pd.to_datetime(item["period"]), "search_volume_est": 0})
                else:
                    for item in data:
                        df_data.append({"date": pd.to_datetime(item["period"]), "search_volume_est": item["ratio"]})
                
                df_kw = pd.DataFrame(df_data)
                if df_kw.empty:
                    continue
                    
                recent = df_kw[(df_kw['date'] >= start_dt) & (df_kw['date'] <= end_dt)]
                prev = df_kw[(df_kw['date'] >= baseline_start) & (df_kw['date'] <= baseline_end)]
                
                if len(recent) == 0 or len(prev) == 0:
                    continue
                    
                avg_recent = recent['search_volume_est'].mean() + 1
                avg_prev = prev['search_volume_est'].mean() + 1
                
                velocity_score = ((avg_recent - avg_prev) / avg_prev) * 100
                
                results.append({
                    "keyword": kw,
                    "avg_recent_3": int(round(avg_recent - 1, 0)),
                    "avg_prev_7": int(round(avg_prev - 1, 0)),
                    "velocity_score": round(velocity_score, 1)
                })
        except Exception as e:
            print(f"Error fetching naver trend for {chunk}: {e}")
            
        import asyncio
        await asyncio.sleep(0.5) # Rate limit 방어
            
    if not results:
        return {"error": "선택하신 기간에 분석할 데이터가 부족합니다."}
        
    res_df = pd.DataFrame(results)
    res_df = res_df.sort_values(by="velocity_score", ascending=False).reset_index(drop=True)
    
    return {"data": res_df.head(10).to_dict(orient="records")}

if __name__ == "__main__":
    run_velocity_model()
