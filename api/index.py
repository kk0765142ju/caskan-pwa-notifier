import sys
import os

# appモジュールのインポートパスを追加
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from app.main import app
