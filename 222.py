import time
import re
import pandas as pd
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Selenium 설정
options = webdriver.ChromeOptions()
options.add_argument("--start-maximized")  # 창 최대화
driver = webdriver.Chrome(options=options)

# 종목 리스트
stocks = {
    "SK이노베이션": "096770",
    "POSCO플릭스": "005490",
    "현대건설": "000720",
    "현대차": "005380",
    "오리온": "271560",
    "삼성바이오로직스": "207940",
    "KB금융": "105560",
    "삼성전자": "005930",
    "네이버": "035420",
    "한국전력": "015760"
}

# 데이터를 저장할 리스트
data = []

def convert_naver_datetime(date_str):
    """
    네이버 뉴스 날짜 문자열을 UTC 형식 ('%Y-%m-%dT%H:%M:%S+09:00')으로 변환
    """
    match = re.search(r'(\d{4}\.\d{2}\.\d{2})\. (오전|오후) (\d{1,2}):(\d{2})', date_str)
    if not match:
        raise ValueError(f"날짜 형식이 예상과 다릅니다: {date_str}")

    date_part, am_pm, hour, minute = match.groups()

    hour = int(hour)
    if am_pm == "오후" and hour != 12:
        hour += 12
    elif am_pm == "오전" and hour == 12:
        hour = 0

    date_utc = datetime.strptime(f"{date_part} {hour}:{minute}", "%Y.%m.%d %H:%M").strftime("%Y-%m-%dT%H:%M:%S+09:00")
    return date_utc

for stock_name, stock_code in stocks.items():
    url = f"https://m.stock.naver.com/domestic/stock/{stock_code}/news"
    driver.get(url)
    time.sleep(3)  # 초기 로딩 대기

    # 🔹 더보기 버튼 클릭 반복 (최대 10회)
    for _ in range(10):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)

        try:
            more_button = driver.find_element(By.CLASS_NAME, "VMore_link__Tsoh9")
            more_button.click()
            time.sleep(2)
        except:
            break  # 더보기 버튼이 없으면 종료

    # 🔹 뉴스 목록 가져오기
    try:
        news_elements = driver.find_elements(By.CLASS_NAME, "NewsList_link__q7jtl")
        print(f"🔎 {stock_name} - 뉴스 {len(news_elements)}개 수집 시도")

        if not news_elements:
            continue  # 뉴스가 없으면 다음 종목으로 이동

        for i in range(len(news_elements)):
            try:
                # 뉴스 목록을 다시 가져오기 (동적 페이지 문제 해결)
                news_elements = driver.find_elements(By.CLASS_NAME, "NewsList_link__q7jtl")

                # 🔹 새 탭에서 열기
                driver.execute_script("arguments[0].click();", news_elements[i])
                time.sleep(3)

                # 🔹 새 창으로 전환
                driver.switch_to.window(driver.window_handles[-1])
                time.sleep(2)

                # 뉴스 제목
                title_element = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "media_end_head_headline"))
                )
                title = title_element.text.strip()

                # 뉴스 내용
                content_element = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "newsct_article"))
                )
                content = content_element.text.strip()

                # 날짜 정보
                date_element = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "media_end_head_info_datestamp_time"))
                )
                date = date_element.text.strip()
                date_utc = convert_naver_datetime(date)

                # 데이터 저장
                data.append({
                    "식별 ID": driver.current_url.split('/')[-1],
                    "수집한 플랫폼": "네이버",
                    "수집한 종목": stock_name,
                    "날짜": date_utc,
                    "뉴스 제목": title,
                    "뉴스 내용": content
                })

                print(f"✅ {stock_name} - {title}")

                # 🔹 현재 창 닫고 원래 창으로 복귀
                driver.close()
                driver.switch_to.window(driver.window_handles[0])
                time.sleep(2)

            except Exception as e:
                print(f"⚠️ {stock_name} 뉴스 수집 오류: {e}")
                driver.close()
                driver.switch_to.window(driver.window_handles[0])
                time.sleep(2)
                continue

    except Exception as e:
        print(f"⚠️ {stock_name} - 뉴스 목록을 가져오지 못함: {e}")
        continue  

# 데이터프레임 변환 및 저장
df = pd.DataFrame(data)

# 중복 제거
df.drop_duplicates(subset=["식별 ID", "수집한 종목"], inplace=True)

# 빠진 종목 확인
missing_stocks = set(stocks.keys()) - set(df["수집한 종목"].unique())
if missing_stocks:
    print(f"🚨 다음 종목에 대한 데이터가 누락되었습니다: {missing_stocks}")

# CSV 저장
df.to_csv("naver_stock_news.csv", index=False)

# 드라이버 종료
driver.quit()
