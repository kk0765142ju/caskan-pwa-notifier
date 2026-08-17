import requests
from bs4 import BeautifulSoup

def print_exact_cast_ids():
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    })
    
    session.get("https://my.caskan.jp/login")
    session.post("https://my.caskan.jp/login", data={"mode": "step1", "shop_code": "rilith", "code": "staff"})
    session.post("https://my.caskan.jp/login/password", data={"mode": "step2", "login_password": "arlt534"})
    
    r = session.get("https://my.caskan.jp/reserve")
    soup = BeautifulSoup(r.text, "html.parser")
    
    cast_select = soup.select_one("select[name='cast_id']")
    print("=== 全キャストの正確な ID マップ ===")
    out_map = {}
    if cast_select:
        for opt in cast_select.select("option"):
            name = opt.text.strip()
            val = opt.get("value", "")
            if name and val:
                out_map[name] = val
                print(f'"{name}": "{val}",')
                
if __name__ == "__main__":
    print_exact_cast_ids()
