import os
import time
import re
import pandas as pd
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# 폴더 생성
output_folder = "naver_news_data"
os.makedirs(output_folder, exist_ok=True)

# Selenium 설정
options = webdriver.ChromeOptions()
options.add_argument("--start-maximized")  # 창 최대화
driver = webdriver.Chrome(options=options)

# 종목 리스트 (삼성전자만 실행, 다른 종목은 유지)
stocks = {
    "SK이노베이션": "096770",
    # "POSCO플릭스": "005490",
    # "현대건설": "000720",
    # "현대차": "005380",
    # "오리온": "271560",
    # "삼성바이오로직스": "207940",
    # "KB금융": "105560",
    "삼성전자": "005930",  # 🔹 삼성전자만 실행
    # "네이버": "035420",
    # "한국전력": "015760"
}

def convert_naver_datetime(date_str):
    """ 네이버 뉴스 날짜를 UTC 형식 변환 """
    match = re.search(r'(\d{4}\.\d{2}\.\d{2})\. (오전|오후) (\d{1,2}):(\d{2})', date_str)
    if not match:
        raise ValueError(f"날짜 형식이 예상과 다릅니다: {date_str}")

    date_part, am_pm, hour, minute = match.groups()

    hour = int(hour)
    if am_pm == "오후" and hour != 12:
        hour += 12
    elif am_pm == "오전" and hour == 12:
        hour = 0

    return datetime.strptime(f"{date_part} {hour}:{minute}", "%Y.%m.%d %H:%M").strftime("%Y-%m-%dT%H:%M:%S+09:00")

for stock_name, stock_code in stocks.items():
    url = f"https://m.stock.naver.com/domestic/stock/{stock_code}/news"
    driver.get(url)
    time.sleep(3)
    print(f"\n🔍 {stock_name} 뉴스 페이지 접속 완료: {url}")

    # 🔹 스크롤 및 '더보기' 버튼 로직 개선
    max_scrolls = 5  # 최대 스크롤 횟수
    scroll_count = 0
    more_button_clicked = 0  # '더보기' 버튼 클릭 횟수

    while scroll_count < max_scrolls:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        print(f"🔻 스크롤 {scroll_count + 1}/{max_scrolls} 실행")
        time.sleep(2)
        
        try:
            more_button = WebDriverWait(driver, 2).until(
                EC.element_to_be_clickable((By.CLASS_NAME, "VMore_link__Tsoh9"))
            )
            more_button.click()
            time.sleep(2)
            more_button_clicked += 1
            print(f"✅ '더보기' 버튼 클릭 ({more_button_clicked}회)")
        except:
            print("⚠️ '더보기' 버튼 없음 (스크롤 계속 진행)")

        scroll_count += 1

    print(f"🎯 최종 스크롤 횟수: {scroll_count}, '더보기' 버튼 클릭 횟수: {more_button_clicked}")

    # 🔹 뉴스 목록 가져오기
    try:
        news_elements = driver.find_elements(By.CLASS_NAME, "NewsList_link__q7jtl")
        print(f"📰 {stock_name} - 뉴스 {len(news_elements)}개 수집 시도")

        if not news_elements:
            print(f"⚠️ {stock_name} 뉴스 없음, 종료")
            continue

        stock_data = []  # 종목별 데이터 저장 리스트

        for i in range(len(news_elements)):
            try:
                print(f"📌 {stock_name} - {i+1}/{len(news_elements)}번째 뉴스 클릭 시도")
                news_elements = driver.find_elements(By.CLASS_NAME, "NewsList_link__q7jtl")
                driver.execute_script("arguments[0].click();", news_elements[i])
                time.sleep(3)

                driver.switch_to.window(driver.window_handles[-1])
                time.sleep(2)

                title = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "media_end_head_headline"))
                ).text.strip()

                content = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "newsct_article"))
                ).text.strip()

                date = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "media_end_head_info_datestamp_time"))
                ).text.strip()

                date_utc = convert_naver_datetime(date)

                stock_data.append({
                    "식별 ID": driver.current_url.split('/')[-1],
                    "수집한 플랫폼": "네이버",
                    "수집한 종목": stock_name,
                    "날짜": date_utc,
                    "뉴스 제목": title,
                    "뉴스 내용": content
                })

                print(f"✅ {stock_name} - 뉴스 수집 완료: {title[:30]}...")

                driver.close()
                driver.switch_to.window(driver.window_handles[0])
                time.sleep(2)

            except Exception as e:
                print(f"⚠️ {stock_name} 뉴스 수집 오류: {e}")
                driver.close()
                driver.switch_to.window(driver.window_handles[0])
                time.sleep(2)
                continue

        # 🔹 데이터 저장 (종목별 개별 파일)
        if stock_data:
            df = pd.DataFrame(stock_data)
            df.drop_duplicates(subset=["식별 ID", "수집한 종목"], inplace=True)

            # 파일명: 종목명을 영문자로 변환 후 저장 (파일명 안전하게)
            safe_stock_name = stock_name.replace(" ", "_").replace("/", "_")
            filename = os.path.join(output_folder, f"{safe_stock_name}.csv")
            df.to_csv(filename, index=False)
            print(f"💾 {stock_name} 데이터 저장 완료: {filename}")

    except Exception as e:
        print(f"⚠️ {stock_name} - 뉴스 목록을 가져오지 못함: {e}")
        continue  

# 드라이버 종료
driver.quit()
print("🚪 크롤링 완료, 드라이버 종료")
