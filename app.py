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

def send_telegram_message(text):
    try:
        token = st.secrets["TELEGRAM_BOT_TOKEN"]
        chat_id = st.secrets["TELEGRAM_CHAT_ID"]
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        clean_text = text.replace("<br>", "\n").replace("<b>", "🔥 ").replace("</b>", " 🔥")
        requests.post(url, data={"chat_id": chat_id, "text": clean_text, "parse_mode": "HTML"})
    except Exception as e:
        print(f"텔레그램 발송 실패: {e}")

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
            
        st.divider()
        st.write("💡 이브의 실시간 속보 채널")
        st.link_button("📲 공식 텔레그램 입장하기", "https://t.me/econbrief_official", type="primary", use_container_width=True)
    else:
        # 🌟 요청하신 "회원 가입 및 채널 입장"으로 텍스트 변경
        with st.expander("💌 회원 가입 및 채널 입장", expanded=True):
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
                            with st.spinner("명단 등록 중... 💌"):
                                try:
                                    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
                                    creds_dict = json.loads(st.secrets["GCP_CREDENTIALS"], strict=False)
                                    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
                                    client = gspread.authorize(creds)
                                    client.open("EconBrief 구독자").sheet1.append_row([login_email, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
                                    st.success("🎉 가입 완료!")
                                    st.balloons()
                                except Exception as e: 
                                    st.error(f"가입 실패: {e}")
                        else: st.success("🎉 로그인 성공!")
                    else: st.error("⚠️ 무단 가입 방지를 위해 주요 포털 이메일만 허용됩니다.")
                else: st.error("⚠️ 올바른 이메일 형식을 입력해주세요.")
            
            st.divider()
            st.markdown("**2️⃣ 실시간 텔레그램 속보방**")
            st.write("이메일보다 빠른 앱 전용 속보 채널!")
            # 👇 여기에 대표님의 텔레그램 채널 주소를 넣어주세요
            st.link_button("📲 공식 텔레그램 입장하기", "https://t.me/econbrief_official", type="primary", use_container_width=True)
            
            st.caption("⚠️ 이용 시 [면책조항]에 동의한 것으로 간주됩니다.")
                    
    st.divider()
    
    st.subheader("📋 메뉴")
    menu_options = ["🏠 글로벌 대시보드", "🇰🇷 K-Macro 딥다이브", "📖 이브(Eve)란?", "📜 이용약관 및 면책조항"]
    if is_admin_mode:
        menu_options.append("🛠️ 관리자 관제실 (Admin)")
        
    menu = st.radio("이동할 페이지를 선택하세요:", menu_options, label_visibility="collapsed")

MY_API_KEY = st.secrets["API_KEY"]
genai.configure(api_key=MY_API_KEY, transport="rest")
model = genai.GenerativeModel('gemini-2.5-flash')

def get_data_and_change(ticker):
    hist = yf.Ticker(ticker).history(period="5d")
    current, previous = round(hist['Close'].iloc[-1], 2), round(hist['Close'].iloc[-2], 2)
    return current, round(current - previous, 2), round(((current - previous) / previous) * 100, 2)

# ==========================================
# 🏠 1. 글로벌 대시보드 (홈 화면)
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

    # 🌟 TTS 복구 완료!
    if st.button("🔄 최신 글로벌 브리핑 생성", key="get_briefing_btn", type="primary"):
        with st.spinner('글로벌 시장 데이터를 스캔 중입니다...'):
            ndx, tnx, vix, krw, news_text, ai_text = get_morning_briefing()
            
            # 오디오 생성 로직 원상복구
            audio_text = re.sub(r'<[^>]+>', '', ai_text).replace("☀️", "").replace("☁️", "").replace("☔", "").replace("☕", "")
            with open("script.txt", "w", encoding="utf-8") as f: f.write(audio_text)
            os.system('edge-tts --file script.txt --voice ko-KR-SunHiNeural --rate=-10% --write-media briefing_audio.mp3')
            
            st.session_state.briefing_data = {"ndx": ndx, "tnx": tnx, "vix": vix, "krw": krw, "news_text": news_text, "ai_text": ai_text}

    if st.session_state.briefing_data:
        d = st.session_state.briefing_data
        
        # 📊 상단 지표 카드
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("🇺🇸 나스닥", f"{d['ndx'][0]:,} pt", f"{d['ndx'][1]} ({d['ndx'][2]}%)")
        c2.metric("💵 원/달러 환율", f"{d['krw'][0]:,} 원", f"{d['krw'][1]} ({d['krw'][2]}%)", delta_color="inverse")
        c3.metric("📈 미 10년물 금리", f"{d['tnx'][0]} %", f"{d['tnx'][1]} bp", delta_color="inverse")
        c4.metric("🚨 공포지수(VIX)", f"{d['vix'][0]}", f"{d['vix'][1]}", delta_color="inverse")
        st.divider()
        
        # 🖥️ 하단 레이아웃
        col_main, col_side = st.columns([7, 3])
        
        with col_main:
            col_t, col_a = st.columns([2, 1])
            with col_t: st.subheader("💡 이브(Eve)의 시황 브리핑")
            with col_a:
                if os.path.exists("briefing_audio.mp3"):
                    st.audio("briefing_audio.mp3", format='audio/mp3')
            
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
            st.subheader("📰 헤드라인")
            st.info(d['news_text'].replace("\n", "\n\n"))

# ==========================================
# 🇰🇷 2. K-Macro 딥다이브 
# ==========================================
elif menu == "🇰🇷 K-Macro 딥다이브":
    st.title("🇰🇷 K-Macro (국내 거시경제) 딥다이브")
    st.write("KOSPI 흐름과 원/달러 환율 등 대한민국 경제의 체력을 깊이 있게 분석합니다.")
    
    if st.button("📊 KOSPI 및 환율 심층 분석하기", type="primary"):
        with st.spinner('한국 증시와 환율 데이터를 수집 중입니다...'):
            ks11 = get_data_and_change("^KS11")
            kq11 = get_data_and_change("^KQ11")
            krw = get_data_and_change("KRW=X")
            kospi_hist = yf.Ticker("^KS11").history(period="1mo")
            
            prompt = f"""너는 거시경제 전문가 '이브'야. 
            [한국 데이터] KOSPI:{ks11[0]}({ks11[2]}%), KOSDAQ:{kq11[0]}({kq11[2]}%), 원/달러환율:{krw[0]}원
            1. 현재 환율이 수출입 기업과 KOSPI에 미치는 영향을 분석해.
            2. 한국은행(BOK)의 통화 정책 스탠스나 국내 물가(CPI) 우려에 대해 간략히 코멘트해.
            3. 마크다운 쓰지 말고 <b>와 <br>만 사용해."""
            st.session_state.kmacro_data = {"ks11": ks11, "kq11": kq11, "krw": krw, "chart": kospi_hist, "ai": model.generate_content(prompt).text}

    if st.session_state.kmacro_data:
        k = st.session_state.kmacro_data
        c1, c2, c3 = st.columns(3)
        c1.metric("KOSPI", f"{k['ks11'][0]:,} pt", f"{k['ks11'][1]} ({k['ks11'][2]}%)")
        c2.metric("KOSDAQ", f"{k['kq11'][0]:,} pt", f"{k['kq11'][1]} ({k['kq11'][2]}%)")
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
# 📖 3. 이브(Eve)란? (소개글 풀버전 복구)
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
        2. **🧠 AI 심층 분석:** 단순한 수치 나열을 넘어, 해당 지표의 변화가 '한국 증시'와 '대출 금리'에 미칠 실질적인 타격을 인과관계에 맞춰 분석합니다.
        3. **💌 모닝 레터 & 텔레그램 속보:** 바쁜 아침 가볍게 들으실 수 있는 음성(TTS) 브리핑은 물론, 시장에 큰 충격이 발생했을 때는 즉시 텔레그램으로 긴급 속보를 발송하여 리스크 관리를 돕습니다.
        """)

# ==========================================
# 📜 4. 면책조항 (풀버전 복구)
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
# 🛠️ 관리자 관제실 (Admin 풀버전)
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
                                
                                ndx, tnx, vix, krw = get_data_and_change("^IXIC"), get_data_and_change("^TNX"), get_data_and_change("^VIX"), get_data_and_change("KRW=X")
                                
                                prompt = f"""너는 경제 비서 '이브'야. [긴급 이슈]: {issue_text}
                                [현재 데이터] 나스닥:{ndx[0]}, 금리:{tnx[0]}%, VIX:{vix[0]}, 환율:{krw[0]}원
                                1. "🚨 [긴급 속보] 안녕하세요, 이브입니다." 로 시작해.
                                2. 이슈가 시장에 미칠 영향을 분석해.
                                3. 절대 마크다운(*, #) 쓰지 말고 HTML <b>, <br>만 사용해."""
                                ai_text = model.generate_content(prompt).text
                                
                                # 📱 텔레그램 발송
                                telegram_msg = f"🚨 [긴급 속보 발생]\n\n이슈: {issue_text}\n\n{ai_text}"
                                send_telegram_message(telegram_msg)
                                
                                # 📧 이메일 대량 발송
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




