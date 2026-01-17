from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import logging

# タイムゾーン設定（日本標準時）
JST = ZoneInfo("Asia/Tokyo")

logger = logging.getLogger(__name__)

# セッション保存（メモリ内、再起動時にリセット）
# 構造: {user_id: {"state": "waiting_for_destination", "origin_stop": "...", "timestamp": datetime, "fail_count": 0}}
user_sessions: Dict[str, Dict[str, Any]] = {}

# セッションタイムアウト（分）
SESSION_TIMEOUT_MINUTES = 10

# 最大失敗回数
MAX_FAIL_COUNT = 5


def start_waiting_for_destination_session(user_id: str, origin_stop: str) -> None:
    """
    目的地入力待ちセッションを開始

    Args:
        user_id: LINEユーザーID
        origin_stop: 出発地バス停名
    """
    user_sessions[user_id] = {
        "state": "waiting_for_destination",
        "origin_stop": origin_stop,
        "timestamp": datetime.now(JST),
        "fail_count": 0,
    }
    logger.info(f"Started destination session for {user_id}: {origin_stop}")


def start_waiting_for_favorite_route_session(user_id: str) -> None:
    """
    お気に入りルート入力待ちセッションを開始

    Args:
        user_id: LINEユーザーID
    """
    user_sessions[user_id] = {
        "state": "waiting_for_favorite_route",
        "timestamp": datetime.now(JST),
        "fail_count": 0,
    }
    logger.info(f"Started favorite route session for {user_id}")


def get_user_session(user_id: str) -> Optional[Dict[str, Any]]:
    """
    ユーザーのセッションを取得（タイムアウトチェック付き）

    Args:
        user_id: LINEユーザーID

    Returns:
        セッション情報の辞書、またはNone（セッションがない、またはタイムアウトの場合）
    """
    if user_id not in user_sessions:
        return None

    session = user_sessions[user_id]
    timestamp = session.get("timestamp")

    # タイムアウトチェック
    if timestamp:
        elapsed = datetime.now(JST) - timestamp
        if elapsed > timedelta(minutes=SESSION_TIMEOUT_MINUTES):
            logger.info(f"Session timeout for {user_id}")
            clear_user_session(user_id)
            return None

    return session


def clear_user_session(user_id: str) -> None:
    """
    ユーザーのセッションをクリア

    Args:
        user_id: LINEユーザーID
    """
    if user_id in user_sessions:
        logger.info(f"Cleared session for {user_id}")
        del user_sessions[user_id]


def increment_fail_count(user_id: str) -> int:
    """
    失敗カウントをインクリメント

    Args:
        user_id: LINEユーザーID

    Returns:
        更新後の失敗カウント
    """
    if user_id in user_sessions:
        user_sessions[user_id]["fail_count"] = (
            user_sessions[user_id].get("fail_count", 0) + 1
        )
        fail_count = user_sessions[user_id]["fail_count"]
        logger.info(f"Incremented fail count for {user_id}: {fail_count}")
        return fail_count
    return 0


def update_session_timestamp(user_id: str) -> None:
    """
    セッションのタイムスタンプを更新（会話が継続している場合）

    Args:
        user_id: LINEユーザーID
    """
    if user_id in user_sessions:
        user_sessions[user_id]["timestamp"] = datetime.now(JST)


def is_session_active(user_id: str) -> bool:
    """
    セッションがアクティブかどうかチェック

    Args:
        user_id: LINEユーザーID

    Returns:
        アクティブな場合True
    """
    return get_user_session(user_id) is not None
