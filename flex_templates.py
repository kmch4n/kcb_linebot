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
    dep_time = format_time(route.get("departure_time", ""))
    arr_time = format_time(route.get("arrival_time", ""))
    travel_time = route.get("travel_time_minutes", 0)
    dep_stop_desc = route.get("departure_stop_desc", from_stop)
    arr_stop_desc = route.get("arrival_stop_desc", to_stop)

    # リアルタイム情報 (Phase 5で実装)
    realtime_info = route.get("realtime_info")  # 将来の拡張用

    # ヘッダー色を決定
    header_color = get_route_header_color(route_name)

    return {
        "type": "bubble",
        "size": "mega",
        "header": create_header(route_name, index, header_color),
        "body": create_body(
            dep_time, arr_time, travel_time,
            dep_stop_desc, arr_stop_desc,
            realtime_info
        ),
        "footer": create_footer(),
        "styles": {
            "header": {"backgroundColor": header_color},
            "body": {"backgroundColor": "#1a1a1a"},
            "footer": {"backgroundColor": "#1a1a1a"},
        }
    }


def create_header(route_name: str, index: int, color: str) -> Dict:
    """ヘッダー部分を生成"""
    return {
        "type": "box",
        "layout": "horizontal",
        "contents": [
            {
                "type": "text",
                "text": f"{index}. 🚌 {route_name}",
                "size": "lg",
                "weight": "bold",
                "color": "#ffffff",
                "flex": 1,
            }
        ],
        "paddingAll": "12px",
        "backgroundColor": color,
    }


def create_body(
    dep_time: str,
    arr_time: str,
    travel_time: int,
    dep_stop_desc: str,
    arr_stop_desc: str,
    realtime_info: Optional[Dict] = None
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

    # 所要時間
    contents.append(create_travel_time_box(travel_time))

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
                        "size": "sm",
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


def create_travel_time_box(travel_time: int) -> Dict:
    """所要時間ボックス"""
    return {
        "type": "box",
        "layout": "horizontal",
        "contents": [
            {
                "type": "text",
                "text": f"↓ 所要時間: {travel_time}分",
                "size": "md",
                "color": "#ffffff",
                "align": "center",
                "weight": "bold",
            },
        ],
        "margin": "md",
        "paddingAll": "8px",
    }


def create_realtime_info_box(realtime_info: Dict) -> Dict:
    """
    リアルタイム情報ボックス (Phase 5実装)

    Args:
        realtime_info: {
            "status": "approaching" | "on_time",
            "current_stop": "河原町五条",
            "next_stop": "四条河原町",
            "estimated_arrival_minutes": 2,
            "message": "河原町五条を出発 → 四条河原町に向かっています"
        }
    """
    status = realtime_info.get("status", "on_time")
    estimated_arrival = realtime_info.get("estimated_arrival_minutes", 0)
    message = realtime_info.get("message", "")

    # ステータスバッジ
    if status == "approaching":
        status_text = "🔴 市バス接近中"
        badge_color = "#F39C12"
    else:
        status_text = "✅ 定時運行"
        badge_color = "#27AE60"

    contents = [
        # ステータスバッジ
        {
            "type": "box",
            "layout": "horizontal",
            "contents": [
                {
                    "type": "text",
                    "text": status_text,
                    "size": "sm",
                    "weight": "bold",
                    "color": "#ffffff",
                    "align": "center",
                }
            ],
            "backgroundColor": badge_color,
            "cornerRadius": "12px",
            "paddingAll": "8px",
        },
    ]

    # 位置情報メッセージ
    if message:
        contents.append({
            "type": "text",
            "text": message,
            "size": "xs",
            "color": "#e0e0e0",
            "margin": "xs",
            "wrap": True,
        })

    # 到着予定時間
    if status == "approaching" and estimated_arrival > 0:
        contents.append({
            "type": "text",
            "text": f"あと約 {estimated_arrival} 分で到着予定",
            "size": "xs",
            "color": "#ffffff",
            "margin": "xs",
            "weight": "bold",
        })

    return {
        "type": "box",
        "layout": "vertical",
        "contents": contents,
        "margin": "md",
        "backgroundColor": "#2c2c2c",
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
                "text": "※表示時刻は目安です。最新情報はバス会社サイトでご確認ください。",
                "size": "xs",
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
