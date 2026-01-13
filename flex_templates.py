from typing import List, Dict, Optional
import re
import logging

logger = logging.getLogger(__name__)


def create_bus_routes_flex(
    routes: List[Dict],
    from_stop: str,
    to_stop: str
) -> Dict:
    """
    バス路線検索結果のFlex Message生成

    Args:
        routes: search_routes()から取得した路線情報リスト
        from_stop: 出発地バス停名
        to_stop: 目的地バス停名

    Returns:
        単一Bubble or Carousel (複数結果の場合)
    """
    if not routes:
        return create_no_results_flex(from_stop, to_stop)

    bubbles = []
    for i, route in enumerate(routes[:3], 1):
        bubble = create_single_route_bubble(route, i, from_stop, to_stop)
        bubbles.append(bubble)

    # 単一結果 or Carousel
    if len(bubbles) == 1:
        return bubbles[0]
    else:
        return {
            "type": "carousel",
            "contents": bubbles,
        }


def create_single_route_bubble(
    route: Dict,
    index: int,
    from_stop: str,
    to_stop: str
) -> Dict:
    """
    単一路線のBubble生成

    Args:
        route: 路線情報
        index: 表示順序 (1, 2, 3)
        from_stop: 出発地
        to_stop: 目的地

    Returns:
        Bubble構造
    """
    route_name = route.get("route_name", "不明")
    headsign = route.get("headsign", "")
    dep_time = format_time(route.get("departure_time", ""))
    arr_time = format_time(route.get("arrival_time", ""))
    travel_time = route.get("travel_time_minutes", 0)
    stops_count = route.get("stops_count", 0)
    dep_stop_desc = route.get("departure_stop_desc", from_stop)
    arr_stop_desc = route.get("arrival_stop_desc", to_stop)

    # リアルタイム情報 (Phase 5で実装)
    realtime_info = route.get("realtime_info")  # 将来の拡張用

    # ヘッダー色を決定
    header_color = get_route_header_color(route_name)

    return {
        "type": "bubble",
        "size": "mega",
        "header": create_header(route_name, index, header_color, headsign),
        "body": create_body(
            dep_time, arr_time, travel_time,
            dep_stop_desc, arr_stop_desc,
            realtime_info, stops_count
        ),
        "footer": create_footer(),
        "styles": {
            "header": {"backgroundColor": header_color},
            "body": {"backgroundColor": "#1a1a1a"},
            "footer": {"backgroundColor": "#1a1a1a"},
        }
    }


def create_header(route_name: str, index: int, color: str, headsign: str = "") -> Dict:
    """ヘッダー部分を生成"""
    # コンテンツリスト
    contents = [
        {
            "type": "text",
            "text": f"{index}. 🚌 {route_name}",
            "size": "md",
            "weight": "bold",
            "color": "#ffffff",
            "wrap": True,
        }
    ]

    # 行先がある場合は2行目として追加
    if headsign:
        contents.append({
            "type": "text",
            "text": f"→ {headsign}",
            "size": "sm",
            "color": "#ffffff",
            "wrap": True,
            "margin": "xs",
        })

    return {
        "type": "box",
        "layout": "vertical",
        "contents": contents,
        "paddingAll": "12px",
        "backgroundColor": color,
    }


def create_body(
    dep_time: str,
    arr_time: str,
    travel_time: int,
    dep_stop_desc: str,
    arr_stop_desc: str,
    realtime_info: Optional[Dict] = None,
    stops_count: int = 0
) -> Dict:
    """ボディ部分を生成"""

    contents = []

    # 出発情報エリア
    contents.append(create_stop_info_box(
        icon="🚏",
        label="出発",
        time=dep_time,
        stop_desc=dep_stop_desc,
        bar_color="#70AD47",  # 緑
    ))

    # セパレータ
    contents.append({
        "type": "separator",
        "margin": "md",
        "color": "#404040",
    })

    # 所要時間・停車駅数
    contents.append(create_travel_time_box(travel_time, stops_count))

    # セパレータ
    contents.append({
        "type": "separator",
        "margin": "md",
        "color": "#404040",
    })

    # 到着情報エリア
    contents.append(create_stop_info_box(
        icon="🚩",
        label="到着",
        time=arr_time,
        stop_desc=arr_stop_desc,
        bar_color="#ED7D31",  # オレンジ
    ))

    # リアルタイム情報 (Phase 5)
    if realtime_info:
        contents.append({
            "type": "separator",
            "margin": "md",
            "color": "#404040",
        })
        contents.append(create_realtime_info_box(realtime_info))

    return {
        "type": "box",
        "layout": "vertical",
        "contents": contents,
        "paddingAll": "12px",
        "backgroundColor": "#1a1a1a",
    }


