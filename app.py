import streamlit as st
import yfinance as yf
import google.generativeai as genai
import plotly.graph_objects as go
import os
import re
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import datetime
import requests  # 👈 텔레그램 통신을 위해 새로 추가된 도구!

st.set_page_config(page_title="EconBrief AI", page_icon="🌤️", layout="wide")

# ==========================================
# 0. 세션 상태 초기화
# ==========================================
if "briefing_data" not in st.session_state:
    st.session_state.briefing_data = None
if "logged_in_user" not in st.session_state:
    st.session_state.logged_in_user = None

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

    html_content = f"""
    <html><body>
    <h2>📈 시황 분석</h2><p>{ai_text}</p><hr><h2>📰 뉴스</h2><p>{news_text.replace(chr(10), '<br>')}</p>
    <hr>
    <p style='color:gray; font-size:12px;'><i>여러분의 경제 비서 이브(Eve)가 발송한 메일입니다.</i></p>
    <p style='color:#a0a0a0; font-size:10px; line-height:1.4;'><b>[면책 조항]</b> 본 메일의 내용은 투자 참고용이며, 법적 책임 소재의 증빙 자료로 사용될 수 없습니다. 투자의 최종 결정과 책임은 투자자 본인에게 있습니다.</p>
    </body></html>
    """
    msg.attach(MIMEText(html_content, 'html'))

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(sender_email, app_password)
            server.send_message(msg)
        return True
    except Exception as e:
        st.error(f"메일 발송 실패: {e}")
        return False

# 📱 텔레그램 발송 전용 함수
def send_telegram_message(text):
    try:
        token = st.secrets["TELEGRAM_BOT_TOKEN"]
        chat_id = st.secrets["TELEGRAM_CHAT_ID"]
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        
        # HTML 태그를 텔레그램용 마크다운이나 일반 텍스트로 조금 다듬어줍니다
        clean_text = text.replace("<br>", "\n").replace("<b>", "🔥 ").replace("</b>", " 🔥")
        
        payload = {"chat_id": chat_id, "text": clean_text, "parse_mode": "HTML"}
        requests.post(url, data=payload)
    except Exception as e:
        print(f"텔레그램 발송 실패: {e}")

is_admin_mode = st.query_params.get("admin") == "true"

# ==========================================
# 1. 사이드바 (로그인 우선 배치 -> 메뉴)
# ==========================================
with st.sidebar:
    st.title("🌤️ EconBrief AI")
    
    st.subheader("👤 내 계정")
    if st.session_state.logged_in_user:
        st.success(f"👋 환영합니다!\n**{st.session_state.logged_in_user}** 님")
        if st.button("로그아웃", use_container_width=True):
            st.session_state.logged_in_user = None
            st.rerun()
    else:
        with st.expander("🚀 이메일로 3초 간편 가입", expanded=True):
            login_email = st.text_input("이메일 주소", placeholder="example@gmail.com")
            want_newsletter = st.checkbox("📬 매일 아침 브리핑 구독", value=True)
            st.caption("⚠️ 가입 시 [이용약관 및 면책조항]에 동의한 것으로 간주됩니다.")
            
            if st.button("시작하기", use_container_width=True, type="primary"):
                allowed_domains = ["gmail.com", "naver.com", "daum.net", "kakao.com", "hanmail.net", "nate.com", "icloud.com"]
                if "@" in login_email and "." in login_email:
                    domain = login_email.split("@")[1].lower()
                    if domain in allowed_domains:
                        st.session_state.logged_in_user = login_email
                        if want_newsletter:
                            with st.spinner("명단 등록 중... 💌"):
                                try:
                                    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
                                    creds_dict = json.loads(st.secrets["GCP_CREDENTIALS"], strict=False)
                                    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
                                    client = gspread.authorize(creds)
                                    sheet = client.open("EconBrief 구독자").sheet1
                                    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                    sheet.append_row([login_email, now])
                                    st.success("🎉 가입 완료!")
                                    st.balloons()
                                except Exception as e:
                                    st.error(f"가입 실패: {e}")
                        else:
                            st.success("🎉 로그인 성공!")
                            st.balloons()
                    else:
                        st.error("⚠️ 무단 가입 방지를 위해 주요 포털 이메일만 허용됩니다.")
                else:
                    st.error("⚠️ 올바른 이메일 형식을 입력해주세요.")
                    
    st.divider()
    
    st.subheader("📋 메뉴")
    menu_options = ["🏠 홈 (오늘의 브리핑)", "📖 이브(Eve)란?", "📜 이용약관 및 면책조항"]
    if is_admin_mode:
        menu_options.append("🛠️ 관리자 관제실 (Admin)")
        
    menu = st.radio("이동할 페이지를 선택하세요:", menu_options, label_visibility="collapsed")

