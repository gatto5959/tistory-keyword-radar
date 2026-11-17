import streamlit as st
import requests
import pandas as pd
import json
from datetime import datetime, timedelta

# ----------------------------------------------------
# 1. API 키 설정 (네이버 클라우드 플랫폼 인증 정보)
# ----------------------------------------------------
CLIENT_ID = st.secrets["kau026dh56"]
CLIENT_SECRET = st.secrets["lbrX4TFkN2q05fTWgF4gSc6W3KkLdGa1iGwqJ7lH"]

# API HUB 전용 헤더
headers_cloud = {
    "X-NCP-APIGW-API-KEY-ID": CLIENT_ID,
    "X-NCP-APIGW-API-KEY": CLIENT_SECRET,
}
headers_datalab = {
    "X-NCP-APIGW-API-KEY-ID": CLIENT_ID,
    "X-NCP-APIGW-API-KEY": CLIENT_SECRET,
    "Content-Type": "application/json"
}

# ----------------------------------------------------
# 2. 데이터 수집 함수
# ----------------------------------------------------
def get_blog_doc_count(keyword):
    """검색 API를 통해 해당 키워드의 누적 블로그 문서 수를 가져옵니다."""
    url = f"https://naveropenapi.apigw.ntruss.com/search-blog/v1/search?query={keyword}&display=1"
    response = requests.get(url, headers=headers_cloud)
    if response.status_code == 200:
        return response.json().get('total', 0)
    return 0

def get_search_trend(keyword, start_date, end_date, device="mo"):
    """데이터랩 API를 통해 4050 타겟의 핵심인 모바일 검색 트렌드 지수를 가져옵니다."""
    url = "https://naveropenapi.apigw.ntruss.com/datalab/v1/search"
    body = {
        "startDate": start_date,
        "endDate": end_date,
        "timeUnit": "date",
        "keywordGroups": [{"groupName": keyword, "keywords": [keyword]}],
        "device": device,
        "ages": ["4", "5", "6"] # 40대, 50대, 60대 이상 타겟팅
    }
    response = requests.post(url, headers=headers_datalab, data=json.dumps(body))
    if response.status_code == 200:
        data = response.json()
        try:
            results = data['results'][0]['data']
            # 최근 트렌드 지수의 합산을 통해 관심도(Volume) 추정
            trend_score = sum([item['ratio'] for item in results])
            return trend_score, results
        except IndexError:
            return 0, []
    return 0, []

# ----------------------------------------------------
# 3. 스트림릿 UI 구성
# ----------------------------------------------------
st.set_page_config(page_title="티스토리 황금 키워드 발굴기", layout="wide")
st.title("📈 4050 타겟 건강·금융 황금 키워드 발굴기")

# 사이드바: 검색 조건 입력
with st.sidebar:
    st.header("🔍 키워드 검색 조건")
    keywords_input = st.text_area(
        "분석할 키워드를 입력하세요 (쉼표로 구분)", 
        value="기초연금 수급자격, 고혈압 낮추는 방법, 당뇨 초기증상, 파킹통장 추천, 건강보험료 피부양자"
    )
    period = st.selectbox("트렌드 조회 기간", ["최근 1개월", "최근 3개월", "최근 1년"])
    
    if period == "최근 1개월":
        days = 30
    elif period == "최근 3개월":
        days = 90
    else:
        days = 365
        
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    
    analyze_btn = st.button("황금 키워드 추출하기", type="primary")

# 메인 화면: 데이터 분석 및 출력
if analyze_btn:
    keyword_list = [k.strip() for k in keywords_input.split(",") if k.strip()]
    
    if not keyword_list:
        st.warning("키워드를 입력해 주세요.")
    else:
        with st.spinner('네이버 API 서버에서 4050 검색 데이터를 수집하고 있습니다...'):
            results_data = []
            trend_charts = {}
            
            for kw in keyword_list:
                # 1. 누적 문서 수 수집
                doc_count = get_blog_doc_count(kw)
                
                # 2. 검색어 트렌드 지수 수집 (4060세대, 모바일 기준)
                trend_score, trend_raw_data = get_search_trend(kw, start_date, end_date, device="mo")
                
                # 3. 경쟁률 계산 (문서 수 / 트렌드 지수) -> 낮을수록 글 쓰기 좋은 황금 키워드
                # 트렌드 지수가 0인 경우 분모가 0이 되는 것을 방지
                competitiveness = round(doc_count / trend_score, 2) if trend_score > 0 else 99999
                
                results_data.append({
                    "키워드": kw,
                    "4050 트렌드 지수 (높을수록 좋음)": round(trend_score, 1),
                    "누적 블로그 문서 수 (낮을수록 좋음)": doc_count,
                    "🔥 경쟁률 (낮을수록 좋음)": competitiveness
                })
                
                # 차트용 데이터 가공
                if trend_raw_data:
                    df_trend = pd.DataFrame(trend_raw_data)
                    df_trend.rename(columns={'period': '날짜', 'ratio': '검색량 비율'}, inplace=True)
                    df_trend.set_index('날짜', inplace=True)
                    trend_charts[kw] = df_trend

            # 데이터프레임 생성 및 정렬 (경쟁률 낮은 순)
            df_results = pd.DataFrame(results_data)
            df_results = df_results.sort_values(by="🔥 경쟁률 (낮을수록 좋음)")
            df_results.reset_index(drop=True, inplace=True)

            # --- 결과 출력 ---
            st.subheader("🏆 키워드 경쟁력 분석 결과")
            st.markdown("경쟁률 숫자가 **가장 낮은 키워드**부터 티스토리에 포스팅하세요. (트렌드 지수 대비 문서 수가 적다는 의미입니다.)")
            st.dataframe(df_results, use_container_width=True)

            st.divider()

            # 트렌드 차트 출력
            st.subheader("📊 키워드별 검색량 급상승 트렌드")
            
            # 차트를 2열로 배치
            cols = st.columns(2)
            for idx, (kw, chart_data) in enumerate(trend_charts.items()):
                with cols[idx % 2]:
                    st.write(f"**{kw}**")
                    st.line_chart(chart_data)