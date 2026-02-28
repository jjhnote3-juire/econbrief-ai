import streamlit as st
import yfinance as yf
import google.generativeai as genai
import plotly.graph_objects as go
import pandas as pd
import os
import re
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import datetime
import requests

st.set_page_config(page_title="EconBrief AI", page_icon="🌤️", layout="wide")

# ==========================================
# 0. 세션 상태 초기화
# ==========================================
if "briefing_data" not in st.session_state:
    st.session_state.briefing_data = None
if "logged_in_user" not in st.session_state:
    st.session_state.logged_in_user = None
if "kmacro_data" not in st.session_state:
    st.session_state.kmacro_data = None

# ==========================================
# 📧 이메일 & 텔레그램 발송 함수
# ==========================================
def send_email(ai_text, news_text):
    sender_email = st.secrets["SENDER_EMAIL"]
    app_password = st.secrets["APP_PASSWORD"]
    receiver_email = st.session_state.logged_in_user if st.session_state.logged_in_user else st.secrets["SENDER_EMAIL"]

    msg = MIMEMultipart()
    msg['Subject'] = '🌤️ 오늘의 이브(Eve) 모닝 브리핑'
    msg['From'] = sender_email
    msg['To'] = receiver_email

    html_content = f"<html><body><h2>📈 시황 분석</h2><p>{ai_text}</p><hr><h2>📰 뉴스</h2><p>{news_text.replace(chr(10), '<br>')}</p><hr><p style='color:gray; font-size:12px;'><i>[면책 조항] 본 메일은 투자 참고용입니다.</i></p></body></html>"
    msg.attach(MIMEText(html_content, 'html'))
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(sender_email, app_password)
            server.send_message(msg)
        return True
    except Exception as e:
        return False

def send_telegram_message(text):
    try:
        token = st.secrets["TELEGRAM_BOT_TOKEN"]
        chat_id = st.secrets["TELEGRAM_CHAT_ID"]
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        clean_text = text.replace("<br>", "\n").replace("<b>", "🔥 ").replace("</b>", " 🔥")
        requests.post(url, data={"chat_id": chat_id, "text": clean_text, "parse_mode": "HTML"})
    except: pass

is_admin_mode = st.query_params.get("admin") == "true"

