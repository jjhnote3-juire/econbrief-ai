import streamlit as st
import yfinance as yf
import google.generativeai as genai
import plotly.graph_objects as go
import os
import re
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

st.set_page_config(page_title="EconBrief AI", page_icon="🌤️", layout="wide")

# ==========================================
# 📧 이메일 발송 함수
# ==========================================
def send_email(ai_text, news_text):
    # 👇 본인 정보로 수정 필수!
    sender_email = st.secrets["SENDER_EMAIL"]
    app_password = st.secrets["APP_PASSWORD"]
    receiver_email = "jjhnote3@gmail.com" 

    msg = MIMEMultipart()
    msg['Subject'] = '🌤️ 오늘의 EconBrief AI 모닝 브리핑'
    msg['From'] = sender_email
    msg['To'] = receiver_email

    html_content = f"<html><body><h2>📈 시황 분석</h2><p>{ai_text}</p><hr><h2>📰 뉴스</h2><p>{news_text.replace(chr(10), '<br>')}</p></body></html>"
    msg.attach(MIMEText(html_content, 'html'))

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(sender_email, app_password)
            server.send_message(msg)
        return True
    except Exception as e:
        st.error(f"발송 실패: {e}")
        return False

# ==========================================
# 0. 세션 상태(메모장) 초기화 - 데이터 유지의 핵심
# ==========================================
if "briefing_data" not in st.session_state:
    st.session_state.briefing_data = None

# ==========================================
# 1. 사이드바 메뉴
# ==========================================
with st.sidebar:
    st.title("📋 메뉴")
    menu = st.radio("이동할 페이지를 선택하세요:", ["🏠 홈 (오늘의 브리핑)", "📖 EconBrief AI 란?"], key="menu_radio")

# ==========================================
# 📖 가이드 페이지
# ==========================================
if menu == "📖 EconBrief AI 란?":
    st.title("📖 EconBrief AI 소개")
    st.write("초보자를 위한 경제 비서 서비스입니다.")
    st.info("☀️ 맑음: 상승장 | ☁️ 흐림: 혼조세 | ☔ 비: 하락장")

