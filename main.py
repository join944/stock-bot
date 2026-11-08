import os
from deep_translator import GoogleTranslator
import feedparser
import requests
import yfinance as yf

# 1. 환경변수에서 텔레그램 정보 불러오기
TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')


def get_stock_data():
  """보유 해외 ETF의 미국 기초 자산 지수, 환율 및 예상가 계산"""
  tickers = ['^NDX', 'CIBR', 'USDKRW=X']
  # 최근 5일 데이터를 받아와서 가장 최신 종가(마감가)와 전일 종가 확보
  df = yf.download(tickers, period='5d', progress=False)['Close']

  # 데이터프레임에서 값 추출
  ndx = df['^NDX'].dropna()
  cibr = df['CIBR'].dropna()
  krw = df['USDKRW=X'].dropna()

  # 나스닥 100
  ndx_prev = float(ndx.iloc[-2])
  ndx_curr = float(ndx.iloc[-1])
  ndx_pct = (ndx_curr - ndx_prev) / ndx_prev * 100

  # 글로벌 사이버보안 (CIBR)
  cibr_prev = float(cibr.iloc[-2])
  cibr_curr = float(cibr.iloc[-1])
  cibr_pct = (cibr_curr - cibr_prev) / cibr_prev * 100

  # 환율
  exchange_rate = float(krw.iloc[-1])

  # [참고] KODEX 미국나스닥100 및 TIGER 글로벌AI사이버보안의 대략적인 전일 기준 국내 종가 기준 예상가 산출
  # (실제 국내 ETF는 원달러 환율과 기초자산 등락률, 괴리율에 따라 움직입니다)
  # 임의의 기준 전일 국내가 대비 예상가 변동 반영 (기초지수 등락률 + 환율 변동 복합 반영)
  estimated_kodex_nasdaq = 10000 * (1 + (ndx_pct / 100))  # 이해를 돕기 위한 예상 추정치 베이스
  estimated_tiger_cyber = 10000 * (1 + (cibr_pct / 100))

  return {
      'ndx_pct': ndx_pct,
      'cibr_pct': cibr_pct,
      'exchange_rate': exchange_rate,
  }


def get_translated_news():
  """미국 야후 파이낸스 뉴스를 가져와서 한글로 번역"""
  news_list = []
  try:
    url = 'https://finance.yahoo.com/news/rssindex'
    feed = feedparser.parse(url)
    translator = GoogleTranslator(source='en', target='ko')

    # 상위 3개 뉴스 가져와서 한글 번역
    for entry in feed.entries[:3]:
      original_title = entry.title
      try:
        translated_title = translator.translate(original_title)
      except:
        translated_title = original_title  # 번역 실패시 원문 유지

      news_list.append(f'• {translated_title}')
  except Exception as e:
    news_list.append('• 최신 미국 증권 뉴스를 불러오는 중입니다.')

  return '\n'.join(news_list) if news_list else '• 등록된 뉴스가 없습니다.'


def main():
  stock_info = get_stock_data()
  news_summary = get_translated_news()

  # 텔레그램 메시지 구성
  message = f"""📊 [미장 마감 & 해외 ETF 예상 리포트]

💱 마감 환율: {stock_info['exchange_rate']:,.2f}원

📈 보유 ETF 연동지수 및 예상 동향:
🔹 KODEX 미국나스닥100
   - 지수 등락: {stock_info['ndx_pct']:+.2f}%

🔹 TIGER 글로벌AI사이버보안
   - 지수 등락: {stock_info['cibr_pct']:+.2f}%

📰 밤사이 미국 주요 증권 뉴스 (한글 번역):
{news_summary}
"""

  # 텔레그램 API 전송
  url = f'https://api.telegram.org/bot{TOKEN}/sendMessage'
  payload = {'chat_id': CHAT_ID, '
