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
# 0. 세션 상태(메모장) 초기화
# ==========================================
if "briefing_data" not in st.session_state:
    st.session_state.briefing_data = None
# [신규] 로그인된 사용자 이메일을 기억하는 메모장
if "logged_in_user" not in st.session_state:
    st.session_state.logged_in_user = None

# ==========================================
# 📧 이메일 발송 함수
# ==========================================
def send_email(ai_text, news_text):
    sender_email = st.secrets["SENDER_EMAIL"]
    app_password = st.secrets["APP_PASSWORD"]
    # 현재 로그인한 사람이 있으면 그 사람에게, 없으면 본인(테스트)에게 발송
    receiver_email = st.session_state.logged_in_user if st.session_state.logged_in_user else st.secrets["SENDER_EMAIL"]

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
# 1. 사이드바 메뉴 및 로그인 상태 표시
# ==========================================
with st.sidebar:
    st.title("📋 메뉴")
    menu = st.radio("이동할 페이지를 선택하세요:", ["🏠 홈 (오늘의 브리핑)", "📖 이브(Eve)란?", "👤 가입 / 로그인"], key="menu_radio")
    
    st.divider()
    # 로그인 상태 표시기
    if st.session_state.logged_in_user:
        st.success(f"👋 환영합니다!\n**{st.session_state.logged_in_user}** 님")
        if st.button("로그아웃"):
            st.session_state.logged_in_user = None
            st.rerun() # 화면 새로고침
    else:
        st.info("로그인하고 이브의 모닝 브리핑을 구독해 보세요!")

# ==========================================
# 👤 가입 / 로그인 페이지 (이메일 간편 로그인)
# ==========================================
if menu == "👤 가입 / 로그인":
    st.title("👤 이브(Eve)와 함께하기")
    
    if st.session_state.logged_in_user:
        st.write("이미 로그인되어 있습니다. 홈 화면에서 오늘의 브리핑을 확인해 보세요!")
    else:
        st.write("비밀번호 없이 **이메일만으로** 간편하게 가입하고 로그인하세요.")
        
        with st.container(border=True):
            login_email = st.text_input("이메일 주소", placeholder="example@gmail.com")
            want_newsletter = st.checkbox("📬 매일 아침 7시 이브의 모닝 브리핑 이메일로 받기 (무료)", value=True)
            
            if st.button("시작하기", use_container_width=True):
                # 💡 [핵심 방어막] 허용할 대형 이메일 도메인 리스트
                allowed_domains = ["gmail.com", "naver.com", "daum.net", "kakao.com", "hanmail.net", "nate.com", "icloud.com"]
                
                if "@" in login_email and "." in login_email:
                    # 입력한 이메일에서 @ 뒤의 도메인만 잘라내서 소문자로 변환 (예: NaVer.com -> naver.com)
                    domain = login_email.split("@")[1].lower()
                    
                    if domain in allowed_domains:
                        # 1. 로그인 성공 처리
                        st.session_state.logged_in_user = login_email
                        
                        # 2. 브리핑 수신에 체크했을 경우에만 구글 시트(DB)에 저장
                        if want_newsletter:
                            with st.spinner("구독 명단에 소중한 이메일을 등록하는 중입니다... 💌"):
                                try:
                                    import gspread
                                    from oauth2client.service_account import ServiceAccountCredentials
                                    import datetime
                                    import json

                                    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
                                    creds_dict = json.loads(st.secrets["GCP_CREDENTIALS"])
                                    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
                                    client = gspread.authorize(creds)

                                    sheet = client.open("EconBrief 구독자").sheet1
                                    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                    sheet.append_row([login_email, now])

                                    st.success("🎉 가입 및 브리핑 구독이 완료되었습니다!")
                                    st.balloons()
                                except Exception as e:
                                    st.error(f"로그인은 되었으나, 구글 시트 저장에 실패했습니다. 관리자에게 문의하세요. ({e})")
                        else:
                            st.success("🎉 성공적으로 로그인되었습니다! (브리핑 메일은 발송되지 않습니다.)")
                            st.balloons()
                    else:
                        # 도메인이 허용 목록에 없을 때 튕겨내기!
                        st.error("⚠️ 봇(Bot) 무단 가입 방지를 위해 구글, 네이버, 다음, 카카오 등 주요 포털 이메일로만 가입할 수 있습니다.")
                else:
                    st.error("⚠️ 올바른 이메일 형식을 입력해주세요.")