# ==========================================
# 🏠 홈 화면
# ==========================================
else:
    st.title("🌤️ EconBrief AI 모닝 브리핑")
    st.write("경제 데이터와 AI의 통찰을 결합한 브리핑입니다. ☕")
    st.divider()

    # API 설정 (키 입력 필수!)
    MY_API_KEY = st.secrets["API_KEY"]
    genai.configure(api_key=MY_API_KEY, transport="rest")
    model = genai.GenerativeModel('gemini-2.5-flash')

    def get_data_and_change(ticker):
        hist = yf.Ticker(ticker).history(period="5d")
        current, previous = round(hist['Close'].iloc[-1], 2), round(hist['Close'].iloc[-2], 2)
        change = round(current - previous, 2)
        pct = round((change / previous) * 100, 2)
        return current, change, pct

    @st.cache_data(ttl=3600, show_spinner=False)
    def get_morning_briefing():
        ndx = get_data_and_change("^IXIC")
        tnx = get_data_and_change("^TNX")
        vix = get_data_and_change("^VIX")
        krw = get_data_and_change("KRW=X")

        spy_news = yf.Ticker("SPY").news[:3]
        qqq_news = yf.Ticker("QQQ").news[:3]
        all_news = spy_news + qqq_news
        news_titles, news_text = [], ""
        for news in all_news:
            title = news.get('title', '제목 없음')
            if title not in news_titles and title != '제목 없음':
                news_titles.append(title)
                news_text += f"{len(news_titles)}. {title}\n"

        prompt = f"""
        당신은 전문 경제 아나운서입니다.
        [데이터] 나스닥:{ndx[0]}({ndx[2]}%), 금리:{tnx[0]}%, VIX:{vix[0]}, 환율:{krw[0]}원
        [뉴스] {news_text}
        형식: 1. 시장 날씨, 2. KOSPI 타격 예상, 3. 부동산/대출 영향.
        용어설명: 어려운 용어는 <abbr title='뜻'>용어</abbr> 태그 사용.
        """
        response = model.generate_content(prompt)
        return ndx, tnx, vix, krw, news_text, response.text

    # --- 브리핑 가져오기 버튼 (고유 KEY 부여) ---
    if st.button("🔄 오늘 아침 브리핑 가져오기", key="get_briefing_btn"):
        with st.spinner('분석 중...'):
            ndx, tnx, vix, krw, news_text, ai_text = get_morning_briefing()
            
            # 오디오 생성
            audio_text = re.sub(r'<[^>]+>', '', ai_text)
            audio_text = audio_text.replace("☀️", "").replace("☁️", "").replace("☔", "").replace("☕", "").replace("*", "").replace("#", "")
            with open("script.txt", "w", encoding="utf-8") as f: f.write(audio_text)
            os.system('python -m edge_tts --file script.txt --voice ko-KR-SunHiNeural --rate=+20% --write-media briefing_audio.mp3')
            
            # 메모장에 저장
            st.session_state.briefing_data = {
                "ndx": ndx, "tnx": tnx, "vix": vix, "krw": krw, "news_text": news_text, "ai_text": ai_text
            }

    # 데이터가 있을 때만 화면 표시
    if st.session_state.briefing_data:
        d = st.session_state.briefing_data
        
        col_t, col_a = st.columns([2, 1])
        with col_t:
            st.subheader("💡 AI의 거시경제 시황 분석")
            st.caption("🔍 점선 밑줄 단어에 마우스를 올려보세요.")
        with col_a:
            if os.path.exists("briefing_audio.mp3"):
                st.audio("briefing_audio.mp3", format='audio/mp3')
        
        st.markdown(d['ai_text'], unsafe_allow_html=True)
        
        # 메일 보내기 버튼 (고유 KEY 부여)
        if st.button("📨 이 브리핑을 내 이메일로 보내기", key="send_email_btn"):
            if send_email(d['ai_text'], d['news_text']):
                st.success("✅ 메일 발송 성공!")

        st.divider()
        st.subheader("📊 오늘의 핵심 지표 (전일 대비)")
        c1, c2, c3 = st.columns(3)
        c1.metric("나스닥", f"{d['ndx'][0]:,} pt", f"{d['ndx'][1]} ({d['ndx'][2]}%)")
        c2.metric("환율", f"{d['krw'][0]:,} 원", f"{d['krw'][1]} ({d['krw'][2]}%)", delta_color="inverse")
        c3.metric("미 10년물 금리", f"{d['tnx'][0]} %", f"{d['tnx'][1]} ({d['tnx'][2]}%)", delta_color="inverse")
        
        st.divider()
        st.subheader("🚨 현재 시장의 공포 탐욕 지수 (VIX)")
        fig = go.Figure(go.Indicator(
            mode = "gauge+number+delta", value = d['vix'][0],
            delta = {'reference': d['vix'][0] - d['vix'][1], 'increasing': {'color': "red"}},
            gauge = {'axis': {'range': [None, 40]}, 'steps': [{'range': [0, 15], 'color': "#b2f2bb"}, {'range': [15, 25], 'color': "#ffec99"}, {'range': [25, 40], 'color': "#ffa8a8"}]}
        ))
        fig.update_layout(height=250, margin=dict(l=20, r=20, t=30, b=20))
        st.plotly_chart(fig, use_container_width=True)

        with st.expander("📰 원문 종합 뉴스 보기"):
            st.write(d['news_text'])

  # (기존 코드의 st.expander 뉴스 보기 아래쪽부터)
    # ==========================================
    # 📬 매일 아침 브리핑 자동 구독 시스템 (구글 시트 연동)
    # ==========================================
    st.divider()
    st.subheader("📬 매일 아침 7시, 브리핑 자동 구독하기")
    
    col_i, col_b = st.columns([3, 1])
    with col_i:
        user_email = st.text_input("이메일 주소", key="sub_email_input", placeholder="example@gmail.com", label_visibility="collapsed")
    with col_b:
        if st.button("구독하기", key="sub_confirm_btn"):
            if "@" in user_email and "." in user_email:
               with st.spinner("매일 아침 찾아갈 주소를 정성껏 적고 있습니다... ☕"):
                    try:
                        import gspread
                        from oauth2client.service_account import ServiceAccountCredentials
                        import datetime

                        # 1. 구글 시트 인증 출입증 꺼내기
                        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
                        import json
                        creds_dict = json.loads(st.secrets["GCP_CREDENTIALS"])
                        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
                        client = gspread.authorize(creds)

                        # 2. 'EconBrief 구독자' 시트 열기
                        sheet = client.open("EconBrief 구독자").sheet1

                        # 3. 새로운 행에 데이터 추가하기 (이메일, 현재시간)
                        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        sheet.append_row([user_email, now])

                        st.success("🎉 구독 완료! 안전하게 데이터베이스에 저장되었습니다.")
                        st.balloons()
                    except Exception as e:
                        st.error(f"구글 시트 저장 실패: {e}\n(secrets.json 파일 위치와 시트 공유 상태를 확인하세요!)")
            else:
                st.error("⚠️ 올바른 이메일 주소를 입력해주세요.")

