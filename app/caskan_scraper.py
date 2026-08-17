import logging
import asyncio
import datetime
import json
import os
import re
from typing import List, Dict, Any, Optional
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

class CaskanScraper:
    """
    caskan (my.caskan.jp) 予約・給与・シフト取得エンジン
    """
    
    def __init__(self, login_url: str = "https://my.caskan.jp/login", username: str = "staff", password: str = "arlt534", shop_id: str = "rilith"):
        self.login_url = login_url
        self.username = username
        self.password = password
        self.shop_id = shop_id
        self.cast_map = self._load_cast_map()

    def _load_cast_map(self) -> Dict[str, str]:
        map_path = os.path.join(os.path.dirname(__file__), "..", "cast_id_map.json")
        if os.path.exists(map_path):
            try:
                with open(map_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"cast_id_map.json 読み込みエラー: {e}")
        return {}

    def _parse_time_minutes(self, time_str: str) -> int:
        """時刻文字列 (例: '16:00', '24:50', '27:40') を数値(分)に変換してソート用数値を返す"""
        match = re.search(r"(\d{1,2}):(\d{2})", time_str)
        if match:
            h = int(match.group(1))
            m = int(match.group(2))
            return h * 60 + m
        return 99999

    async def fetch_today_data(self) -> Dict[str, Any]:
        if not self.username or not self.password:
            return {"date": datetime.date.today().strftime("%Y-%m-%d"), "shifts": [], "reservations": []}

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context()
                page = await context.new_page()
                
                await page.goto(self.login_url, wait_until="networkidle")
                await page.fill("input[name='shop_code']", self.shop_id)
                await page.fill("input[name='code']", self.username)
                await page.click("button[type='submit']")
                await page.wait_for_load_state("networkidle")
                await page.wait_for_timeout(1000)
                
                await page.fill("input[name='login_password']", self.password)
                await page.click("button[type='submit']")
                await page.wait_for_load_state("networkidle")
                await page.wait_for_timeout(2000)
                
                shifts = []
                textarea_el = await page.query_selector("textarea.textarea-auto")
                if textarea_el:
                    shift_text = await textarea_el.input_value()
                    for line in shift_text.split("\n"):
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
                await browser.close()
                return {
                    "date": datetime.date.today().strftime("%Y-%m-%d"),
                    "shifts": shifts,
                    "reservations": []
                }
        except Exception as e:
            logger.error(f"fetch_today_dataエラー: {e}")
            return {"date": datetime.date.today().strftime("%Y-%m-%d"), "shifts": [], "reservations": []}

    async def fetch_therapist_full_data(self, therapist_name: str) -> Dict[str, Any]:
        """
        指定セラピストの全データ取得（予約ソート順：時間の早い順）
        """
        today_date = datetime.date.today()
        yesterday_date = today_date - datetime.timedelta(days=1)
        
        today_str = today_date.strftime("%Y-%m-%d")
        yesterday_str = yesterday_date.strftime("%Y-%m-%d")
        month_start_str = today_date.replace(day=1).strftime("%Y-%m-%d")
        
        today_md = f"{today_date.month}/{today_date.day}"
        yesterday_md = f"{yesterday_date.month}/{yesterday_date.day}"
        
        clean_name = re.sub(r"[\s　]+", "", therapist_name)
        cast_id = self.cast_map.get(clean_name, "")
        
        if not self.username or not self.password:
            return self._generate_mock_data(therapist_name)

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context()
                page = await context.new_page()
                
                # 1. ログイン
                await page.goto(self.login_url, wait_until="networkidle")
                await page.fill("input[name='shop_code']", self.shop_id)
                await page.fill("input[name='code']", self.username)
                await page.click("button[type='submit']")
                await page.wait_for_load_state("networkidle")
                await page.wait_for_timeout(1000)
                
                await page.fill("input[name='login_password']", self.password)
                await page.click("button[type='submit']")
                await page.wait_for_load_state("networkidle")
                await page.wait_for_timeout(2000)

                # 2. 当月予約一覧
                if cast_id:
                    target_reserve_url = f"https://my.caskan.jp/reserve?mode=&sort=&date_from={month_start_str}&date_to=2026-08-31&cast_id={cast_id}"
                else:
                    target_reserve_url = f"https://my.caskan.jp/reserve?date_from={month_start_str}&date_to={today_str}"

                logger.info(f"キャスト [{therapist_name} (ID:{cast_id})] の予約一覧アクセス: {target_reserve_url}")
                await page.goto(target_reserve_url, wait_until="networkidle")
                await page.wait_for_timeout(2000)

                raw_reservations = []
                today_room = "未割当"
                
                rows = await page.query_selector_all("table.tbl-reserve-list tbody tr, table.table tbody tr")
                for row in rows:
                    try:
                        tds = await row.query_selector_all("td")
                        if len(tds) < 8:
                            continue
                            
                        cust_el = await row.query_selector("a[href*='/customer/view']")
                        cust_name = (await cust_el.inner_text()).strip() if cust_el else "フリーお客様"
                        
                        date_cell = (await tds[4].inner_text()).strip()
                        course_cell = (await tds[6].inner_text()).strip() if len(tds) > 6 else "90分"
                        room_cell = (await tds[7].inner_text()).strip() if len(tds) > 7 else "部屋未定"
                        price_cell = (await tds[8].inner_text()).strip() if len(tds) > 8 else "0"

                        shimei_el = await row.query_selector("span.text-xs, span.mg-left-sm")
                        raw_shimei = (await shimei_el.inner_text()).strip() if shimei_el else "指名なし"
                        
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

                        link_status = await row.query_selector("a.link-status")
                        res_id = await link_status.get_attribute("data-reserve-id") if link_status else None
                        if not res_id:
                            edit_link = await row.query_selector("a[href*='/reserve/edit?id=']")
                            if edit_link:
                                href = await edit_link.get_attribute("href")
                                m_id = re.search(r"id=(\d+)", href)
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

                # 3. 予約詳細画面より割引・給与生フィールドを取得
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
                            await page.goto(edit_url, wait_until="networkidle")
                            await page.wait_for_timeout(1000)

                            nom_val = await page.get_attribute("input[name='nominate_charge']", "value")
                            nom_back_val = await page.get_attribute("input[name='cast_margin_nominate']", "value")
                            sys_back_val = await page.get_attribute("input[name='cast_margin_system']", "value")
                            opt_back_val = await page.get_attribute("input[name='cast_margin_option']", "value")
                            disc_val = await page.get_attribute("input[name='discount2']", "value")
                            disc_back_val = await page.get_attribute("input[name='cast_margin_discount']", "value")
                            mrate_val = await page.get_attribute("input[name='margin_rate']", "value")

                            nominate_charge = int(re.sub(r"[^\d]", "", nom_val or "0"))
                            cast_margin_nominate = int(re.sub(r"[^\d]", "", nom_back_val or "0"))
                            cast_margin_system = int(re.sub(r"[^\d]", "", sys_back_val or "0"))
                            cast_margin_option = int(re.sub(r"[^\d]", "", opt_back_val or "0"))
                            discount_amount = int(re.sub(r"[^\d]", "", disc_val or "0"))
                            cast_margin_discount = int(re.sub(r"[^\d]", "", disc_back_val or "0"))
                            margin_rate = int(re.sub(r"[^\d]", "", mrate_val or "50"))
                            
                            cast_total_pay = (cast_margin_system + cast_margin_nominate + cast_margin_option) - cast_margin_discount
                        except Exception as ex_detail:
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

                # ★ 予約を「時間の早い順 (昇順: 例 16:00 ➔ 21:00 ➔ 24:50 ➔ 27:40)」で精密ソート ★
                active_reservations.sort(key=lambda x: self._parse_time_minutes(x.get("start_time", "00:00")))

                # 4. /shift 画面より時間付き出勤予定を取得
                upcoming_shifts = []
                try:
                    await page.goto("https://my.caskan.jp/shift", wait_until="networkidle")
                    await page.wait_for_timeout(2000)
                    
                    soup = BeautifulSoup(await page.content(), "html.parser")
                    headers = [th.text.strip() for th in soup.select("table thead th")]
                    
                    cast_tr = None
                    for tr in soup.select("table tbody tr"):
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
                except Exception as ex_shift_page:
                    pass

                await browser.close()
                logger.info(f"★ [{therapist_name}] 予約ソート完了(時間の早い順): 全{len(active_reservations)}件")

                return {
                    "therapist_name": therapist_name,
                    "today_room": today_room,
                    "today_reservations": active_reservations,
                    "monthly_reservations": monthly_reservations,
                    "upcoming_shifts": upcoming_shifts,
                    "is_yesterday_mode": is_yesterday_mode
                }
        except Exception as e:
            logger.error(f"スクレイピングエラー: {e}")
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