# ==========================================
# 🏠 홈 화면 
# ==========================================
if menu == "🏠 홈 (오늘의 브리핑)":
    st.title("🌤️ 이브(Eve)의 모닝 브리핑")
    st.write("경제 데이터와 AI 비서 이브의 통찰을 결합한 브리핑입니다. ☕")
    st.divider()

    MY_API_KEY = st.secrets["API_KEY"]
    genai.configure(api_key=MY_API_KEY, transport="rest")
    model = genai.GenerativeModel('gemini-2.5-flash')

    def get_data_and_change(ticker):
        hist = yf.Ticker(ticker).history(period="5d")
        current, previous = round(hist['Close'].iloc[-1], 2), round(hist['Close'].iloc[-2], 2)
        return current, round(current - previous, 2), round(((current - previous) / previous) * 100, 2)

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
            news_text = "현재 서버 통신 문제로 뉴스를 불러오지 못했습니다."

        if not news_text.strip():
            news_text = "오늘 장에 큰 영향을 미칠만한 거시경제 뉴스가 없습니다."

        prompt = f"""
        너는 사용자의 스마트한 경제 비서이자 전속 아나운서인 '이브(Eve)'야.
        [데이터] 나스닥:{ndx[0]}({ndx[2]}%), 금리:{tnx[0]}%, VIX:{vix[0]}, 환율:{krw[0]}원
        [뉴스] {news_text}
        
        1. 시작할 때 "안녕하세요! 여러분의 경제 비서 이브입니다." 라고 다정하게 인사해.
        2. 시장 날씨, KOSPI 예상, 대출 금리 영향을 분석해.
        3. [법적 규칙]: 절대 "매수/매도 하세요" 등 단정적인 권유를 하지 말고 중립적으로 작성해.
        4. 절대로 마크다운(*, #) 쓰지 말고 HTML <b>, <br>만 사용해.
        """
        response = model.generate_content(prompt)
        return ndx, tnx, vix, krw, news_text, response.text

    if st.button("🔄 오늘 아침 브리핑 가져오기", key="get_briefing_btn"):
        with st.spinner('이브가 시장 데이터를 분석 중입니다...'):
            ndx, tnx, vix, krw, news_text, ai_text = get_morning_briefing()
            audio_text = re.sub(r'<[^>]+>', '', ai_text).replace("☀️", "").replace("☁️", "").replace("☔", "").replace("☕", "")
            with open("script.txt", "w", encoding="utf-8") as f: f.write(audio_text)
            os.system('edge-tts --file script.txt --voice ko-KR-SunHiNeural --rate=+20% --write-media briefing_audio.mp3')
            st.session_state.briefing_data = {"ndx": ndx, "tnx": tnx, "vix": vix, "krw": krw, "news_text": news_text, "ai_text": ai_text}

    if st.session_state.briefing_data:
        d = st.session_state.briefing_data
        col_t, col_a = st.columns([2, 1])
        with col_t:
            st.subheader("💡 AI 비서 이브의 거시경제 분석")
        with col_a:
            if os.path.exists("briefing_audio.mp3"):
                st.audio("briefing_audio.mp3", format='audio/mp3')
        st.markdown(d['ai_text'], unsafe_allow_html=True)
        
        if st.button("📨 이 브리핑을 내 이메일로 보내기", key="send_email_btn"):
            if not st.session_state.logged_in_user:
                st.warning("로그인 후 이용하시면 입력하신 이메일로 발송됩니다!")
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
            
        st.divider()
        st.caption("⚠️ **[면책 조항]** 본 서비스는 투자 참고용이며, 이용 시 사이드바 메뉴의 [이용약관 및 면책조항]에 동의한 것으로 간주됩니다. 투자의 최종 결정과 책임은 본인에게 있습니다.")

