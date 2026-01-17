"""
ユーザー検索履歴の保存・管理モジュール

fcntlロックを使用した安全なJSON読み書きを実装
"""

import json
import fcntl
import os
import logging
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# データディレクトリ
DATA_DIR = Path(__file__).parent / "data"
SEARCH_HISTORY_FILE = DATA_DIR / "search_history.json"

# お気に入り上限
MAX_FAVORITES = 5


def _ensure_data_dir():
    """データディレクトリが存在することを確認"""
    DATA_DIR.mkdir(exist_ok=True)


def _read_search_history() -> Dict:
    """
    検索履歴ファイルを読み込み（fcntl共有ロック）

    Returns:
        検索履歴の辞書
    """
    _ensure_data_dir()

    if not SEARCH_HISTORY_FILE.exists():
        return {}

    try:
        with open(SEARCH_HISTORY_FILE, "r", encoding="utf-8") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_SH)
            try:
                data = json.load(f)
                return data
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    except json.JSONDecodeError:
        logger.error("Failed to decode search_history.json")
        return {}
    except Exception as e:
        logger.error(f"Error reading search history: {e}")
        return {}


def _write_search_history(data: Dict):
    """
    検索履歴ファイルに書き込み（fcntl排他ロック）

    Args:
        data: 検索履歴の辞書
    """
    _ensure_data_dir()

    try:
        with open(SEARCH_HISTORY_FILE, "a+", encoding="utf-8") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                f.seek(0)
                f.truncate()
                json.dump(data, f, ensure_ascii=False, indent=2)
                f.flush()  # Pythonバッファをフラッシュ
                os.fsync(f.fileno())
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    except Exception as e:
        logger.error(f"Error writing search history: {e}")


def add_search_history(user_id: str, from_stop: str, to_stop: str):
    """
    検索履歴を追加または更新

    Args:
        user_id: ユーザーID
        from_stop: 出発地
        to_stop: 目的地
    """
    data = _read_search_history()

    if user_id not in data:
        data[user_id] = {"search_history": []}

    # 既存の履歴から同じルートを検索
    search_history = data[user_id]["search_history"]
    found = False

    for entry in search_history:
        if entry["from_stop"] == from_stop and entry["to_stop"] == to_stop:
            entry["count"] = entry.get("count", 1) + 1
            entry["last_searched"] = datetime.now().isoformat()
            found = True
            break

    # 新規ルートの場合は追加
    if not found:
        search_history.append({
            "from_stop": from_stop,
            "to_stop": to_stop,
            "count": 1,
            "last_searched": datetime.now().isoformat()
        })

    data[user_id]["search_history"] = search_history
    _write_search_history(data)
    logger.info(f"Added search history for {user_id}: {from_stop} -> {to_stop}")


def get_top_searches(user_id: str, limit: int = 3) -> List[Dict]:
    """
    ユーザーのトップ検索履歴を取得

    Args:
        user_id: ユーザーID
        limit: 取得件数（デフォルト: 3）

    Returns:
        検索履歴のリスト（頻度順）
        [{"from_stop": str, "to_stop": str, "count": int}, ...]
    """
    data = _read_search_history()

    if user_id not in data:
        return []

    search_history = data[user_id].get("search_history", [])

    # 頻度順にソート
    sorted_history = sorted(
        search_history,
        key=lambda x: x.get("count", 0),
        reverse=True
    )

    return sorted_history[:limit]


def add_favorite(user_id: str, from_stop: str, to_stop: str) -> bool:
    """
    お気に入りルートを追加

    Args:
        user_id: ユーザーID
        from_stop: 出発地
        to_stop: 目的地

    Returns:
        True: 追加成功, False: 上限到達または既に登録済み
    """
    data = _read_search_history()

    if user_id not in data:
        data[user_id] = {"search_history": [], "favorites": []}

    if "favorites" not in data[user_id]:
        data[user_id]["favorites"] = []

    favorites = data[user_id]["favorites"]

    # 既に登録済みかチェック
    for fav in favorites:
        if fav["from_stop"] == from_stop and fav["to_stop"] == to_stop:
            logger.info(f"Favorite already exists for {user_id}: {from_stop} -> {to_stop}")
            return False

    # 上限チェック
    if len(favorites) >= MAX_FAVORITES:
        logger.info(f"Favorites limit reached for {user_id}")
        return False

    # 新規追加
    favorites.append({
        "from_stop": from_stop,
        "to_stop": to_stop,
        "added_at": datetime.now().isoformat()
    })

    data[user_id]["favorites"] = favorites
    _write_search_history(data)
    logger.info(f"Added favorite for {user_id}: {from_stop} -> {to_stop}")
    return True


def remove_favorite(user_id: str, from_stop: str, to_stop: str) -> bool:
    """
    お気に入りルートを削除

    Args:
        user_id: ユーザーID
        from_stop: 出発地
        to_stop: 目的地

    Returns:
        True: 削除成功, False: 見つからなかった
    """
    data = _read_search_history()

    if user_id not in data or "favorites" not in data[user_id]:
        return False

    favorites = data[user_id]["favorites"]
    original_length = len(favorites)

    # 一致するお気に入りを除外
    favorites = [
        fav for fav in favorites
        if not (fav["from_stop"] == from_stop and fav["to_stop"] == to_stop)
    ]

    if len(favorites) == original_length:
        return False  # 見つからなかった

    data[user_id]["favorites"] = favorites
    _write_search_history(data)
    logger.info(f"Removed favorite for {user_id}: {from_stop} -> {to_stop}")
    return True


def get_favorites(user_id: str) -> List[Dict]:
    """
    ユーザーのお気に入りルートを取得

    Args:
        user_id: ユーザーID

    Returns:
        お気に入りルートのリスト
        [{"from_stop": str, "to_stop": str, "added_at": str}, ...]
    """
    data = _read_search_history()

    if user_id not in data:
        return []

    return data[user_id].get("favorites", [])


def is_favorite(user_id: str, from_stop: str, to_stop: str) -> bool:
    """
    指定ルートがお気に入りかどうか確認

    Args:
        user_id: ユーザーID
        from_stop: 出発地
        to_stop: 目的地

    Returns:
        お気に入りの場合True
    """
    favorites = get_favorites(user_id)
    for fav in favorites:
        if fav["from_stop"] == from_stop and fav["to_stop"] == to_stop:
            return True
    return False
