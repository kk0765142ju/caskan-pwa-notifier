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

# キャストIDマップ (田島りり様: 71307 含む最新版)
CAST_ID_MAP = {
    "あんな": "75389",
    "ほのか": "75388",
    "愛沢るな": "71588",
    "真白のん": "71589",
    "星乃せら": "71590",
    "美波のん": "71591",
    "森永ここあ": "71587",
    "田島りり": "71307",
    "りり": "71307"
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
            session.get(self.login_url, timeout=5)

            step1_data = {
                "mode": "step1",
                "shop_code": self.shop_id,
                "code": self.username
            }
            session.post(self.login_url, data=step1_data, timeout=5)

            step2_data = {
                "mode": "step2",
                "login_password": self.password
            }
            session.post("https://my.caskan.jp/login/password", data=step2_data, timeout=5)

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
            r = session.get("https://my.caskan.jp/mypage", timeout=5)
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
        jst_tz = datetime.timezone(datetime.timedelta(hours=9))
        now_jst = datetime.datetime.now(jst_tz)
        today_date = now_jst.date()
        today_str = today_date.strftime("%Y-%m-%d") # 例: "2026-08-17"
        
        clean_target_name = re.sub(r"[\s　]+", "", therapist_name)
        cast_id = self.cast_map.get(clean_target_name, "")
        
        session = self._get_session()
        if not session:
            return self._generate_mock_data(therapist_name)

        try:
            # ★ ユーザー様ご指定のピンポイント日付範囲 (date_from={today_str}&date_to={today_str}) で限定検索 ★
            if cast_id:
                target_url = f"https://my.caskan.jp/reserve?mode=&sort=&date_from={today_str}&date_to={today_str}&cast_id={cast_id}&staff_id=&room_id=&reserve_route_id=&payment_id=&reserve_status_id=&word="
            else:
                target_url = f"https://my.caskan.jp/reserve?mode=&sort=&date_from={today_str}&date_to={today_str}&staff_id=&room_id=&reserve_route_id=&payment_id=&reserve_status_id=&word="

            r_res = session.get(target_url, timeout=5)
            soup_res = BeautifulSoup(r_res.text, "html.parser")

            today_room = "未割当"
            today_reservations = []

            rows = soup_res.select("table.tbl-reserve-list tr, table.table tr")
            for row in rows:
                try:
                    tds = row.select("td")
                    if len(tds) < 6:
                        continue

                    shimei_cell = tds[5].text.strip() if len(tds) > 5 else ""
                    clean_shimei_cell = re.sub(r"[\s　]+", "", shimei_cell)

                    # cast_id 未指定時等のための念のためキャスト名チェック
                    if cast_id == "" and clean_target_name not in clean_shimei_cell:
                        continue

                    cust_el = row.select_one("a[href*='/customer/view']")
                    cust_name = cust_el.text.strip() if cust_el else (tds[3].text.strip() if len(tds) > 3 else "お客様")

                    date_cell = tds[4].text.strip() if len(tds) > 4 else ""
                    course_cell = tds[6].text.strip() if len(tds) > 6 else "90分"
                    room_cell = tds[7].text.strip() if len(tds) > 7 else "部屋未定"
                    price_cell = tds[8].text.strip() if len(tds) > 8 else "0"

                    if "本指名" in shimei_cell:
                        shimei_type = "本指名"
                    elif "写真指名" in shimei_cell:
                        shimei_type = "写真指名"
                    elif "リピーター" in shimei_cell:
                        shimei_type = "リピーター"
                    elif "指名なし" in shimei_cell:
                        shimei_type = "指名なし"
                    else:
                        shimei_type = shimei_cell or "指名なし"

                    time_match = re.search(r"(\d{1,2}:\d{2})", date_cell)
                    start_time = time_match.group(1) if time_match else "00:00"

                    is_luxury = "luxury" in course_cell.lower() or "ラグジュアリー" in course_cell or "B" in course_cell
                    price_val = int(re.sub(r"[^\d]", "", price_cell) or 0)

                    nominate_charge = 2000 if ("本指名" in shimei_type or "写真指名" in shimei_type) else 0
                    cast_margin_nominate = nominate_charge
                    option_fee = (3000 if "70分" in course_cell else 4000) if is_luxury else 0

                    res_item = {
                        "id": None,
                        "therapist_name": therapist_name,
                        "customer_name": cust_name,
                        "date_text": date_cell,
                        "start_time": start_time,
                        "end_time": "終了未定",
                        "course_name": course_cell,
                        "room_name": room_cell,
                        "is_luxury": is_luxury,
                        "shimei_type": shimei_type,
                        "price": price_val,
                        "nominate_charge": nominate_charge,
                        "cast_margin_nominate": cast_margin_nominate,
                        "cast_margin_system": price_val // 2,
                        "cast_margin_option": option_fee,
                        "discount_amount": 0,
                        "cast_margin_discount": 0,
                        "margin_rate": 50,
                        "therapist_net_pay": price_val // 2
                    }

                    today_reservations.append(res_item)
                    if room_cell and room_cell != "部屋未定":
                        today_room = room_cell
                except Exception as ex_row:
                    continue

            today_reservations.sort(key=lambda x: self._parse_time_minutes(x.get("start_time", "00:00")))

            upcoming_shifts = []
            try:
                r_shift = session.get("https://my.caskan.jp/shift", timeout=3)
                soup_shift = BeautifulSoup(r_shift.text, "html.parser")
                headers = [th.text.strip() for th in soup_shift.select("table thead th")]

                cast_tr = None
                for tr in soup_shift.select("table tr"):
                    c_link = tr.select_one("a[href*='/cast/view']")
                    if c_link and clean_target_name in re.sub(r"[\s　]+", "", c_link.text):
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
                "today_reservations": today_reservations,
                "monthly_reservations": today_reservations,
                "upcoming_shifts": upcoming_shifts,
                "is_yesterday_mode": False
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