def create_stop_info_box(
    icon: str,
    label: str,
    time: str,
    stop_desc: str,
    bar_color: str
) -> Dict:
    """停留所情報ボックス (出発/到着)"""
    return {
        "type": "box",
        "layout": "horizontal",
        "contents": [
            # 左カラーバー
            {
                "type": "box",
                "layout": "vertical",
                "contents": [],
                "width": "5px",
                "backgroundColor": bar_color,
                "cornerRadius": "2px",
            },
            # コンテンツエリア
            {
                "type": "box",
                "layout": "vertical",
                "paddingStart": "12px",
                "flex": 1,
                "contents": [
                    # アイコン + ラベル + 時刻
                    {
                        "type": "box",
                        "layout": "horizontal",
                        "contents": [
                            {
                                "type": "text",
                                "text": icon,
                                "size": "md",
                                "flex": 0,
                            },
                            {
                                "type": "text",
                                "text": f" {label}",
                                "size": "xs",
                                "color": "#e0e0e0",
                                "flex": 0,
                            },
                            {
                                "type": "text",
                                "text": time,
                                "size": "xxl",
                                "weight": "bold",
                                "color": "#ffffff",
                                "align": "end",
                                "flex": 1,
                            },
                        ],
                    },
                    # 停留所詳細
                    {
                        "type": "text",
                        "text": f"📍 {stop_desc}",
                        "size": "xxs",
                        "color": "#e0e0e0",
                        "margin": "xs",
                        "wrap": True,
                    },
                ],
            },
        ],
        "margin": "md",
        "backgroundColor": "#2c2c2c",
        "cornerRadius": "8px",
        "paddingAll": "12px",
    }


def create_travel_time_box(travel_time: int, stops_count: int = 0) -> Dict:
    """所要時間・停車駅数ボックス"""
    # テキストを構築
    text = f"↓ 所要時間: {travel_time}分"
    if stops_count > 0:
        text += f" • {stops_count}停留所"

    return {
        "type": "box",
        "layout": "horizontal",
        "contents": [
            {
                "type": "text",
                "text": text,
                "size": "md",
                "color": "#ffffff",
                "align": "center",
                "weight": "bold",
                "wrap": True,
            },
        ],
        "margin": "md",
        "paddingAll": "8px",
    }


def create_realtime_info_box(realtime_info: Dict) -> Dict:
    """
    リアルタイム情報ボックス - 縦リスト形式でバス停を表示

    Args:
        realtime_info: {
            "previous_stops": [{"stop_name": str, "time": str}, ...],
            "boarding_stop": {"stop_name": str, "time": str},
            "bus_position": {
                "type": "between" | "at_stop",
                "current_stop": str,
                "from_stop": str,
                "to_stop": str
            } または None
        }
    """
    previous_stops = realtime_info.get("previous_stops", [])
    boarding_stop = realtime_info.get("boarding_stop", {})
    bus_position = realtime_info.get("bus_position")

    contents = []

    # バス位置の状態メッセージを追加
    if bus_position:
        bus_type = bus_position.get("type")
        stops_away = bus_position.get("stops_away", 0)

        status_message = ""
        if bus_type == "between" and stops_away >= 1:
            status_message = f"🚍 {stops_away}個前のバス停を出発しました"
        elif bus_type == "at_stop" and stops_away >= 1:
            status_message = f"🚍 {stops_away}つ前の停留所に停車中"
        elif bus_type == "far":
            status_message = f"バスはまだ遠くにいます。({stops_away}つ以上前の停留所)"

        if status_message:
            contents.append({
                "type": "text",
                "text": status_message,
                "size": "xs",
                "color": "#70AD47" if bus_type != "far" else "#a0a0a0",
                "weight": "bold" if bus_type != "far" else "regular",
                "margin": "none",
            })
            # セパレータ
            contents.append({
                "type": "separator",
                "margin": "md",
                "color": "#404040",
            })

    # 前3つの停留所を縦に表示
    for i, stop in enumerate(previous_stops):
        # 停留所名 + 時刻
        contents.append({
            "type": "box",
            "layout": "horizontal",
            "contents": [
                {
                    "type": "text",
                    "text": stop.get("stop_name", ""),
                    "size": "xxs",
                    "color": "#e0e0e0",
                    "flex": 1,
                    "wrap": True,
                },
                {
                    "type": "text",
                    "text": stop.get("time", ""),
                    "size": "xxs",
                    "color": "#a0a0a0",
                    "align": "end",
                    "flex": 0,
                },
            ],
            "margin": "none" if i == 0 else "sm",
        })

        # 矢印（バス位置表示の可能性あり）
        arrow_text = "↓"

        # バスが停車中の場合
        if bus_position and bus_position.get("type") == "at_stop":
            if stop.get("stop_name") == bus_position.get("current_stop"):
                arrow_text = "🚍️停車中"

        # バスが走行中の場合（この停留所の次の停留所へ向かっている）
        if bus_position and bus_position.get("type") == "between":
            if stop.get("stop_name") == bus_position.get("from_stop"):
                arrow_text = "↓  🚍️走行中"

        contents.append({
            "type": "text",
            "text": arrow_text,
            "size": "sm",
            "color": "#70AD47" if "🚍️" in arrow_text else "#a0a0a0",
            "margin": "xs",
            "weight": "bold" if "🚍️" in arrow_text else "regular",
        })

    # 乗車予定バス停
    contents.append({
        "type": "box",
        "layout": "horizontal",
        "contents": [
            {
                "type": "text",
                "text": f"{boarding_stop.get('stop_name', '')}（乗車）",
                "size": "xxs",
                "color": "#ffffff",
                "flex": 1,
                "weight": "bold",
                "wrap": True,
            },
            {
                "type": "text",
                "text": boarding_stop.get("time", ""),
                "size": "xxs",
                "color": "#e0e0e0",
                "align": "end",
                "flex": 0,
            },
        ],
        "margin": "sm",
        "backgroundColor": "#2c2c2c",
        "cornerRadius": "4px",
        "paddingAll": "8px",
    })

    return {
        "type": "box",
        "layout": "vertical",
        "contents": contents,
        "margin": "md",
        "backgroundColor": "#1f1f1f",
        "cornerRadius": "8px",
        "paddingAll": "12px",
    }