# ==========================================
# 1. 사이드바 (구독/가입 창 통합)
# ==========================================
with st.sidebar:
    st.title("🌤️ EconBrief AI")
    
    st.subheader("👤 내 계정")
    if st.session_state.logged_in_user:
        st.success(f"👋 환영합니다!\n**{st.session_state.logged_in_user}** 님")
        if st.button("로그아웃", use_container_width=True):
            st.session_state.logged_in_user = None
            st.rerun()
        
        # 로그인된 상태에서도 텔레그램 방을 찾을 수 있게 버튼 제공
        st.divider()
        st.write("💡 이브의 실시간 속보 채널")
        st.link_button("📲 공식 텔레그램 입장하기", "https://t.me/여기에_채널_링크_입력", type="primary", use_container_width=True)
            
    else:
        # 🌟 이름 변경 및 텔레그램 버튼 통합!
        with st.expander("💌 멤버십 가입 및 채널 입장", expanded=True):
            st.markdown("**1️⃣ 이메일 브리핑 무료 구독**")
            login_email = st.text_input("이메일 주소", placeholder="example@gmail.com", label_visibility="collapsed")
            want_newsletter = st.checkbox("📬 매일 아침 브리핑 받기", value=True)
            
            if st.button("구독 시작하기", use_container_width=True):
                allowed_domains = ["gmail.com", "naver.com", "daum.net", "kakao.com", "hanmail.net", "nate.com", "icloud.com"]
                if "@" in login_email and "." in login_email:
                    domain = login_email.split("@")[1].lower()
                    if domain in allowed_domains:
                        st.session_state.logged_in_user = login_email
                        if want_newsletter:
                            with st.spinner("등록 중..."):
                                try:
                                    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
                                    creds_dict = json.loads(st.secrets["GCP_CREDENTIALS"], strict=False)
                                    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
                                    client = gspread.authorize(creds)
                                    client.open("EconBrief 구독자").sheet1.append_row([login_email, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
                                    st.success("🎉 구독 완료!")
                                    st.balloons()
                                except: st.error("가입 실패")
                        else: st.success("🎉 로그인 성공!")
                    else: st.error("⚠️ 주요 포털 이메일만 허용됩니다.")
                else: st.error("⚠️ 올바른 이메일 형식을 입력해주세요.")
            
            st.divider()
            st.markdown("**2️⃣ 실시간 텔레그램 속보방**")
            st.write("이메일보다 빠른 앱 전용 속보 채널!")
            # 👇 여기에 대표님의 텔레그램 채널 주소를 넣어주세요
            st.link_button("📲 공식 텔레그램 입장하기", "https://t.me/여기에_채널_링크_입력", type="primary", use_container_width=True)
            
            st.caption("⚠️ 이용 시 [면책조항]에 동의한 것으로 간주됩니다.")
                    
    st.divider()
    
    st.subheader("📋 메뉴")
    menu_options = ["🏠 글로벌 대시보드", "🇰🇷 K-Macro 딥다이브", "📖 이브(Eve)란?", "📜 이용약관 및 면책조항"]
    if is_admin_mode:
        menu_options.append("🛠️ 관리자 관제실 (Admin)")
        
    menu = st.radio("이동할 페이지를 선택하세요:", menu_options, label_visibility="collapsed")

# 공통 함수
MY_API_KEY = st.secrets["API_KEY"]
genai.configure(api_key=MY_API_KEY, transport="rest")
model = genai.GenerativeModel('gemini-2.5-flash')

def get_data_and_change(ticker):
    hist = yf.Ticker(ticker).history(period="5d")
    current, previous = round(hist['Close'].iloc[-1], 2), round(hist['Close'].iloc[-2], 2)
    return current, round(current - previous, 2), round(((current - previous) / previous) * 100, 2)

# ==========================================
# 🏠 1. 글로벌 대시보드 (터미널 스타일 개편)
# ==========================================
if menu == "🏠 글로벌 대시보드":
    st.title("🌎 글로벌 경제 대시보드")
    st.write("월스트리트의 핵심 지표와 이브(Eve)의 시황 분석을 한눈에 파악하세요.")
    
    @st.cache_data(ttl=3600, show_spinner=False)
    def get_morning_briefing():
        ndx, tnx, vix, krw = get_data_and_change("^IXIC"), get_data_and_change("^TNX"), get_data_and_change("^VIX"), get_data_and_change("KRW=X")
        news_titles, news_text = [], ""
        try:
            for news in yf.Ticker("SPY").get_news()[:5]:
                if news.get('title') and news.get('title') not in news_titles:
                    news_titles.append(news.get('title'))
                    news_text += f"• {news.get('title')}\n"
        except: news_text = "뉴스 업데이트 지연"
        
        prompt = f"""너는 경제 비서 '이브'야. [데이터] 나스닥:{ndx[0]}({ndx[2]}%), 금리:{tnx[0]}%, VIX:{vix[0]}, 환율:{krw[0]}원
        [뉴스] {news_text}
        1. 다정하게 인사하고, 시장 날씨와 핵심 동향을 분석해.
        2. 절대 단정적인 투자 권유는 피하고 중립적인 어조를 써.
        3. 마크다운(*, #) 쓰지 말고 HTML <b>, <br>만 사용해."""
        return ndx, tnx, vix, krw, news_text, model.generate_content(prompt).text

    if st.button("🔄 최신 글로벌 브리핑 생성", key="get_briefing_btn", type="primary"):
        with st.spinner('글로벌 시장 데이터를 스캔 중입니다...'):
            ndx, tnx, vix, krw, news_text, ai_text = get_morning_briefing()
            st.session_state.briefing_data = {"ndx": ndx, "tnx": tnx, "vix": vix, "krw": krw, "news_text": news_text, "ai_text": ai_text}

    if st.session_state.briefing_data:
        d = st.session_state.briefing_data
        
        # 📊 상단: 핵심 지표 카드 4개 배치
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("🇺🇸 나스닥", f"{d['ndx'][0]:,} pt", f"{d['ndx'][1]} ({d['ndx'][2]}%)")
        c2.metric("💵 원/달러 환율", f"{d['krw'][0]:,} 원", f"{d['krw'][1]} ({d['krw'][2]}%)", delta_color="inverse")
        c3.metric("📈 미 10년물 금리", f"{d['tnx'][0]} %", f"{d['tnx'][1]} bp", delta_color="inverse")
        c4.metric("🚨 공포지수(VIX)", f"{d['vix'][0]}", f"{d['vix'][1]}", delta_color="inverse")
        
        st.divider()
        
        # 🖥️ 하단: 2단 분리 대시보드 (왼쪽: AI 브리핑 / 오른쪽: 뉴스 및 차트)
        col_main, col_side = st.columns([7, 3])
        
        with col_main:
            st.subheader("💡 이브(Eve)의 시황 브리핑")
            st.markdown(d['ai_text'], unsafe_allow_html=True)
            if st.button("📨 내 이메일로 이 브리핑 보내기"):
                send_email(d['ai_text'], d['news_text'])
                st.toast("✅ 메일이 성공적으로 발송되었습니다!")
                
        with col_side:
            st.subheader("🚨 현재 시장 온도")
            fig = go.Figure(go.Indicator(
                mode = "gauge+number", value = d['vix'][0],
                gauge = {'axis': {'range': [None, 40]}, 'bar': {'color': "black"}, 'steps': [{'range': [0, 15], 'color': "#b2f2bb"}, {'range': [15, 25], 'color': "#ffec99"}, {'range': [25, 40], 'color': "#ffa8a8"}]}
            ))
            fig.update_layout(height=200, margin=dict(l=10, r=10, t=10, b=10))
            st.plotly_chart(fig, use_container_width=True)
            
            st.subheader("📰 월스트리트 헤드라인")
            st.info(d['news_text'].replace("\n", "\n\n"))

# ==========================================
# 🇰🇷 2. K-Macro 딥다이브 (신규 탭!)
# ==========================================
elif menu == "🇰🇷 K-Macro 딥다이브":
    st.title("🇰🇷 K-Macro (국내 거시경제) 딥다이브")
    st.write("KOSPI 흐름과 원/달러 환율 등 대한민국 경제의 체력을 깊이 있게 분석합니다.")
    
    if st.button("📊 KOSPI 및 환율 심층 분석하기", type="primary"):
        with st.spinner('한국 증시와 환율 데이터를 수집 중입니다...'):
            ks11 = get_data_and_change("^KS11") # 코스피
            kq11 = get_data_and_change("^KQ11") # 코스닥
            krw = get_data_and_change("KRW=X")  # 환율
            
            # 최근 1개월 코스피 차트 데이터
            kospi_hist = yf.Ticker("^KS11").history(period="1mo")
            
            prompt = f"""
            너는 거시경제 전문가 '이브'야. 
            [한국 데이터] KOSPI:{ks11[0]}({ks11[2]}%), KOSDAQ:{kq11[0]}({kq11[2]}%), 원/달러환율:{krw[0]}원
            1. 현재 환율이 수출입 기업과 KOSPI에 미치는 영향을 분석해.
            2. 한국은행(BOK)의 통화 정책 스탠스나 국내 물가(CPI) 우려에 대해 간략히 코멘트해.
            3. 마크다운 쓰지 말고 <b>와 <br>만 사용해.
            """
            k_ai_text = model.generate_content(prompt).text
            st.session_state.kmacro_data = {"ks11": ks11, "kq11": kq11, "krw": krw, "chart": kospi_hist, "ai": k_ai_text}

    if st.session_state.kmacro_data:
        k = st.session_state.kmacro_data
        
        c1, c2, c3 = st.columns(3)
        c1.metric("KOSPI (코스피)", f"{k['ks11'][0]:,} pt", f"{k['ks11'][1]} ({k['ks11'][2]}%)")
        c2.metric("KOSDAQ (코스닥)", f"{k['kq11'][0]:,} pt", f"{k['kq11'][1]} ({k['kq11'][2]}%)")
        c3.metric("원/달러 환율", f"{k['krw'][0]:,} 원", f"{k['krw'][1]} ({k['krw'][2]}%)", delta_color="inverse")
        
        st.divider()
        col1, col2 = st.columns([1, 1])
        with col1:
            st.subheader("📈 KOSPI 최근 1개월 추이")
            st.line_chart(k['chart']['Close'], color="#ff4b4b")
        with col2:
            st.subheader("💡 K-Macro 심층 리포트")
            st.markdown(k['ai'], unsafe_allow_html=True)
            st.caption("※ 참고: 향후 한국은행 OPEN API 연동을 통해 실시간 BSI 및 CPI 지표가 추가될 예정입니다.")

# ==========================================
# 📖 이브(Eve)란? & 📜 면책조항 & 🛠️ 관리자
# ==========================================
elif menu == "📖 이브(Eve)란?":
    st.title("📖 경제 비서, 이브(Eve)를 소개합니다")
    st.write("초보자를 위한 똑똑한 경제 비서, 이브입니다.")
    st.info("EconBrief AI는 매일 아침 복잡한 경제 뉴스를 분석하여 '경제 날씨'로 번역해 줍니다.")

elif menu == "📜 이용약관 및 면책조항":
    st.title("📜 법적 면책조항")
    st.write("본 서비스의 모든 정보는 참고용이며, 투자 결과에 대한 책임은 투자자 본인에게 있습니다.")

elif menu == "🛠️ 관리자 관제실 (Admin)":
    st.title("🚨 긴급 속보 관제실")
    admin_pw = st.text_input("🔑 비밀번호", type="password")
    if admin_pw == st.secrets.get("ADMIN_PASSWORD", ""):
        issue_text = st.text_input("이슈 입력")
        if st.button("발송"):
            st.success("발송 테스트 모드 활성화됨 (전체 코드 참조)")
