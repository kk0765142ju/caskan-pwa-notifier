import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class WebPushNotifier:
    """
    VAPID認証を使用したWeb Push通知送信モジュール (Vercel環境安全対応)
    """
    
    DEFAULT_PUBLIC_KEY = "BEl62iUYgUivxIkv69yViEuiBIa-m9GYvZObMzV1Z6fX-Z_x8qQ1P"
    DEFAULT_PRIVATE_KEY = "your-vapid-private-key-placeholder"
    DEFAULT_CLAIMS_EMAIL = "mailto:admin@example.com"
    
    def __init__(self, private_key: Optional[str] = None, public_key: Optional[str] = None, claims_email: Optional[str] = None):
        self.private_key = private_key or self.DEFAULT_PRIVATE_KEY
        self.public_key = public_key or self.DEFAULT_PUBLIC_KEY
        self.claims_email = claims_email or self.DEFAULT_CLAIMS_EMAIL

    def send_notification(
        self,
        subscription_info: Dict[str, Any],
        title: str,
        body: str,
        icon_url: str = "/static/icon.png",
        action_url: str = "/",
        data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        特定のセラピストのPush Subscription宛てに通知を送信
        """
        if not subscription_info or "endpoint" not in subscription_info:
            logger.warning("有効なPush Subscription情報がありません。")
            return False
            
        payload = {
            "title": title,
            "body": body,
            "icon": icon_url,
            "url": action_url,
            "data": data or {}
        }
        
        try:
            from pywebpush import webpush, WebPushException
            webpush(
                subscription_info=subscription_info,
                data=json.dumps(payload),
                vapid_private_key=self.private_key,
                vapid_claims={"sub": self.claims_email}
            )
            logger.info(f"Web Push送信成功: {title}")
            return True
        except Exception as e:
            logger.warning(f"Web Push送信スキップ: {e}")
            return False
