import os
import json
import logging
import datetime
import re
from typing import Dict, Any, Optional
from fastapi import FastAPI, Request, Query, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.payroll_calculator import PayrollCalculator
from app.caskan_scraper import CaskanScraper
from app.sheets_manager import SheetsManager
from app.push_notifier import WebPushNotifier

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="aroma Rilith Caskan PWA Notifier")

static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

CASKAN_USER = os.getenv("CASKAN_USER", "staff")
CASKAN_PASS = os.getenv("CASKAN_PASS", "arlt534")
CASKAN_SHOP = os.getenv("CASKAN_SHOP", "rilith")

scraper = CaskanScraper(
    username=CASKAN_USER,
    password=CASKAN_PASS,
    shop_id=CASKAN_SHOP
)
sheets_mgr = SheetsManager(
    spreadsheet_id=os.getenv("SPREADSHEET_ID", ""),
    credentials_path=os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
)
sheets_mgr.connect()

push_notifier = WebPushNotifier(
    private_key=os.getenv("VAPID_PRIVATE_KEY"),
    public_key=os.getenv("VAPID_PUBLIC_KEY")
)

_last_reservations_cache: Dict[str, Any] = {}

@app.get("/", response_class=HTMLResponse)
async def get_index():
    html_path = os.path.join(static_dir, "index.html")
    with open(html_path, "r", encoding="utf-8") as f:
        return f.read()

@app.get("/api/therapists")
async def get_active_therapists():
    """新店舗 [rilith] の前日・本日出勤キャスト ＆ 全キャストリスト取得"""
    today_therapists = ["森永ここあ", "美波のん", "真白のん", "星乃せら", "あんな", "ほのか"]
    try:
        caskan_data = await scraper.fetch_today_data()
        shifts = caskan_data.get("shifts", [])
        if shifts:
            today_therapists = [s["therapist_name"] for s in shifts if "therapist_name" in s]
    except Exception as e:
        logger.warning(f"出勤キャスト取得例外: {e}")

    cast_map = scraper.cast_map
    all_therapists = list(cast_map.keys())

    combined = []
    seen = set()
    
    for t in today_therapists:
        clean = re.sub(r"[\s　]+", "", t)
        if clean and clean not in seen:
            seen.add(clean)
            combined.append(t)
            
    for t in sorted(all_therapists):
        clean = re.sub(r"[\s　]+", "", t)
        if clean and clean not in seen:
            seen.add(clean)
            combined.append(t)
            
    return {
        "therapists": combined,
        "today_therapists": today_therapists
    }

@app.post("/api/subscribe")
async def register_subscription(request: Request):
    body = await request.json()
    therapist_name = body.get("therapist_name")
    subscription = body.get("subscription")
    
    if not therapist_name or not subscription:
        return JSONResponse({"status": "error", "message": "無効なリクエストです。"}, status_code=400)
        
    sheets_mgr.register_therapist_subscription(therapist_name, subscription)
    logger.info(f"セラピスト [{therapist_name}] のWeb Push通知登録が完了しました。")
    return {"status": "success", "message": f"{therapist_name}さんの通知登録が完了しました。"}

@app.get("/api/therapist/data")
async def get_therapist_data(name: str = Query(...)):
    """セラピストピンポイントデータ取得 (前日リアルデータ対応)"""
    tdata = await scraper.fetch_therapist_full_data(name)
    today_res = tdata.get("today_reservations", [])
    
    mapping = sheets_mgr.get_therapist_mapping(name) or {}
    
    today_summary = PayrollCalculator.calculate_daily_summary(
        reservations=today_res,
        is_fixed_salary=mapping.get("is_fixed_salary", False),
        is_discount_exempt=mapping.get("is_discount_exempt", False)
    )
    
    upcoming_shifts_raw = tdata.get("upcoming_shifts", [])
    upcoming_list = [us.get("date_time", "") for us in upcoming_shifts_raw]

    return {
        "therapist_name": name,
        "today_room": tdata.get("today_room", "未割当"),
        "summary": today_summary,
        "reservations": today_summary["reservations"],
        "next_shift": "出勤データあり" if len(today_res) > 0 else "出勤予定あり",
        "upcoming_shifts": upcoming_list,
        "is_yesterday_mode": tdata.get("is_yesterday_mode", False)
    }

@app.api_route("/cron/15min-batch", methods=["GET", "POST"])
async def run_15min_batch(background_tasks: BackgroundTasks):
    global _last_reservations_cache
    logger.info("--- 15分監視バッチ開始 ---")
    mappings = sheets_mgr.get_all_therapist_mappings()
    
    for therapist_name, mapping in mappings.items():
        tdata = await scraper.fetch_therapist_full_data(therapist_name)
        t_current = tdata.get("today_reservations", [])
        t_last = _last_reservations_cache.get(therapist_name, [])
        
        last_ids = {r.get("id") for r in t_last if "id" in r}
        new_reservations = [r for r in t_current if r.get("id") not in last_ids]
        
        if new_reservations and mapping.get("subscription"):
            summary = PayrollCalculator.calculate_daily_summary(
                t_current,
                is_fixed_salary=mapping.get("is_fixed_salary", False),
                is_discount_exempt=mapping.get("is_discount_exempt", False)
            )
            
            title = "【新規予約が入りました！🔔】"
            body = (
                f"{therapist_name}さん、新しい予約が追加されました。\n"
                f"想定確定給与: ¥{summary['total_therapist_net_pay']:,} (歩合率{summary['slide_rate']}%)\n"
                f"本日予約計: {len(t_current)}件"
            )
            
            push_notifier.send_notification(
                subscription_info=mapping["subscription"],
                title=title,
                body=body
            )
            
        _last_reservations_cache[therapist_name] = t_current
        
    logger.info("--- 15分監視バッチ完了 ---")
    return {"status": "success"}
