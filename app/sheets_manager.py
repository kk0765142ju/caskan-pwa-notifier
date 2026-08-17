import json
import logging
import datetime
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class SheetsManager:
    """
    Googleスプレッドシート操作・データ保持モジュール
    """
    
    def __init__(self, spreadsheet_id: Optional[str] = None, credentials_path: Optional[str] = None):
        self.spreadsheet_id = spreadsheet_id
        self.credentials_path = credentials_path
        self.client = None
        self.spreadsheet = None
        # インメモリフォールバック用（ローカルテストやAPIキー未指定時）
        self._mock_therapist_mapping: Dict[str, Dict[str, Any]] = {}
        self._mock_reservations: List[Dict[str, Any]] = []

    def connect(self) -> bool:
        """
        gspreadクライアントの初期化接続
        """
        try:
            import gspread
            from google.oauth2.service_account import Credentials
            
            if not self.credentials_path or not self.spreadsheet_id:
                logger.info("スプレッドシート情報が未指定のため、ローカルインメモリストレージモードで動作します。")
                return False
                
            scopes = [
                'https://www.googleapis.com/auth/spreadsheets',
                'https://www.googleapis.com/auth/drive'
            ]
            creds = Credentials.from_service_account_file(self.credentials_path, scopes=scopes)
            self.client = gspread.authorize(creds)
            self.spreadsheet = self.client.open_by_key(self.spreadsheet_id)
            logger.info("Googleスプレッドシートへの接続に成功しました。")
            return True
        except Exception as e:
            logger.warning(f"Googleスプレッドシート接続スキップ (インメモリ動作): {e}")
            return False

    def register_therapist_subscription(
        self,
        therapist_name: str,
        subscription_json: Dict[str, Any],
        is_fixed_salary: bool = False,
        is_discount_exempt: bool = False
    ) -> bool:
        """
        セラピスト名とPush Subscription情報の紐付け登録
        """
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        record = {
            "therapist_name": therapist_name,
            "subscription": subscription_json,
            "is_fixed_salary": is_fixed_salary,
            "is_discount_exempt": is_discount_exempt,
            "updated_at": now_str
        }
        self._mock_therapist_mapping[therapist_name] = record
        
        if self.spreadsheet:
            try:
                sheet = self.spreadsheet.worksheet("セラピストマッピング")
                # 既存検索 & 更新 or 追加
                records = sheet.get_all_records()
                row_idx = None
                for idx, r in enumerate(records, start=2):
                    if r.get("セラピスト名") == therapist_name:
                        row_idx = idx
                        break
                
                sub_str = json.dumps(subscription_json, ensure_ascii=False)
                row_data = [therapist_name, sub_str, is_fixed_salary, is_discount_exempt, now_str]
                if row_idx:
                    sheet.update(f"A{row_idx}:E{row_idx}", [row_data])
                else:
                    sheet.append_row(row_data)
                return True
            except Exception as e:
                logger.error(f"スプレッドシート書込エラー: {e}")
                
        return True

    def get_therapist_mapping(self, therapist_name: str) -> Optional[Dict[str, Any]]:
        """
        指定されたセラピストのマッピング（Push Subscription含む）情報を取得
        """
        if therapist_name in self._mock_therapist_mapping:
            return self._mock_therapist_mapping[therapist_name]
            
        if self.spreadsheet:
            try:
                sheet = self.spreadsheet.worksheet("セラピストマッピング")
                records = sheet.get_all_records()
                for r in records:
                    if r.get("セラピスト名") == therapist_name:
                        sub_json = json.loads(r.get("Push Subscription (JSON)", "{}"))
                        return {
                            "therapist_name": therapist_name,
                            "subscription": sub_json,
                            "is_fixed_salary": bool(r.get("固定給フラグ")),
                            "is_discount_exempt": bool(r.get("割引適用外")),
                            "updated_at": r.get("登録日時")
                        }
            except Exception as e:
                logger.error(f"スプレッドシート読込エラー: {e}")
                
        return None

    def get_all_therapist_mappings(self) -> Dict[str, Dict[str, Any]]:
        """
        全セラピストのマッピング一覧を取得
        """
        result = dict(self._mock_therapist_mapping)
        if self.spreadsheet:
            try:
                sheet = self.spreadsheet.worksheet("セラピストマッピング")
                records = sheet.get_all_records()
                for r in records:
                    tname = r.get("セラピスト名")
                    if tname:
                        sub_json = json.loads(r.get("Push Subscription (JSON)", "{}"))
                        result[tname] = {
                            "therapist_name": tname,
                            "subscription": sub_json,
                            "is_fixed_salary": bool(r.get("固定給フラグ")),
                            "is_discount_exempt": bool(r.get("割引適用外")),
                            "updated_at": r.get("登録日時")
                        }
            except Exception as e:
                logger.error(f"全マッピング取得エラー: {e}")
        return result
