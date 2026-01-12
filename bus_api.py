import requests
from typing import Optional, List, Dict
from datetime import datetime
import logging
from config import API_KEY, API_BASE_URL

logger = logging.getLogger(__name__)

# API設定
API_TIMEOUT = 10  # 秒


class BusAPIError(Exception):
    """バスAPI関連のエラー"""
    pass


def get_day_type() -> str:
    """
    現在の曜日タイプを取得

    Returns:
        "weekday", "saturday", "sunday" のいずれか
    """
    weekday = datetime.now().weekday()
    if weekday == 5:  # 土曜日
        return "saturday"
    elif weekday == 6:  # 日曜日
        return "sunday"
    else:  # 平日
        return "weekday"


def search_stops(query: str, limit: int = 5) -> Optional[List[Dict]]:
    """
    停留所検索

    Args:
        query: 検索クエリ（バス停名）
        limit: 最大結果数（デフォルト: 5）

    Returns:
        停留所情報のリスト、またはNone（エラー時）

    Raises:
        BusAPIError: API通信エラー
    """
    url = f"{API_BASE_URL}/stops/search"
    headers = {"X-API-Key": API_KEY}
    params = {"query": query, "limit": limit}

    try:
        response = requests.get(url, headers=headers, params=params, timeout=API_TIMEOUT)
        response.raise_for_status()
        data = response.json()

        if data.get("success"):
            return data.get("stops", [])
        else:
            logger.warning(f"Stop search failed: {data.get('error')}")
            return None

    except requests.exceptions.Timeout:
        raise BusAPIError("検索がタイムアウトしました。もう一度お試しください。")
    except requests.exceptions.ConnectionError:
        raise BusAPIError("バス停の検索に失敗しました。")
    except requests.exceptions.HTTPError as e:
        raise BusAPIError(f"API通信エラー: {e}")
    except Exception as e:
        logger.error(f"Unexpected error in search_stops: {e}")
        raise BusAPIError("予期しないエラーが発生しました。")


def search_routes(
    from_stop: str,
    to_stop: str,
    current_time: Optional[str] = None,
    day_type: str = "weekday",
    limit: int = 3
) -> Optional[List[Dict]]:
    """
    バス路線検索

    Args:
        from_stop: 出発バス停名
        to_stop: 目的地バス停名
        current_time: 検索時刻（HH:MM形式、Noneの場合は現在時刻）
        day_type: 曜日タイプ（"weekday", "saturday", "sunday"）
        limit: 最大結果数（デフォルト: 3）

    Returns:
        路線情報のリスト、またはNone（エラー時）

    Raises:
        BusAPIError: API通信エラー
    """
    url = f"{API_BASE_URL}/search"
    headers = {"X-API-Key": API_KEY}

    # 現在時刻を使用する場合
    if current_time is None:
        current_time = datetime.now().strftime("%H:%M")

    payload = {
        "from_stop": from_stop,
        "to_stop": to_stop,
        "current_time": current_time,
        "day_type": day_type,
        "limit": limit
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=API_TIMEOUT)

        # ステータスコードチェック前にJSONを取得
        data = response.json()

        # 400エラーの場合、APIのエラーメッセージを取得
        if response.status_code == 400:
            error_msg = data.get("error", "バス停名が見つかりません。")
            raise BusAPIError(error_msg)

        # その他のHTTPエラー
        response.raise_for_status()

        if data.get("success"):
            return data.get("routes", [])
        else:
            logger.warning(f"Route search failed: {data.get('error')}")
            return None

    except requests.exceptions.Timeout:
        raise BusAPIError("検索がタイムアウトしました。もう一度お試しください。")
    except requests.exceptions.ConnectionError:
        raise BusAPIError("バス路線の検索に失敗しました。")
    except BusAPIError:
        # 既にBusAPIErrorの場合はそのまま再raise
        raise
    except requests.exceptions.HTTPError as e:
        raise BusAPIError(f"API通信エラー: {e}")
    except Exception as e:
        logger.error(f"Unexpected error in search_routes: {e}")
        raise BusAPIError("予期しないエラーが発生しました。")


