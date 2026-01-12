from flask import Flask, request, abort, jsonify
from linebot.v3.exceptions import InvalidSignatureError
from datetime import datetime
import logging

# ローカルモジュール
from config import handler, FLASK_PORT, FLASK_DEBUG
import handlers  # メッセージハンドラー登録

# Load environment variables
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    print(
        "Warning: python-dotenv not installed. Make sure environment variables are set."
    )

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)


@app.route("/")
def index():
    """ルートアクセス時のメッセージ"""
    return "KCB LINE Bot is running"


@app.route("/kcb_linebot/health", methods=["GET"])
def health_check():
    """ヘルスチェックエンドポイント"""
    return jsonify({
        "status": "ok",
        "service": "kcb_linebot",
        "timestamp": datetime.now().isoformat()
    })


@app.route("/kcb_linebot/callback", methods=["POST"])
def callback():
    """LINE Webhook エンドポイント"""
    # 署名検証
    signature = request.headers.get("X-Line-Signature")
    if not signature:
        logger.warning("No signature in request")
        abort(400)

    # リクエストボディ取得
    body = request.get_data(as_text=True)
    logger.info(f"Webhook received: {body[:100]}...")

    # ハンドラーで処理
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        logger.error("Invalid signature")
        abort(400)

    return "OK"


if __name__ == "__main__":
    logger.info("Starting KCB LINE Bot webhook server...")
    logger.info(f"Port: {FLASK_PORT}, Debug: {FLASK_DEBUG}")
    app.run(host="0.0.0.0", port=FLASK_PORT, debug=FLASK_DEBUG)
