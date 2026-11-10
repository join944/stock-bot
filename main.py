
import os
import re
import html
import requests
import feedparser
import time
import yfinance as yf
import pandas_market_calendars as mcal

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from deep_translator import GoogleTranslator


# =====================================
# 1. 기본 설정
# =====================================

TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

HOLDINGS = {
    "KODEX 미국나스닥100": {
        "ticker": "379810.KS",
        "shares": 40,
        "index": "^NDX"
    },
    "TIGER 글로벌AI사이버보안": {
        "ticker": "418670.KS",
        "shares": 7,
        "index": "CIBR"
    }
}

FX_TICKER = "USDKRW=X"


# =====================================
# 2. 미국 증시 마감 시간 확인
# =====================================

def is_report_time():

    ny_time = datetime.now(
        ZoneInfo("America/New_York")
    )

    calendar = mcal.get_calendar("NYSE")

    schedule = calendar.schedule(
        start_date=ny_time.date(),
        end_date=ny_time.date()
    )

    if schedule.empty:
        print("미국 증시 휴장일입니다.")
        return False

    print("미국 증시 거래일 확인 완료")
    return True

# =====================================
# 3. 주가 데이터 수집
# =====================================

def get_history(ticker):

    data = yf.Ticker(ticker).history(
        period="10d",
        interval="1d",
        auto_adjust=False
    )

    if data.empty:
        raise ValueError(f"{ticker} 데이터 수집 실패")

    close = data["Close"].dropna()

    if len(close) < 2:
        raise ValueError(f"{ticker} 데이터 부족")

    return close


def get_change(ticker):

    close = get_history(ticker)

    previous = float(close.iloc[-2])
    current = float(close.iloc[-1])

    change = (current / previous - 1) * 100

    return change


# =====================================
# 4. ETF 예상 가격 계산
# =====================================

def get_stock_data():

    fx_change = get_change(FX_TICKER)

    fx_history = get_history(FX_TICKER)
    exchange_rate = float(fx_history.iloc[-1])

    results = []

    for name, info in HOLDINGS.items():

        domestic_close = get_history(
            info["ticker"]
        )

        base_price = float(domestic_close.iloc[-1])

        index_change = get_change(
            info["index"]
        )

        # 달러 기준 기초자산 변동률과
        # 원달러 환율 변동률을 복합 반영

        estimated_change = (
            (1 + index_change / 100)
            * (1 + fx_change / 100)
            - 1
        ) * 100

        estimated_price = (
            base_price *
            (1 + estimated_change / 100)
        )

        # 국내 ETF 호가 단위에 맞춰 5원 단위 반올림
        estimated_price = round(
            estimated_price / 5
        ) * 5

        shares = info["shares"]

        estimated_value = estimated_price * shares

        results.append({
            "name": name,
            "shares": shares,
            "base_price": base_price,
            "index_change": index_change,
            "estimated_change": estimated_change,
            "estimated_price": estimated_price,
            "estimated_value": estimated_value
        })

    return {
        "exchange_rate": exchange_rate,
        "fx_change": fx_change,
        "results": results
    }


# =====================================
# 5. 미국 증권 뉴스 수집 및 번역
# =====================================


