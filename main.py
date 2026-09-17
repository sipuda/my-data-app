import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta, timezone

# 웹 브라우저 탭에 표시될 제목과 아이콘, 레이아웃을 설정합니다.
st.set_page_config(
    page_title="어제의 일별 박스오피스",
    page_icon="🎬",
    layout="wide"
)

# 배포 서버의 시계와 상관없이 항상 한국 표준시(KST: UTC+9) 기준으로 '어제' 날짜를 계산합니다.
kst_timezone = timezone(timedelta(hours=9))
now_in_kst = datetime.now(kst_timezone)
yesterday_kst = now_in_kst - timedelta(days=1)

# API 요청용 날짜 형식 (YYYYMMDD, 예: 20260916)
target_dt = yesterday_kst.strftime("%Y%m%d")
# 사용자 화면 표시용 날짜 형식 (예: 2026년 09월 16일)
display_date = yesterday_kst.strftime("%Y년 %m월 %d일")

# @st.cache_data(ttl=3600) 데코레이터를 사용하여 같은 날짜 데이터 요청 시
# 1시간(3600초)동안 API를 재호출하지 않고 저장된 결과를 사용합니다.
@st.cache_data(ttl=3600)
def fetch_daily_box_office(api_key: str, date_str: str):
    """
    KOBIS(영화관입장권통합전산망) API를 호출하여 일별 박스오피스 데이터를 가져오는 함수
    """
    url = "https://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/searchDailyBoxOfficeList.json"
    params = {
        "key": api_key,
        "targetDt": date_str
    }
    
    try:
        # API 서버에 데이터 요청 (10초 타임아웃)
        response = requests.get(url, params=params, timeout=10)
        # HTTP 응답 상태 코드가 200이 아니면 예외 발생
        response.raise_for_status()
        return response.json(), None
    except requests.exceptions.RequestException as error:
        # 네트워크 연결 문제 또는 서버 오류 처리
        return None, f"네트워크 통신 오류가 발생했습니다: {error}"

st.title("🎬 어제의 박스오피스 순위")
st.caption(f"📅 기준 날짜: **{display_date}** (한국 시간 기준 어제 데이터)")
st.markdown("---")

# Streamlit Secrets(비밀 금고)에 인증키가 설정되어 있는지 확인합니다.
if "KOBIS_KEY" not in st.secrets or not st.secrets["KOBIS_KEY"]:
    st.error("⚠️ KOBIS API 인증키가 설정되지 않았습니다.")
    st.info(
        "**[안내 및 확인 사항]**\n"
        "1. 영화관입장권통합전산망(KOBIS) 개발자센터에서 발급받은 API 키가 필요합니다.\n"
        "2. **로컬 개발 환경**: 프로젝트 폴더 내 `.streamlit/secrets.toml` 파일에 아래 내용을 작성해 주세요.\n"
        "   ```toml\n"
        "   KOBIS_KEY = \"발급받은_API_키_입력\"\n"
        "   ```\n"
        "3. **Streamlit Cloud 배포**: App Settings -> **Secrets** 메뉴에서 `KOBIS_KEY` 항목을 등록해 주세요."
    )
    st.stop()

# 비밀 금고에서 안전하게 인증키를 가져옵니다.
api_key = st.secrets["KOBIS_KEY"]

with st.spinner("영화관입장권통합전산망에서 최신 박스오피스 데이터를 가져오는 중입니다..."):
    data, error_msg = fetch_daily_box_office(api_key, target_dt)

if error_msg:
    st.error("⚠️ 데이터를 불러오는 중 오류가 발생했습니다.")
    st.warning(
        f"**상세 내용**: {error_msg}\n\n"
        "**[확인 항목]**\n"
        "- 인터넷 연결 상태가 정상인지 확인해 주세요.\n"
        "- KOBIS API 서버가 일시적인 점검 중일 수 있으니 잠시 후 다시 시도해 주세요."
    )
    st.stop()