def search_nearby_stops(
    lat: float,
    lon: float,
    radius: int = 500,
    limit: int = 5
) -> Optional[List[Dict]]:
    """
    周辺バス停検索

    Args:
        lat: 緯度（-90 ~ 90）
        lon: 経度（-180 ~ 180）
        radius: 検索半径（メートル、デフォルト: 500、範囲: 1-5000）
        limit: 最大結果数（デフォルト: 5、範囲: 1-100）

    Returns:
        バス停情報のリスト（距離順）、またはNone（エラー時）
        各バス停: {"stop_name": str, "distance_meters": float}

    Raises:
        BusAPIError: API通信エラー
    """
    url = f"{API_BASE_URL}/stops/nearby"
    headers = {"X-API-Key": API_KEY}
    params = {
        "lat": lat,
        "lon": lon,
        "radius": radius,
        "limit": limit
    }

    try:
        response = requests.get(url, headers=headers, params=params, timeout=API_TIMEOUT)

        # ステータスコードチェック前にJSONを取得
        data = response.json()

        # 400エラーの場合、APIのエラーメッセージを取得
        if response.status_code == 400:
            error_msg = data.get("error", "無効な座標です。")
            raise BusAPIError(error_msg)

        # その他のHTTPエラー
        response.raise_for_status()

        stops = data.get("stops", [])
        return stops if stops else None

    except requests.exceptions.Timeout:
        raise BusAPIError("検索がタイムアウトしました。もう一度お試しください。")
    except requests.exceptions.ConnectionError:
        raise BusAPIError("バス停の検索に失敗しました。")
    except BusAPIError:
        # 既にBusAPIErrorの場合はそのまま再raise
        raise
    except requests.exceptions.HTTPError as e:
        raise BusAPIError(f"API通信エラー: {e}")
    except Exception as e:
        logger.error(f"Unexpected error in search_nearby_stops: {e}")
        raise BusAPIError("予期しないエラーが発生しました。")


def get_trip_location(
    trip_id: str,
    time: Optional[str] = None
) -> Optional[Dict]:
    """
    バスの現在位置を推定（時刻表ベース）

    Args:
        trip_id: トリップID（例: "00900_01001_4048"）
        time: 参照時刻（HH:MM or HH:MM:SS、Noneの場合は現在時刻）

    Returns:
        位置情報の辞書、またはNone（エラー時）
        {
            "success": true,
            "trip_id": str,
            "query_time": str,
            "status": "not_started" | "between_stops" | "arrived",
            "message": str,
            "from_stop": {"stop_id": str, "stop_name": str, "time": str},
            "to_stop": {"stop_id": str, "stop_name": str, "time": str},
            "estimated_arrival_minutes": int
        }

    Raises:
        BusAPIError: API通信エラー
    """
    url = f"{API_BASE_URL}/trip/{trip_id}/location"
    headers = {"X-API-Key": API_KEY}
    params = {}

    if time:
        params["time"] = time

    try:
        response = requests.get(url, headers=headers, params=params, timeout=API_TIMEOUT)

        # ステータスコードチェック前にJSONを取得
        data = response.json()

        # 400エラーの場合、APIのエラーメッセージを取得
        if response.status_code == 400:
            error_msg = data.get("error", "トリップ情報の取得に失敗しました。")
            raise BusAPIError(error_msg)

        # 404エラーの場合、トリップIDが見つからない
        if response.status_code == 404:
            logger.warning(f"Trip ID not found: {trip_id}")
            return None

        # その他のHTTPエラー
        response.raise_for_status()

        if data.get("success"):
            return data
        else:
            logger.warning(f"Trip location fetch failed: {data.get('error')}")
            return None

    except requests.exceptions.Timeout:
        logger.error(f"Timeout getting trip location for {trip_id}")
        # タイムアウトは致命的ではないので、Noneを返す（リアルタイム情報なしで表示）
        return None
    except requests.exceptions.ConnectionError:
        logger.error(f"Connection error getting trip location for {trip_id}")
        return None
    except BusAPIError:
        # 既にBusAPIErrorの場合はそのまま再raise
        raise
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP error getting trip location for {trip_id}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error in get_trip_location: {e}")
        return None