# ==========================================
# 📖 이브(Eve) 소개 및 제작 배경
# ==========================================
elif menu == "📖 이브(Eve)란?":
    st.title("📖 경제 비서, 이브(Eve)를 소개합니다")
    st.subheader("👋 안녕하세요! 당신의 경제 비서, 이브입니다.")
    st.write("EconBrief AI는 매일 아침 쏟아지는 복잡한 월스트리트의 경제 뉴스와 지표들을 분석하여, 누구나 이해하기 쉬운 **'경제 날씨'**로 번역해 주는 인공지능 시황 브리핑 서비스입니다.")
    with st.container(border=True):
        st.subheader("💡 제작 배경 (Why Eve?)")
        st.write("""
        현대 사회에서 환율, 금리, 글로벌 증시의 흐름은 우리의 지갑 사정과 직결됩니다. 하지만 초보 투자자나 바쁜 현대인들이 매일 새벽에 발표되는 미국 연준(Fed)의 성명서나 블룸버그 기사 원문을 직접 찾아보고 해석하는 것은 시간적으로도, 심리적으로도 큰 장벽입니다.
        
        **"거시 경제(Macro-economics)의 거대한 흐름을 누구나 클릭 한 번으로, 마치 매일 아침 일기예보를 보듯 쉽게 파악할 수는 없을까?"**
        
        이러한 고민에서 출발하여 탄생한 것이 바로 '이브(Eve)'입니다. 이브는 어렵고 차가운 금융 지표와 숫자를 따뜻하고 친절한 언어로 풀어주어, 사용자들의 경제적 시야를 넓혀주고 현명한 의사결정을 돕는 든든한 파트너가 되고자 합니다.
        """)
    with st.container(border=True):
        st.subheader("✨ 이브의 3가지 핵심 능력")
        st.markdown("""
        1. **📊 실시간 데이터 스캐닝:** 나스닥, 미국 10년물 국채 금리, VIX(공포지수), 원/달러 환율 등 경제 핵심 지표를 매일 아침 자동으로 추적합니다.
        2. **🧠 AI 심층 분석:** 단순한 수치 나열을 넘어, 해당 지표의 변화가 '한국 코스피 시장'과 '우리의 대출 금리'에 미칠 실질적인 타격을 인과관계에 맞춰 분석합니다.
        3. **💌 모닝 레터 & 긴급 속보:** 바쁜 출근길에 가볍게 읽으실 수 있도록 매일 아침 7시 브리핑을 배달하며, 시장에 큰 충격이 발생했을 때는 즉시 긴급 속보를 발송하여 리스크 관리를 돕습니다.
        """)

# ==========================================
# 📜 이용약관 및 면책조항 페이지
# ==========================================
elif menu == "📜 이용약관 및 면책조항":
    st.title("📜 법적 면책조항 (Disclaimer)")
    st.write("EconBrief AI 서비스를 이용하시기 전에 반드시 아래 내용을 확인해 주시기 바랍니다.")
    with st.container(border=True):
        st.subheader("제1조 (정보의 목적 및 성격)")
        st.write("본 서비스(EconBrief AI) 및 AI 비서 '이브(Eve)'가 제공하는 모든 분석과 전망은 사용자에게 경제 흐름에 대한 전반적인 이해를 돕기 위한 **단순 정보 제공 및 참고용**입니다.")
        st.subheader("제2조 (투자 책임의 원칙)")
        st.write("본 서비스에서 제공되는 어떠한 정보도 특정 주식, 펀드, 파생상품 등 금융 자산에 대한 매수·매도 추천이나 직접적인 투자 권유를 의미하지 않습니다. **투자의 최종 결정과 그로 인해 발생하는 모든 수익 및 손실에 대한 책임은 전적으로 투자자 본인**에게 있습니다.")
        st.subheader("제3조 (법적 책임의 면제)")
        st.write("서비스 운영자는 본 서비스에서 제공하는 정보의 오류, 지연, 누락, 또는 이를 신뢰하여 내린 투자 결과에 대해 어떠한 직·간접적인 법적 책임도 지지 않습니다.")

