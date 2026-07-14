import os
import sys
from datetime import datetime, timezone, timedelta

import requests
from bs4 import BeautifulSoup

DIET_URL = "https://www.uc.ac.kr/www/CMS/DietMenuMgr/listByWeek.do"
CAMPUS_PARAMS = {"mCode": "MN207", "searchDietCategory": "4"}  # 동부식당
KST = timezone(timedelta(hours=9))


def fetch_today_menu():
    today = datetime.now(KST).date()
    resp = requests.get(DIET_URL, params=CAMPUS_PARAMS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    table = soup.select_one("#cafeteria-menu table.tbl-type01")
    if table is None:
        raise RuntimeError("식단표 테이블을 찾을 수 없습니다 (사이트 구조가 변경되었을 수 있습니다)")

    header_cells = table.select("thead th")[1:]  # skip "구분" column
    dates = [th.select_one(".date").get_text(strip=True) for th in header_cells]

    if str(today) not in dates:
        return None, today  # weekend or out of range

    col_index = dates.index(str(today))

    lunch_row = None
    for row in table.select("tbody tr"):
        header = row.select_one("th")
        if header and header.get_text(strip=True) == "점심":
            lunch_row = row
            break
    if lunch_row is None:
        raise RuntimeError("점심 메뉴 행을 찾을 수 없습니다")

    cells = lunch_row.select("td")
    cell = cells[col_index]
    for br in cell.find_all("br"):
        br.replace_with("\n")
    menu_text = cell.get_text().replace("\r", "").strip()
    return menu_text, today


def build_slack_message(menu_text, today):
    day_kr = ["월", "화", "수", "목", "금", "토", "일"][today.weekday()]
    date_str = f"{today.strftime('%Y-%m-%d')} ({day_kr})"

    if menu_text is None:
        text = f"*{date_str} 오늘의 식단*\n오늘은 식단표 운영일이 아닙니다."
    elif "공휴일" in menu_text or not menu_text:
        text = f"*{date_str} 오늘의 식단*\n오늘은 공휴일/휴무일로 식단이 없습니다."
    else:
        items = "\n".join(f"- {line}" for line in menu_text.split("\n") if line.strip())
        text = f"*{date_str} 오늘의 식단 (동부식당 점심)*\n{items}"

    return text


def send_to_slack(text, webhook_url):
    resp = requests.post(webhook_url, json={"text": text}, timeout=15)
    resp.raise_for_status()


def main():
    webhook_url = os.environ.get("SLACK_WEBHOOK_URL")
    if not webhook_url:
        print("SLACK_WEBHOOK_URL 환경변수가 설정되어 있지 않습니다.", file=sys.stderr)
        sys.exit(1)

    menu_text, today = fetch_today_menu()
    message = build_slack_message(menu_text, today)
    print(message)
    send_to_slack(message, webhook_url)


if __name__ == "__main__":
    main()