def convert_location_to_realtime_info(
    location_data: Dict,
    route: Dict
) -> Optional[Dict]:
    """
    API位置情報をFlex Message用のrealtime_info形式に変換

    Args:
        location_data: get_trip_location()から取得した位置情報
        route: 検索結果のroute情報（departure_time, departure_stop_id, arrival_stop_id含む）

    Returns:
        realtime_info形式の辞書、または None（表示不要の場合）
    """
    if not location_data or not location_data.get("success"):
        return None

    status = location_data.get("status")
    from_stop = location_data.get("from_stop") or {}
    to_stop = location_data.get("to_stop") or {}
    message = location_data.get("message", "")

    # ユーザーの乗車区間情報
    user_departure_stop_id = route.get("departure_stop_id")
    departure_time = route.get("departure_time", "")

    # 出発時刻までの時間を計算
    try:
        from datetime import datetime
        now = datetime.now()
        dep_time = datetime.strptime(departure_time, "%H:%M:%S")
        dep_datetime = now.replace(hour=dep_time.hour, minute=dep_time.minute, second=dep_time.second)

        # 出発時刻が過去の場合、翌日と見なす
        if dep_datetime < now:
            from datetime import timedelta
            dep_datetime += timedelta(days=1)

        minutes_until_departure = int((dep_datetime - now).total_seconds() / 60)
    except:
        # 時刻解析エラー時は表示しない
        return None

    # バスの現在位置が乗車区間に関連しているかチェック
    current_stop_id = from_stop.get("stop_id")
    next_stop_id = to_stop.get("stop_id") if to_stop else None

    # ステータス変換ロジック
    if status == "arrived":
        # 到着済み → リアルタイム情報を表示しない
        return None

    elif status == "not_started":
        # 未出発 → 出発時刻が近い場合のみ表示
        if minutes_until_departure <= 1:
            return {
                "status": "approaching",
                "current_stop": None,
                "next_stop": None,
                "estimated_arrival_minutes": minutes_until_departure,
                "message": "まもなく出発します"
            }
        elif minutes_until_departure <= 10:
            return {
                "status": "on_time",
                "current_stop": None,
                "next_stop": None,
                "estimated_arrival_minutes": minutes_until_departure,
                "message": f"まもなく発車します（{minutes_until_departure}分後）"
            }
        return None

    elif status == "between_stops":
        # バスが乗車区間に関連しているかチェック
        # 現在位置が出発地より前 → まだ来ていない（出発時刻で判定）
        if current_stop_id != user_departure_stop_id and next_stop_id != user_departure_stop_id:
            # 出発地を通過していない場合、出発時刻が10分以内なら表示
            if minutes_until_departure <= 1:
                return {
                    "status": "approaching",
                    "current_stop": from_stop.get("stop_name"),
                    "next_stop": to_stop.get("stop_name") if to_stop else None,
                    "estimated_arrival_minutes": minutes_until_departure,
                    "message": "まもなく到着します"
                }
            elif minutes_until_departure <= 10:
                return {
                    "status": "on_time",
                    "current_stop": from_stop.get("stop_name"),
                    "next_stop": to_stop.get("stop_name") if to_stop else None,
                    "estimated_arrival_minutes": minutes_until_departure,
                    "message": message
                }
            return None

        # バスが出発地付近にいる場合 → 接近中
        if minutes_until_departure <= 1:
            return {
                "status": "approaching",
                "current_stop": from_stop.get("stop_name"),
                "next_stop": to_stop.get("stop_name") if to_stop else None,
                "estimated_arrival_minutes": minutes_until_departure,
                "message": "まもなく到着します"
            }
        elif minutes_until_departure <= 3:
            return {
                "status": "approaching",
                "current_stop": from_stop.get("stop_name"),
                "next_stop": to_stop.get("stop_name") if to_stop else None,
                "estimated_arrival_minutes": minutes_until_departure,
                "message": message
            }
        elif minutes_until_departure <= 10:
            return {
                "status": "on_time",
                "current_stop": from_stop.get("stop_name"),
                "next_stop": to_stop.get("stop_name") if to_stop else None,
                "estimated_arrival_minutes": minutes_until_departure,
                "message": message
            }
        return None

    return None