# ==========================================
# 🛠️ 관리자 관제실 (Admin)
# ==========================================
elif menu == "🛠️ 관리자 관제실 (Admin)":
    st.title("🚨 긴급 속보 관제실 (Admin Only)")
    st.write("구독자 전체에게 이메일을 쏘고, 대표님의 텔레그램으로도 속보를 즉시 발송합니다.")
    
    admin_pw = st.text_input("🔑 관리자 비밀번호를 입력하세요", type="password")
    if admin_pw:
        if admin_pw == st.secrets["ADMIN_PASSWORD"]:
            st.success("✅ 최고 관리자 인증 완료.")
            with st.container(border=True):
                issue_text = st.text_input("현재 발생한 긴급 이슈", placeholder="예: 연준 긴급 금리 인하 발표")
                if st.button("🚨 전 구독자 이메일 & 텔레그램 속보 동시 발송!", type="primary", use_container_width=True):
                    if not issue_text:
                        st.warning("긴급 이슈를 입력해주세요!")
                    else:
                        with st.spinner("발송 준비 중... (이메일 및 텔레그램)"):
                            try:
                                MY_API_KEY = st.secrets["API_KEY"]
                                genai.configure(api_key=MY_API_KEY, transport="rest")
                                model = genai.GenerativeModel('gemini-2.5-flash')
                                
                                def get_data(ticker):
                                    hist = yf.Ticker(ticker).history(period="5d")
                                    curr = round(hist['Close'].iloc[-1], 2)
                                    prev = round(hist['Close'].iloc[-2], 2)
                                    return curr, round(curr - prev, 2), round(((curr - prev) / prev) * 100, 2)
                                ndx, tnx, vix, krw = get_data("^IXIC"), get_data("^TNX"), get_data("^VIX"), get_data("KRW=X")
                                
                                prompt = f"""
                                너는 경제 비서 '이브'야. [긴급 이슈]: {issue_text}
                                [현재 데이터] 나스닥:{ndx[0]}, 금리:{tnx[0]}%, VIX:{vix[0]}, 환율:{krw[0]}원
                                1. "🚨 [긴급 속보] 안녕하세요, 이브입니다." 로 시작해.
                                2. 이슈가 시장에 미칠 영향을 분석해.
                                3. 절대 마크다운(*, #) 쓰지 말고 HTML <b>, <br>만 사용해.
                                """
                                ai_text = model.generate_content(prompt).text
                                
                                # 📱 텔레그램 발송 함수 호출!
                                telegram_msg = f"🚨 [긴급 속보 발생]\n\n이슈: {issue_text}\n\n{ai_text}"
                                send_telegram_message(telegram_msg)
                                
                                # 📧 이메일 발송 처리
                                scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
                                creds_dict = json.loads(st.secrets["GCP_CREDENTIALS"], strict=False)
                                creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
                                client = gspread.authorize(creds)
                                sheet = client.open("EconBrief 구독자").sheet1
                                emails_data = sheet.col_values(1)
                                subscribers = list(set([e for e in emails_data[1:] if "@" in e]))
                                
                                sender_email = st.secrets["SENDER_EMAIL"]
                                app_password = st.secrets["APP_PASSWORD"]
                                
                                with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
                                    server.login(sender_email, app_password)
                                    success_cnt = 0
                                    for receiver in subscribers:
                                        msg = MIMEMultipart()
                                        msg['Subject'] = f'🚨 [긴급 속보] {issue_text} - 이브(Eve)'
                                        msg['From'] = sender_email
                                        msg['To'] = receiver
                                        html_content = f"<html><body>{ai_text}<hr><p style='color:gray; font-size:12px;'><i>[면책 조항] 본 긴급 속보는 투자 참고용이며 법적 증빙으로 사용될 수 없습니다.</i></p></body></html>"
                                        msg.attach(MIMEText(html_content, 'html'))
                                        try:
                                            server.send_message(msg)
                                            success_cnt += 1
                                        except: pass
                                st.success(f"🎉 총 {success_cnt}명 이메일 발송 완료 및 텔레그램 속보 전송 완료!")
                            except Exception as e:
                                st.error(f"오류: {e}")
        else:
            st.error("비밀번호가 일치하지 않습니다.")
