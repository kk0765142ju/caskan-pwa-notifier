import logging
import asyncio
import datetime
import json
import os
import re
import requests
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# ★ Vercel環境で100%確実に動作するインライン キャストIDマップ ★
CAST_ID_MAP = {
    "あんな": "75389",
    "ほのか": "75388",
    "愛沢るな": "71588",
    "真白のん": "71589",
    "星乃せら": "71590",
    "美波のん": "71591",
    "森永ここあ": "71587"
}

class CaskanScraper:
    def __init__(self, login_url: str = "https://my.caskan.jp/login", username: str = "staff", password: str = "arlt534", shop_id: str = "rilith"):
        self.login_url = login_url
        self.username = username
        self.password = password
        self.shop_id = shop_id
        self.cast_map = CAST_ID_MAP
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "ja,en-US;q=0.9,en;q=0.8"
        }

    def _parse_time_minutes(self, time_str: str) -> int:
        match = re.search(r"(\d{1,2}):(\d{2})", time_str)
        if match:
            h = int(match.group(1))
            m = int(match.group(2))
            return h * 60 + m
        return 99999

    def _get_session(self) -> Optional[requests.Session]:
        session = requests.Session()
        session.headers.update(self.headers)
        try:
            r1 = session.get(self.login_url, timeout=10)
            soup1 = BeautifulSoup(r1.text, "html.parser")
            
            token_el = soup1.select_one("input[name='_token']")
            token = token_el["value"] if token_el else ""

            login_data = {
                "_token": token,
                "shop_code": self.shop_id,
                "code": self.username,
                "login_password": self.password
            }

            r2 = session.post(self.login_url, data=login_data, timeout=10)
            if "login" in r2.url and "password" in r2.text.lower():
                r2 = session.post(self.login_url, data=login_data, timeout=10)

            return session
        except Exception as e:
            logger.error(f"caskan セッション確立例外: {e}")
            return None

    async def fetch_today_data(self) -> Dict[str, Any]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._sync_fetch_today_data)

    def _sync_fetch_today_data(self) -> Dict[str, Any]:
        session = self._get_session()
        if not session:
            return {"date": datetime.date.today().strftime("%Y-%m-%d"), "shifts": [], "reservations": []}

        try:
            r = session.get("https://my.caskan.jp/mypage", timeout=10)
            soup = BeautifulSoup(r.text, "html.parser")
            shifts = []
            textarea = soup.select_one("textarea.textarea-auto")
            if textarea:
                for line in textarea.text.split("\n"):
                    line = line.strip()
                    if "💖" in line:
                        match = re.search(r"💖\s*([^\s　]+)[\s　]+(\d{1,2}:\d{2})[〜~](\d{1,2}:\d{2})?", line)
                        if match:
                            tname = match.group(1).strip()
                            stime = match.group(2).strip()
                            etime = match.group(3).strip() if match.group(3) else "退勤未定"
                            shifts.append({
                                "therapist_name": tname,
                                "start_time": stime,
                                "end_time": etime
                            })
            return {
                "date": datetime.date.today().strftime("%Y-%m-%d"),
                "shifts": shifts,
                "reservations": []
            }
        except Exception as e:
            logger.error(f"_sync_fetch_today_data Exception: {e}")
            return {"date": datetime.date.today().strftime("%Y-%m-%d"), "shifts": [], "reservations": []}

    async def fetch_therapist_full_data(self, therapist_name: str) -> Dict[str, Any]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._sync_fetch_therapist_full_data, therapist_name)

    def _sync_fetch_therapist_full_data(self, therapist_name: str) -> Dict[str, Any]:
        today_date = datetime.date.today()
        yesterday_date = today_date - datetime.timedelta(days=1)
        
        today_str = today_date.strftime("%Y-%m-%d")
        yesterday_str = yesterday_date.strftime("%Y-%m-%d")
        month_start_str = today_date.replace(day=1).strftime("%Y-%m-%d")
        
        today_md = f"{today_date.month}/{today_date.day}"
        yesterday_md = f"{yesterday_date.month}/{yesterday_date.day}"
        
        clean_name = re.sub(r"[\s　]+", "", therapist_name)
        cast_id = self.cast_map.get(clean_name, "")
        
        session = self._get_session()
        if not session:
            return self._generate_mock_data(therapist_name)

        try:
            if cast_id:
                target_url = f"https://my.caskan.jp/reserve?mode=&sort=&date_from={month_start_str}&date_to=2026-08-31&cast_id={cast_id}"
            else:
                target_url = f"https://my.caskan.jp/reserve?date_from={month_start_str}&date_to={today_str}"

            r_res = session.get(target_url, timeout=10)
            soup_res = BeautifulSoup(r_res.text, "html.parser")

            raw_reservations = []
            today_room = "未割当"

            rows = soup_res.select("table.tbl-reserve-list tbody tr, table.table tbody tr")
            for row in rows:
                try:
                    tds = row.select("td")
                    if len(tds) < 8:
                        continue

                    cust_el = row.select_one("a[href*='/customer/view']")
                    cust_name = cust_el.text.strip() if cust_el else "フリーお客様"

                    date_cell = tds[4].text.strip()
                    course_cell = tds[6].text.strip() if len(tds) > 6 else "90分"
                    room_cell = tds[7].text.strip() if len(tds) > 7 else "部屋未定"
                    price_cell = tds[8].text.strip() if len(tds) > 8 else "0"

                    shimei_el = row.select_one("span.text-xs, span.mg-left-sm")
                    raw_shimei = shimei_el.text.strip() if shimei_el else "指名なし"

                    if "本指名" in raw_shimei:
                        shimei_type = "本指名"
                    elif "写真指名" in raw_shimei:
                        shimei_type = "写真指名"
                    elif "リピーター" in raw_shimei:
                        shimei_type = "リピーター"
                    elif "指名なし" in raw_shimei:
                        shimei_type = "指名なし"
                    else:
                        shimei_type = raw_shimei or "指名なし"

                    time_match = re.search(r"(\d{1,2}:\d{2})", date_cell)
                    start_time = time_match.group(1) if time_match else "00:00"

                    link_status = row.select_one("a.link-status")
                    res_id = link_status.get("data-reserve-id") if link_status else None
                    if not res_id:
                        edit_link = row.select_one("a[href*='/reserve/edit?id=']")
                        if edit_link:
                            m_id = re.search(r"id=(\d+)", edit_link.get("href", ""))
                            res_id = m_id.group(1) if m_id else None

                    is_luxury = "luxury" in course_cell.lower() or "ラグジュアリー" in course_cell
                    price_val = int(re.sub(r"[^\d]", "", price_cell) or 0)

                    raw_reservations.append({
                        "id": res_id,
                        "therapist_name": therapist_name,
                        "customer_name": cust_name,
                        "date_text": date_cell,
                        "start_time": start_time,
                        "end_time": "終了未定",
                        "course_name": course_cell,
                        "room_name": room_cell,
                        "is_luxury": is_luxury,
                        "shimei_type": shimei_type,
                        "price": price_val
                    })
                except Exception as ex_row:
                    continue

            today_reservations = []
            yesterday_reservations = []
            monthly_reservations = []

            for r in raw_reservations:
                res_id = r.get("id")
                nominate_charge = 0
                cast_margin_nominate = 0
                cast_margin_system = 0
                cast_margin_option = 0
                discount_amount = 0
                cast_margin_discount = 0
                margin_rate = 50
                cast_total_pay = 0

                if res_id:
                    try:
                        edit_url = f"https://my.caskan.jp/reserve/edit?id={res_id}"
                        r_edit = session.get(edit_url, timeout=5)
                        soup_edit = BeautifulSoup(r_edit.text, "html.parser")

                        nom_el = soup_edit.select_one("input[name='nominate_charge']")
                        nom_back_el = soup_edit.select_one("input[name='cast_margin_nominate']")
                        sys_back_el = soup_edit.select_one("input[name='cast_margin_system']")
                        opt_back_el = soup_edit.select_one("input[name='cast_margin_option']")
                        disc_el = soup_edit.select_one("input[name='discount2']")
                        disc_back_el = soup_edit.select_one("input[name='cast_margin_discount']")
                        mrate_el = soup_edit.select_one("input[name='margin_rate']")

                        nominate_charge = int(re.sub(r"[^\d]", "", nom_el.get("value", "0") if nom_el else "0"))
                        cast_margin_nominate = int(re.sub(r"[^\d]", "", nom_back_el.get("value", "0") if nom_back_el else "0"))
                        cast_margin_system = int(re.sub(r"[^\d]", "", sys_back_el.get("value", "0") if sys_back_el else "0"))
                        cast_margin_option = int(re.sub(r"[^\d]", "", opt_back_el.get("value", "0") if opt_back_el else "0"))
                        discount_amount = int(re.sub(r"[^\d]", "", disc_el.get("value", "0") if disc_el else "0"))
                        cast_margin_discount = int(re.sub(r"[^\d]", "", disc_back_el.get("value", "0") if disc_back_el else "0"))
                        margin_rate = int(re.sub(r"[^\d]", "", mrate_el.get("value", "50") if mrate_el else "50"))

                        cast_total_pay = (cast_margin_system + cast_margin_nominate + cast_margin_option) - cast_margin_discount
                    except Exception as ex_edit:
                        pass

                real_price = r["price"]
                if real_price == 0 and discount_amount > 0:
                    real_price = max(0, r["price"] - discount_amount)

                res_item = {
                    "id": res_id,
                    "therapist_name": therapist_name,
                    "customer_name": r["customer_name"],
                    "date_text": r["date_text"],
                    "start_time": r["start_time"],
                    "end_time": r["end_time"],
                    "course_name": r["course_name"],
                    "room_name": r["room_name"],
                    "is_luxury": r["is_luxury"],
                    "shimei_type": r["shimei_type"],
                    "price": real_price,
                    "nominate_charge": nominate_charge,
                    "cast_margin_nominate": cast_margin_nominate,
                    "cast_margin_system": cast_margin_system,
                    "cast_margin_option": cast_margin_option,
                    "discount_amount": discount_amount,
                    "cast_margin_discount": cast_margin_discount,
                    "margin_rate": margin_rate,
                    "therapist_net_pay": cast_total_pay if cast_total_pay > 0 else (real_price // 2)
                }

                monthly_reservations.append(res_item)

                date_cell = r["date_text"]
                if today_md in date_cell or today_str in date_cell:
                    today_reservations.append(res_item)
                    if r["room_name"] and r["room_name"] != "部屋未定":
                        today_room = r["room_name"]

                if yesterday_md in date_cell or yesterday_str in date_cell:
                    yesterday_reservations.append(res_item)

            active_reservations = today_reservations
            is_yesterday_mode = False
            if len(today_reservations) == 0 and len(yesterday_reservations) > 0:
                active_reservations = yesterday_reservations
                is_yesterday_mode = True

            active_reservations.sort(key=lambda x: self._parse_time_minutes(x.get("start_time", "00:00")))

            upcoming_shifts = []
            try:
                r_shift = session.get("https://my.caskan.jp/shift", timeout=10)
                soup_shift = BeautifulSoup(r_shift.text, "html.parser")
                headers = [th.text.strip() for th in soup_shift.select("table thead th")]

                cast_tr = None
                for tr in soup_shift.select("table tbody tr"):
                    c_link = tr.select_one("a[href*='/cast/view']")
                    if c_link and clean_name in re.sub(r"[\s　]+", "", c_link.text):
                        cast_tr = tr
                        break

                if cast_tr:
                    tds = cast_tr.find_all("td")
                    for idx, td in enumerate(tds):
                        text = td.text.strip()
                        time_match = re.search(r"(\d{1,2}:\d{2}[〜~]\d{1,2}:\d{2})", text)
                        if time_match:
                            shift_time = time_match.group(1)
                            header_date = headers[idx] if idx < len(headers) else f"Day{idx}"
                            date_match = re.search(r"(\d{1,2}/\d{1,2}[^ \n]*)", header_date)
                            date_label = date_match.group(1) if date_match else header_date
                            upcoming_shifts.append({
                                "date_time": f"{date_label} {shift_time}"
                            })
            except Exception as ex_shift:
                pass

            return {
                "therapist_name": therapist_name,
                "today_room": today_room,
                "today_reservations": active_reservations,
                "monthly_reservations": monthly_reservations,
                "upcoming_shifts": upcoming_shifts,
                "is_yesterday_mode": is_yesterday_mode
            }
        except Exception as e:
            logger.error(f"requestsスクレイピング例外: {e}")
            return self._generate_mock_data(therapist_name)

    def _generate_mock_data(self, therapist_name: str) -> Dict[str, Any]:
        return {
            "therapist_name": therapist_name,
            "today_room": "恵比寿",
            "today_reservations": [],
            "monthly_reservations": [],
            "upcoming_shifts": [],
            "is_yesterday_mode": False
        }
