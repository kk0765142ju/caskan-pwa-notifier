import requests
from bs4 import BeautifulSoup
import re

def verify_filtering():
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    })
    
    session.get("https://my.caskan.jp/login")
    session.post("https://my.caskan.jp/login", data={"mode": "step1", "shop_code": "rilith", "code": "staff"})
    session.post("https://my.caskan.jp/login/password", data={"mode": "step2", "login_password": "arlt534"})
    
    # 日付範囲を今月初から月末まで広く指定して全予約取得
    url_all = "https://my.caskan.jp/reserve?date_from=2026-08-01&date_to=2026-08-31"
    r = session.get(url_all)
    soup = BeautifulSoup(r.text, "html.parser")
    
    rows = soup.select("table.tbl-reserve-list tr, table.table tr")
    print(f"=== 店全体予約テーブル 総行数: {len(rows)}行 ===")
    
    therapists = ["愛沢るな", "森永ここあ", "美波のん", "真白のん", "星乃せら", "あんな", "ほのか"]
    
    for tname in therapists:
        clean_tname = re.sub(r"[\s　]+", "", tname)
        matched_rows = []
        for row in rows:
            tds = row.select("td")
            if len(tds) >= 6:
                shimei_cell = tds[5].text.strip()
                if clean_tname in re.sub(r"[\s　]+", "", shimei_cell):
                    date_cell = tds[4].text.strip()
                    cust_name = tds[3].text.strip()
                    course_cell = tds[6].text.strip() if len(tds) > 6 else ""
                    matched_rows.append(f"日時:{date_cell} | 顧客:{cust_name} | コース:{course_cell} | セル:{shimei_cell}")
                    
        print(f"\n【{tname}】 マッチ件数: {len(matched_rows)}件")
        for m in matched_rows:
            print(f"  ・{m}")

if __name__ == "__main__":
    verify_filtering()
