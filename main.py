import os
import requests
import yfinance as yf
from bs4 import BeautifulSoup

# 1. 환경변수에서 텔레그램 정보 불러오기
TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

def get_stock_data():
    """보유 해외 ETF의 미국 기초 자산 지수 및 환율 수집"""
    # ^NDX: 나스닥100 지수 (KODEX 미국나스닥100 기초자산)
    # BUGZ: First Trust Nasdaq Cybersecurity ETF (TIGER 글로벌AI사이버보안 주요 연동 ETF)
    # USDKRW=X: 원/달러 환율
    tickers = ['^NDX', 'BUGZ', 'USDKRW=X']
    data = yf.download(tickers, period='2d', progress=False)['Close']
    
    # 나스닥 100 등락률
    ndx_prev = data['^NDX'].iloc[-2]
    ndx_curr = data['^NDX'].iloc[-1]
    ndx_pct = (ndx_curr - ndx_prev) / ndx_prev * 100
    
    # 글로벌 사이버보안 ETF(BUGZ) 등락률
    bugz_prev = data['BUGZ'].iloc[-2]
    bugz_curr = data['BUGZ'].iloc[-1]
    bugz_pct = (bugz_curr - bugz_prev) / bugz_prev * 100
    
    # 환율
    exchange_rate = data['USDKRW=X'].iloc[-1]
    
    return {
        'ndx_pct': ndx_pct,
        'bugz_pct': bugz_pct,
        'exchange_rate': exchange_rate
    }

def get_market_news():
    """네이버 금융 해외증시 주요 뉴스 헤드라인 크롤링"""
    url = "https://finance.naver.com/news/mainnews.naver"
    headers = {
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15'
    }
    
    news_list = []
    try:
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 주요 뉴스 헤드라인 추출 (상위 3개)
        articles = soup.select('.newsList .articleSubject a')
        for article in articles[:3]:
            title = article.get_text(strip=True)
            news_list.append(f"• {title}")
    except Exception as e:
        news_list.append("• 뉴스 정보를 가져오는 중 오류가 발생했습니다.")
        
    return "\n".join(news_list)

def main():
    stock_info = get_stock_data()
    news_summary = get_market_news()
    
    # 텔레그램 메시지 구성
    message = f"""📊 [미장 마감 & 해외 ETF 리포트]

💱 마감 환율: {stock_info['exchange_rate']:.2f}원

📈 보유 ETF 연동지수 예상 동향:
🔹 KODEX 미국나스닥100: {stock_info['ndx_pct']:+.2f}%
🔹 TIGER 글로벌AI사이버보안: {stock_info['bugz_pct']:+.2f}%

📰 밤사이 주요 증권 뉴스:
{news_summary}
"""

    # 텔레그램 API 전송
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message
    }
    requests.post(url, json=payload)

if __name__ == "__main__":
    main()
