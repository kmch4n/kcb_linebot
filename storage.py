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
