import requests
from bs4 import BeautifulSoup

def dump_reserve_page():
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    })
    
    session.get("https://my.caskan.jp/login")
    session.post("https://my.caskan.jp/login", data={"mode": "step1", "shop_code": "rilith", "code": "staff"})
    r_login = session.post("https://my.caskan.jp/login/password", data={"mode": "step2", "login_password": "arlt534"})
    
    r_mypage = session.get("https://my.caskan.jp/mypage")
    soup_my = BeautifulSoup(r_mypage.text, "html.parser")
    print("=== MYPAGE LINKS ===")
    for a in soup_my.select("a"):
        href = a.get("href", "")
        if "reserve" in href or "schedule" in href or "cast" in href:
            print(f"  Link: {a.text.strip()} => {href}")
            
    r_res = session.get("https://my.caskan.jp/reserve")
    soup_res = BeautifulSoup(r_res.text, "html.parser")
    print("\n=== RESERVE PAGE TABLES ===")
    tables = soup_res.select("table")
    print(f"テーブル数: {len(tables)}")
    for t_idx, t in enumerate(tables):
        print(f"  Table[{t_idx+1}] class={t.get('class')}")
        tr_list = t.select("tr")
        print(f"    tr行数: {len(tr_list)}")
        if len(tr_list) > 0:
            print(f"    最初の1行: {tr_list[0].text.strip()[:100]}")

if __name__ == "__main__":
    dump_reserve_page()