# KOBIS API는 인증키 오류 시에도 HTTP 200을 반환하며 응답 내 'faultInfo' 객체를 포함합니다.
if "faultInfo" in data:
    fault = data["faultInfo"]
    st.error("⚠️ KOBIS API 응답 오류가 발생했습니다.")
    st.warning(
        f"**오류 메시지**: {fault.get('message', '알 수 없는 오류')}\n"
        f"**오류 코드**: {fault.get('errorCode', 'N/A')}\n\n"
        "**[확인 항목]**\n"
        "1. Secrets에 입력한 `KOBIS_KEY`가 올바른 키인지 다시 한번 확인해 주세요.\n"
        "2. KOBIS 개발자센터에서 일일 요청 제한 건수를 초과했는지 확인해 주세요."
    )
    st.stop()

box_office_result = data.get("boxOfficeResult", {})
daily_list = box_office_result.get("dailyBoxOfficeList", [])

if not daily_list:
    st.warning("⚠️ 어제의 박스오피스 데이터가 존재하지 않거나 비어 있습니다.")
    st.info(
        "**[확인 항목]**\n"
        "- 아직 KOBIS 측의 어제 일자 박스오피스 마감 집계가 완료되지 않았을 수 있습니다.\n"
        "- 잠시 후 페이지를 새로고침해 주세요."
    )
    st.stop()

# API 응답 결과는 모든 숫자가 문자열로 전달되므로 연산 및 시각화를 위해 정수형(int)으로 변환합니다.
df = pd.DataFrame(daily_list)

numeric_columns = ["rank", "rankInten", "audiCnt", "audiAcc", "scrnCnt", "showCnt"]
for col in numeric_columns:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

# 순위 기준으로 오름차순 정렬
df = df.sort_values(by="rank").reset_index(drop=True)

# 1위 영화 정보를 크게 지표 카드 3장으로 시각화합니다.
top_1_movie = df.iloc[0]

st.subheader(f"🥇 1위 영화: {top_1_movie['movieNm']}")

col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        label="당일 관객수",
        value=f"{top_1_movie['audiCnt']:,} 명",
        delta=f"전일 대비 {top_1_movie['rankInten']}위" if top_1_movie['rankInten'] != 0 else "순위 변동 없음"
    )

with col2:
    st.metric(
        label="누적 관객수",
        value=f"{top_1_movie['audiAcc']:,} 명"
    )

with col3:
    st.metric(
        label="스크린 수",
        value=f"{top_1_movie['scrnCnt']:,} 개"
    )

st.markdown("---")

# 관객수 상위 5개 영화를 막대그래프로 시각화합니다.
st.subheader("📊 관객수 TOP 5 막대그래프")

top_5_df = df.head(5).copy()
chart_data = top_5_df[["movieNm", "audiCnt"]].rename(
    columns={"movieNm": "영화명", "audiCnt": "당일 관객수"}
)

st.bar_chart(
    data=chart_data,
    x="영화명",
    y="당일 관객수",
    use_container_width=True
)

st.markdown("---")

# 전체 순위, 영화명, 개봉일, 관객수, 누적관객, 스크린수를 표로 출력합니다.
st.subheader("📋 전체 박스오피스 상세 목록")

# 필요한 컬럼 추출 및 한글 컬럼명으로 변경
display_df = df[["rank", "movieNm", "openDt", "audiCnt", "audiAcc", "scrnCnt"]].copy()
display_df.columns = ["순위", "영화명", "개봉일", "당일 관객수", "누적 관객수", "스크린수"]

# 테이블 숫자에 천 단위 콤마(,) 포맷팅 적용
st.dataframe(
    display_df,
    use_container_width=True,
    hide_index=True,
    column_config={
        "순위": st.column_config.NumberColumn("순위", format="%d"),
        "당일 관객수": st.column_config.NumberColumn("당일 관객수", format="%'d 명"),
        "누적 관객수": st.column_config.NumberColumn("누적 관객수", format="%'d 명"),
        "스크린수": st.column_config.NumberColumn("스크린수", format="%'d 개"),
    }
)