# ==========================================
# 📖 가이드 페이지
# ==========================================
elif menu == "📖 이브(Eve)란?":
    st.title("📖 EconBrief AI 소개")
    st.write("초보자를 위한 똑똑한 경제 비서, 이브(Eve)입니다.")
    st.info("☀️ 맑음: 상승장 | ☁️ 흐림: 혼조세 | ☔ 비: 하락장")

# ==========================================
# 🏠 홈 화면 (비밀번호 없이 바로 접근!)
# ==========================================
elif menu == "🏠 홈 (오늘의 브리핑)":
    st.title("🌤️ 이브(Eve)의 모닝 브리핑")
    st.write("경제 데이터와 AI 비서 이브의 통찰을 결합한 브리핑입니다. ☕")
    st.divider()

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

        news_titles, news_text = [], ""
        try:
            spy_ticker = yf.Ticker("SPY")
            all_news = spy_ticker.get_news()[:5] 
            for news in all_news:
                title = news.get('title', '')
                if title and title not in news_titles:
                    news_titles.append(title)
                    news_text += f"{len(news_titles)}. {title}\n"
        except Exception:
            news_text = "현재 클라우드 서버 통신 문제로 실시간 뉴스를 불러오지 못했습니다."

        if not news_text.strip():
            news_text = "오늘 장에 큰 영향을 미칠만한 특별한 거시경제 주요 뉴스가 없습니다."

        prompt = f"""
        너는 사용자의 스마트한 경제 비서이자 전속 아나운서인 '이브(Eve)'야.
        
        [데이터] 나스닥:{ndx[0]}({ndx[2]}%), 금리:{tnx[0]}%, VIX:{vix[0]}, 환율:{krw[0]}원
        [뉴스] {news_text}
        
        위 데이터를 바탕으로 아래 규칙을 지켜서 브리핑을 작성해.
        1. 시작할 때 반드시 "안녕하세요! 여러분의 경제 비서 이브입니다." 라고 다정하게 인사할 것.
        2. [시장의 날씨와 변화량]: 날씨 이모티콘으로 분위기 표현, 수치 변화 설명.
        3. [오늘의 KOSPI 타격 예상]: 미장 결과가 한국 증시에 미칠 영향.
        4. [국내 부동산/대출 금리 영향]: 미 국채 금리와 환율이 한국 시장 금리에 미칠 영향.
        어려운 용어는 반드시 <abbr title='뜻'>용어</abbr> 태그를 사용할 것.
        """
        response = model.generate_content(prompt)
        return ndx, tnx, vix, krw, news_text, response.text

    # --- 브리핑 가져오기 버튼 ---
    if st.button("🔄 오늘 아침 브리핑 가져오기", key="get_briefing_btn"):
        with st.spinner('이브가 시장 데이터를 분석 중입니다...'):
            ndx, tnx, vix, krw, news_text, ai_text = get_morning_briefing()
            
            audio_text = re.sub(r'<[^>]+>', '', ai_text)
            audio_text = audio_text.replace("☀️", "").replace("☁️", "").replace("☔", "").replace("☕", "").replace("*", "").replace("#", "")
            with open("script.txt", "w", encoding="utf-8") as f: f.write(audio_text)
            
            os.system('edge-tts --file script.txt --voice ko-KR-SunHiNeural --rate=+20% --write-media briefing_audio.mp3')
            
            st.session_state.briefing_data = {
                "ndx": ndx, "tnx": tnx, "vix": vix, "krw": krw, "news_text": news_text, "ai_text": ai_text
            }

    # --- 데이터가 있을 때 화면 표시 ---
    if st.session_state.briefing_data:
        d = st.session_state.briefing_data
        
        col_t, col_a = st.columns([2, 1])
        with col_t:
            st.subheader("💡 AI 비서 이브의 거시경제 분석")
            st.caption("🔍 점선 밑줄 단어에 마우스를 올려보세요.")
        with col_a:
            if os.path.exists("briefing_audio.mp3"):
                st.audio("briefing_audio.mp3", format='audio/mp3')
        
        st.markdown(d['ai_text'], unsafe_allow_html=True)
        
        # 메일 보내기 버튼 (로그인된 상태라면 내 메일로, 아니면 개발자 테스트용으로)
        if st.button("📨 이 브리핑을 내 이메일로 보내기", key="send_email_btn"):
            if not st.session_state.logged_in_user:
                st.warning("로그인 후 이용하시면 입력하신 이메일로 발송됩니다! (현재는 테스트 계정으로 발송됩니다)")
            
            with st.spinner("이브가 브리핑을 전송 중입니다... 💌"):
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