def create_footer() -> Dict:
    """フッター部分を生成"""
    return {
        "type": "box",
        "layout": "vertical",
        "contents": [
            {
                "type": "text",
                "text": "※時刻表ベースの目安です。バスは数分遅れることがあります。",
                "size": "xxs",
                "color": "#999999",
                "align": "center",
                "wrap": True,
            },
        ],
        "paddingAll": "12px",
        "backgroundColor": "#1a1a1a",
    }


def format_time(time_str: str) -> str:
    """時刻フォーマット HH:MM:SS → HH:MM"""
    if not time_str:
        return "不明"

    parts = time_str.split(":")
    if len(parts) >= 2:
        return f"{parts[0]}:{parts[1]}"
    return time_str


def get_route_header_color(route_name: str) -> str:
    """
    路線番号に基づいてヘッダー色を決定

    Args:
        route_name: 路線名（例: "市バス９", "急行101"）

    Returns:
        ヘッダー背景色（Hex形式）
    """
    # 路線番号を抽出
    route_num = extract_route_number(route_name)

    # 色分けマップ
    if 1 <= route_num < 20:
        return "#2d5016"    # 緑系 (1-19番)
    elif 20 <= route_num < 40:
        return "#1e3a5f"   # 青系 (20-39番)
    elif 40 <= route_num < 60:
        return "#5f2d11"   # 茶系 (40-59番)
    elif 60 <= route_num < 80:
        return "#4a1e5f"   # 紫系 (60-79番)
    elif 80 <= route_num < 300:
        return "#5f1e1e"   # 赤系 (80番以上)
    else:
        return "#2d5016"  # デフォルト: 緑


def extract_route_number(route_name: str) -> int:
    """
    路線名から番号を抽出

    Args:
        route_name: 路線名（例: "市バス９", "急行101", "特101甲"）

    Returns:
        路線番号（抽出できない場合は0）
    """
    # 数字のみを抽出
    match = re.search(r'\d+', route_name)
    if match:
        try:
            return int(match.group())
        except ValueError:
            logger.warning(f"Failed to parse route number from: {route_name}")
            return 0
    return 0


def create_no_results_flex(from_stop: str, to_stop: str) -> Dict:
    """検索結果なしのFlex Message"""
    return {
        "type": "bubble",
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": "⚠️ 路線が見つかりませんでした",
                    "size": "lg",
                    "weight": "bold",
                    "color": "#E74C3C",
                    "align": "center",
                },
                {
                    "type": "separator",
                    "margin": "md",
                    "color": "#404040",
                },
                {
                    "type": "text",
                    "text": f"{from_stop} から {to_stop} への路線が見つかりませんでした。",
                    "size": "sm",
                    "color": "#e0e0e0",
                    "wrap": True,
                    "margin": "md",
                },
                {
                    "type": "text",
                    "text": "バス停名を確認して、もう一度お試しください。",
                    "size": "sm",
                    "color": "#e0e0e0",
                    "wrap": True,
                    "margin": "xs",
                },
            ],
            "paddingAll": "20px",
            "backgroundColor": "#1a1a1a",
        },
    }
