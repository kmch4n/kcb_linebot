import requests
from typing import Optional, List, Dict
from datetime import datetime
from zoneinfo import ZoneInfo
import logging
from config import API_KEY, API_BASE_URL

# タイムゾーン設定（日本標準時）
JST = ZoneInfo("Asia/Tokyo")

logger = logging.getLogger(__name__)

# API設定
API_TIMEOUT = 10  # 秒


class BusAPIError(Exception):
    """バスAPI関連のエラー"""
    pass


def get_day_type(date: datetime = None) -> str:
    """
    曜日タイプを取得

    Args:
        date: 判定対象の日時（Noneの場合は現在時刻）

    Returns:
        "weekday", "saturday", "sunday" のいずれか
    """
    if date is None:
        date = datetime.now(JST)
    weekday = date.weekday()
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
    params = {"q": query, "limit": limit}

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


def validate_stop_exists(stop_name: str) -> bool:
    """
    バス停が存在するか確認

    Args:
        stop_name: バス停名

    Returns:
        存在する場合True、存在しない場合False

    Raises:
        BusAPIError: API通信エラー
    """
    stops = search_stops(stop_name, limit=1)
    return stops is not None and len(stops) > 0


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
        current_time = datetime.now(JST).strftime("%H:%M")

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
    time: Optional[str] = None,
    departure_stop_id: Optional[str] = None
) -> Optional[Dict]:
    """
    バスの現在位置を推定（時刻表ベース）

    Args:
        trip_id: トリップID（例: "00900_01001_4048"）
        time: 参照時刻（HH:MM or HH:MM:SS、Noneの場合は現在時刻）
        departure_stop_id: ユーザーの乗車予定バス停ID（前3つの停留所情報を取得する場合）

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
            "estimated_arrival_minutes": int,
            "previous_stops": [{"stop_id": str, "stop_name": str, "time": str}, ...],
            "boarding_stop": {"stop_id": str, "stop_name": str, "time": str}
        }

    Raises:
        BusAPIError: API通信エラー
    """
    url = f"{API_BASE_URL}/trip/{trip_id}/location"
    headers = {"X-API-Key": API_KEY}
    params = {}

    if time:
        params["time"] = time

    if departure_stop_id:
        params["departure_stop_id"] = departure_stop_id

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
    API位置情報をFlex Message用のrealtime_info形式に変換（縦リスト形式）

    Args:
        location_data: get_trip_location()から取得した位置情報
        route: 検索結果のroute情報（departure_time, departure_stop_id含む）

    Returns:
        realtime_info形式の辞書:
        {
            "previous_stops": [{"stop_name": str, "time": str}, ...],
            "boarding_stop": {"stop_name": str, "time": str},
            "bus_position": {
                "type": "between" | "at_stop",
                "current_stop": str,  # 停車中の場合
                "from_stop": str,     # 走行中の場合
                "to_stop": str        # 走行中の場合
            } または None
        }
    """
    if not location_data or not location_data.get("success"):
        return None

    # 前3つの停留所リストを取得
    previous_stops_data = location_data.get("previous_stops") or []
    boarding_stop_data = location_data.get("boarding_stop")

    # 停留所リストがない場合は表示しない
    if not previous_stops_data or not boarding_stop_data:
        return None

    # 停留所リストをFlex Message用に変換
    previous_stops = []
    for stop in previous_stops_data:
        previous_stops.append({
            "stop_name": stop.get("stop_name", ""),
            "time": stop.get("time", "")[:5]  # HH:MM形式に変換
        })

    boarding_stop = {
        "stop_name": boarding_stop_data.get("stop_name", ""),
        "time": boarding_stop_data.get("time", "")[:5]
    }

    # バスの現在位置を取得
    status = location_data.get("status")
    from_stop = location_data.get("from_stop") or {}
    to_stop = location_data.get("to_stop") or {}

    # バスが前3つの停留所の範囲内にいるかチェック
    bus_position = None

    if status == "between_stops" and from_stop and to_stop:
        from_stop_id = from_stop.get("stop_id")
        from_stop_name = from_stop.get("stop_name")

        # 前3つのstop_idとstop_nameリスト
        previous_stop_ids = [stop.get("stop_id") for stop in previous_stops_data]
        previous_stop_names = [stop.get("stop_name") for stop in previous_stops_data]

        # バスが何つ前にいるか計算
        stops_away = None
        if from_stop_name in previous_stop_names:
            idx = previous_stop_names.index(from_stop_name)
            stops_away = len(previous_stops) - idx  # 3 - 0 = 3, 3 - 1 = 2, 3 - 2 = 1
        elif from_stop_id in previous_stop_ids:
            idx = previous_stop_ids.index(from_stop_id)
            stops_away = len(previous_stops) - idx

        # バスが前3つの範囲内にいる場合
        if stops_away is not None:
            if stops_away == 0:
                # バスが乗車停留所に停車中
                bus_position = {
                    "type": "at_stop",
                    "current_stop": from_stop_name,
                    "stops_away": 0
                }
            else:
                # バスが走行中（1〜3つ前）
                bus_position = {
                    "type": "between",
                    "from_stop": from_stop_name,
                    "to_stop": to_stop.get("stop_name"),
                    "stops_away": stops_away
                }
        else:
            # バスが遠い（4つ以上前）
            bus_position = {
                "type": "far",
                "stops_away": 4  # 4つ以上前
            }

    elif status == "not_started":
        # 未出発の場合、バスはまだ始発にいる（遠い）
        bus_position = {
            "type": "far",
            "stops_away": 4  # 4つ以上前
        }

    # バスが遠い場合でもbus_positionを設定（Noneではなく）
    if bus_position is None:
        bus_position = {
            "type": "far",
            "stops_away": 4  # 4つ以上前
        }

    return {
        "previous_stops": previous_stops,
        "boarding_stop": boarding_stop,
        "bus_position": bus_position
    }
