import os
import sys
from linebot.v3 import WebhookHandler
from linebot.v3.messaging import Configuration

# 環境変数読み込み
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("Warning: python-dotenv not installed. Make sure environment variables are set.")

# LINE API 認証情報（必須）
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")

# バスAPI設定
API_KEY = os.getenv("API_KEY")
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8081/kcb_api")

# Flask設定（オプション）
FLASK_PORT = int(os.getenv("FLASK_PORT", "8000"))
FLASK_DEBUG = os.getenv("FLASK_DEBUG", "False").lower() == "true"

# 必須変数チェック
if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_CHANNEL_SECRET:
    print("Error: LINE_CHANNEL_ACCESS_TOKEN and LINE_CHANNEL_SECRET must be set in .env")
    sys.exit(1)

# LINE SDK設定オブジェクト
configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)