def get_translated_news():

    url = "https://news.google.com/rss/search"

    params = {
        "q": "US stock market OR Nasdaq OR S&P 500 when:1d",
        "hl": "en-US",
        "gl": "US",
        "ceid": "US:en"
    }

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    try:
        response = requests.get(
            url,
            params=params,
            headers=headers,
            timeout=15
        )

        response.raise_for_status()

        feed = feedparser.parse(response.content)

        print("뉴스 수집 개수:", len(feed.entries))

        if not feed.entries:
            print("뉴스 RSS에 기사가 없습니다.")
            return "• 최신 뉴스를 가져오지 못했습니다."

    except Exception as e:
        print("뉴스 수집 오류:", e)
        return "• 뉴스 서버 연결에 실패했습니다."

    translator = GoogleTranslator(
        source="en",
        target="ko"
    )

    news_list = []


    import time

    for entry in feed.entries[:5]:

        title = entry.get("title", "제목 없음")

        description = entry.get("summary", "")

        description = re.sub(
            r"<[^>]+>",
            " ",
            description
        )

        description = html.unescape(
            description
        ).strip()

        try:
            translated_title = translator.translate(
                title[:450]
            )

            time.sleep(1)

            if description:
                translated_description = translator.translate(
                    description[:450]
                )
            else:
                translated_description = ""

            time.sleep(1)

        except Exception as e:
            print("번역 오류:", e)

            translated_title = title
            translated_description = description

        news_list.append(
            f"• {translated_title}\n"
            f"  {translated_description[:250]}"
        )



# =====================================
# 6. 텔레그램 메시지 구성
# =====================================

def create_message(stock_info, news):

    message = (
        "📊 미국 증시 마감 리포트\n"
        "━━━━━━━━━━━━━━\n\n"
        "💱 환율 정보\n"
        f"원달러 환율: "
        f"{stock_info['exchange_rate']:,.2f}원\n"
        f"환율 변동: "
        f"{stock_info['fx_change']:+.2f}%\n\n"
        "📈 보유 ETF 예상 가격\n"
        "━━━━━━━━━━━━━━\n"
    )

    for item in stock_info["results"]:

        message += (
            f"\n🔹 {item['name']}\n"
            f"보유 수량: {item['shares']}주\n"
            f"직전 국내 종가: "
            f"{item['base_price']:,.0f}원\n"
            f"기초지수 등락: "
            f"{item['index_change']:+.2f}%\n"
            f"예상 등락률: "
            f"{item['estimated_change']:+.2f}%\n"
            f"예상 가격: "
            f"{item['estimated_price']:,.0f}원\n"
            f"예상 평가금액: "
            f"{item['estimated_value']:,.0f}원\n"
        )

    message += (
        "\n━━━━━━━━━━━━━━\n"
        "📰 밤사이 미국 증권 뉴스\n"
        "━━━━━━━━━━━━━━\n\n"
        f"{news}\n\n"
        "━━━━━━━━━━━━━━\n"
        "※ 예상 가격은 참고용 추정치입니다.\n"
        "※ 실제 국내 ETF 가격과 차이가 발생할 수 있습니다."
    )

    return message


# =====================================
# 7. 텔레그램 전송
# =====================================

def send_telegram(message):

    if not TOKEN or not CHAT_ID:
        raise ValueError(
            "텔레그램 환경변수가 설정되지 않았습니다."
        )

    url = (
        f"https://api.telegram.org/"
        f"bot{TOKEN}/sendMessage"
    )

    # 텔레그램 메시지 길이 제한 대응
    chunks = [
        message[i:i + 3900]
        for i in range(0, len(message), 3900)
    ]

    for chunk in chunks:

        response = requests.post(
            url,
            json={
                "chat_id": CHAT_ID,
                "text": chunk
            },
            timeout=30
        )

        response.raise_for_status()

        result = response.json()

        if not result.get("ok"):
            raise RuntimeError(
                f"텔레그램 전송 실패: {result}"
            )

    print("텔레그램 전송 성공!")


# =====================================
# 8. 메인 실행
# =====================================

def main():

    if not is_report_time():
        return

    try:

        print("ETF 데이터 수집 시작")

        stock_info = get_stock_data()

        print("뉴스 수집 시작")

        news = get_translated_news()

        message = create_message(
            stock_info,
            news
        )

        send_telegram(message)

    except Exception as e:

        print("실행 오류:", e)

        send_telegram(
            "⚠️ ETF 아침 리포트 오류\n\n"
            f"오류 내용: {str(e)[:1000]}"
        )


if __name__ == "__main__":
    main()
