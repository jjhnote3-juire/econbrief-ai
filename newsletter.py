import yfinance as yf
import google.generativeai as genai
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import datetime
import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json

def job_send_newsletter():
    print(f"[{datetime.datetime.now()}] 🚀 이브(Eve)가 무인 서버에서 모닝 브리핑 발송을 시작합니다...")
    
    # 🔒 깃허브 비밀 금고(환경 변수)에서 정보 꺼내기
    MY_API_KEY = os.environ.get("API_KEY")
    sender_email = os.environ.get("SENDER_EMAIL")
    app_password = os.environ.get("APP_PASSWORD")

    genai.configure(api_key=MY_API_KEY, transport="rest")
    model = genai.GenerativeModel('gemini-2.5-flash')

    # 1. 데이터 수집
    def get_data(ticker):
        hist = yf.Ticker(ticker).history(period="5d")
        current = round(hist['Close'].iloc[-1], 2)
        previous = round(hist['Close'].iloc[-2], 2)
        return current, round(current - previous, 2), round(((current - previous) / previous) * 100, 2)

    ndx = get_data("^IXIC")
    tnx = get_data("^TNX")
    vix = get_data("^VIX")
    krw = get_data("KRW=X")

    # 2. 뉴스 수집
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
        news_text = "오늘 장에 큰 영향을 미칠만한 특별한 거시경제 뉴스가 없습니다."

    # 💡 [마크다운 방지 프롬프트 추가!]
    prompt = f"""
    너는 사용자의 스마트한 경제 비서이자 전속 아나운서인 '이브(Eve)'야.
    [데이터] 나스닥:{ndx[0]}({ndx[2]}%), 금리:{tnx[0]}%, VIX:{vix[0]}, 환율:{krw[0]}원
    [뉴스] {news_text}
    
    1. 반드시 "안녕하세요! 여러분의 경제 비서 이브입니다." 라고 다정하게 시작해.
    2. 시장 날씨, KOSPI 예상, 대출 금리 영향을 분석해줘.
    
    🚨 [매우 중요 규칙]
    절대로 마크다운 기호(*, #, -, ` 등)를 사용하지 마! 
    글자를 강조하고 싶을 때는 반드시 HTML <b>태그를 쓰고, 줄바꿈은 <br> 태그만 사용해서 아주 깔끔하게 작성해.
    """
    response = model.generate_content(prompt)
    ai_text = response.text

    # 3. 구글 시트에서 구독자 명단 읽어오기
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        # 🔒 깃허브 금고에서 JSON 출입증 꺼내기
        creds_dict = json.loads(os.environ.get("GCP_CREDENTIALS"))
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        
        sheet = client.open("EconBrief 구독자").sheet1
        emails_data = sheet.col_values(1) 
        
        subscribers = []
        for email in emails_data[1:]:
            if "@" in email and email not in subscribers: 
                subscribers.append(email)
                
    except Exception as e:
        print(f"❌ 구글 시트 연결 실패: {e}")
        return

    if not subscribers:
        print("📭 시트에 구독자가 0명입니다.")
        return

    # 4. 1:N 이메일 발송
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(sender_email, app_password)
        
        success_count = 0
        for receiver in subscribers:
            msg = MIMEMultipart()
            msg['Subject'] = f'🌤️ 이브(Eve)의 모닝 브리핑 ({datetime.date.today()} 기준)'
            msg['From'] = sender_email
            msg['To'] = receiver
            
            html_content = f"""
            <html>
              <body style="font-family: Arial, sans-serif; line-height:1.6;">
                <h2 style="color: #2e6c80;">📈 오늘의 거시경제 시황</h2>
                <p>{ai_text}</p>
                <hr>
                <p style="color:gray; font-size:12px;"><i>이브(Eve) 무인 서버가 아침 7시에 자동으로 발송한 메일입니다.</i></p>
              </body>
            </html>
            """
            msg.attach(MIMEText(html_content, 'html'))
            
            try:
                server.send_message(msg)
                print(f"✅ {receiver} 발송 성공!")
                success_count += 1
            except Exception as e:
                print(f"❌ {receiver} 발송 실패: {e}")

# 스케줄러 없이 파일이 실행되면 즉시 딱 1번만 일하고 종료!
if __name__ == "__main__":
    job_send_newsletter()