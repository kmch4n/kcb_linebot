import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# タイムゾーン設定（日本標準時）
JST = ZoneInfo("Asia/Tokyo")

from linebot.v3.messaging import (
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
    QuickReply,
    QuickReplyItem,
    MessageAction,
    FlexMessage,
    FlexContainer,
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent, LocationMessageContent

from config import handler, configuration

# ローカルモジュール
from bus_api import (
    search_routes,
    get_day_type,
    search_nearby_stops,
    get_trip_location,
    convert_location_to_realtime_info,
    validate_stop_exists,
    BusAPIError
)
from message_parser import (
    parse_bus_search_message,
    is_help_command,
    is_cancel_command,
    is_favorite_command,
    is_favorite_register_only_command,
    is_nearby_stops_command,
    is_timetable_command,
    is_data_attribution_command,
    parse_favorite_command,
)
from storage import (
    add_search_history,
    add_favorite,
    remove_favorite,
    get_favorites,
    is_favorite,
    MAX_FAVORITES,
)
from session import (
    get_user_session,
    start_waiting_for_destination_session,
    start_waiting_for_favorite_route_session,
    clear_user_session,
    increment_fail_count,
    update_session_timestamp,
    MAX_FAIL_COUNT,
)
from flex_templates import create_bus_routes_flex

logger = logging.getLogger(__name__)


# ============================================================================
# メッセージハンドラー
# ============================================================================


@handler.add(MessageEvent, message=TextMessageContent)
def handle_text_message(event):
    """テキストメッセージの処理"""
    user_message = event.message.text
    user_id = event.source.user_id

    logger.info(f"Received message from {user_id}: {user_message}")

    # 1. セッション処理
    session = get_user_session(user_id)
    if session:
        state = session.get("state")
        if state == "waiting_for_destination":
            handle_destination_input(event, session)
            return
        elif state == "waiting_for_favorite_route":
            handle_favorite_route_input(event, session)
            return

    # 2. ヘルプコマンド
    if is_help_command(user_message):
        send_help_message(event)
        return

    # 2.5. キャンセルコマンド（セッション外）
    if is_cancel_command(user_message):
        send_text_reply(event, "キャンセルしました。")
        return

    # 2.6. お気に入り登録のみ（ルートなし）
    if is_favorite_register_only_command(user_message):
        start_waiting_for_favorite_route_session(user_id)
        # キャンセルボタンのみのQuick Reply
        cancel_quick_reply = QuickReply(items=[
            QuickReplyItem(action=MessageAction(label="キャンセル", text="キャンセル"))
        ])
        send_text_reply(
            event,
            "⭐ お気に入りルートに登録します。\n\n"
            "登録したいルートを送信してください。\n"
            "例: 「四条河原町 京都駅」\n\n"
            "（キャンセルする場合は「キャンセル」と入力）",
            quick_reply=cancel_quick_reply
        )
        return

    # 2.7. 周辺バス停検索コマンド
    if is_nearby_stops_command(user_message):
        send_nearby_stops_prompt(event)
        return

    # 2.8. 時刻表検索コマンド
    if is_timetable_command(user_message):
        send_timetable_not_implemented(event)
        return

    # 2.9. データについてコマンド
    if is_data_attribution_command(user_message):
        send_data_attribution(event)
        return

    # 2.10. お気に入りコマンド（ルート付き）
    if is_favorite_command(user_message):
        parsed_fav = parse_favorite_command(user_message)
        if parsed_fav:
            handle_favorite_command(event, parsed_fav)
            return
        else:
            # 不完全なお気に入りコマンドに対するエラーメッセージ
            send_text_reply(
                event,
                "⚠️ コマンドの形式が正しくありません。\n\n"
                "【使用例】\n"
                "• お気に入り一覧\n"
                "• お気に入り登録 出発地 目的地\n"
                "• お気に入り削除 番号"
            )
            return

    # 3. バス検索処理
    parsed = parse_bus_search_message(user_message)

    if parsed:
        from_stop = parsed.get("from_stop")
        to_stop = parsed.get("to_stop")

        if from_stop and to_stop:
            # 完全な入力 → 即座に検索
            execute_bus_search(event, from_stop, to_stop)
            return
        elif from_stop:
            # 部分的な入力 → バス停の存在を確認してからセッション開始
            try:
                if not validate_stop_exists(from_stop):
                    send_text_reply(event, f"⚠️ 停留所「{from_stop}」が見つかりません。\n\n正しいバス停名を入力してください。")
                    return
            except BusAPIError as e:
                logger.error(f"Error validating stop: {e}")
                send_text_reply(event, f"⚠️ {str(e)}")
                return

            # バス停が存在する場合、セッション開始
            start_waiting_for_destination_session(user_id, from_stop)
            send_destination_prompt(event, user_id)
            return

    # 4. デフォルト: 理解できなかったメッセージ
    send_text_reply(
        event,
        "すみません、入力内容を理解できませんでした。\n\n"
        "バス検索は「出発地 目的地」の形式で入力してください。\n"
        "例: 「四条河原町 京都駅」"
    )


@handler.add(MessageEvent, message=LocationMessageContent)
def handle_location_message(event):
    """
    位置情報メッセージの処理

    位置情報から周辺のバス停を検索し、Quick Replyで選択肢を表示
    """
    user_id = event.source.user_id
    latitude = event.message.latitude
    longitude = event.message.longitude
    title = event.message.title  # Optional
    address = event.message.address  # Optional

    logger.info(f"Received location from {user_id}: "
                f"lat={latitude}, lng={longitude}, "
                f"title={title}, address={address}")

    try:
        # 周辺500m以内のバス停を最大5件検索
        nearby_stops = search_nearby_stops(latitude, longitude, radius=500, limit=5)

        if not nearby_stops:
            send_text_reply(
                event,
                "📍 周辺にバス停が見つかりませんでした。\n\n"
                "別の場所を試すか、バス停名を直接入力してください。"
            )
            return

        # Quick Replyで近くのバス停を表示
        quick_reply = create_nearby_stops_quick_reply(nearby_stops)

        location_info = f"場所: {title}\n" if title else ""
        send_text_reply(
            event,
            f"📍 位置情報を受け取りました。\n{location_info}\n"
            f"近くのバス停が {len(nearby_stops)} 件見つかりました。\n"
            f"出発するバス停を選択してください。",
            quick_reply=quick_reply
        )

    except BusAPIError as e:
        logger.error(f"Bus API error in location handler: {e}")
        send_text_reply(event, f"⚠️ {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error in handle_location_message: {e}")
        send_text_reply(event, "⚠️ エラーが発生しました。もう一度お試しください。")


def truncate_quick_reply_label(text: str, max_length: int = 20) -> str:
    """
    Quick Replyラベルを指定長に切り詰める

    Args:
        text: 元のラベルテキスト
        max_length: 最大文字数（デフォルト: 20、LINE Quick Reply制限）

    Returns:
        切り詰められたラベル
    """
    if len(text) <= max_length:
        return text
    return text[:max_length - 1] + "…"


def create_nearby_stops_quick_reply(stops: list, max_items: int = 5) -> QuickReply:
    """
    周辺バス停情報からQuick Replyを生成

    Args:
        stops: search_nearby_stops()から取得したバス停情報リスト
               [{"stop_name": str, "distance_meters": float}, ...]
        max_items: 最大表示数（デフォルト: 5）

    Returns:
        QuickReply object
    """
    items = []

    # バス停ボタン（最大5個）
    for stop in stops[:max_items]:
        stop_name = stop.get("stop_name", "不明")
        distance = stop.get("distance_meters", 0)

        # ラベル: "バス停名 (距離m)" - 20文字制限に対応
        distance_str = f"({int(distance)}m)"
        max_name_len = 20 - len(distance_str) - 1  # スペース分を引く
        if len(stop_name) > max_name_len:
            stop_name_display = stop_name[:max_name_len - 1] + "…"
        else:
            stop_name_display = stop_name
        label = f"{stop_name_display} {distance_str}"

        # 送信テキスト: バス停名のみ（切り詰めない）
        # （距離情報は表示用で、検索には不要）
        text = stop_name

        items.append(
            QuickReplyItem(
                action=MessageAction(
                    label=label,
                    text=text
                )
            )
        )

    # キャンセルボタン
    items.append(
        QuickReplyItem(action=MessageAction(label="キャンセル", text="キャンセル"))
    )

    return QuickReply(items=items)


# ============================================================================
# バス検索関連
# ============================================================================


def execute_bus_search(event, from_stop: str, to_stop: str):
    """
    バス検索を実行して結果を返信

    Args:
        event: LINE Webhookイベント
        from_stop: 出発地バス停名
        to_stop: 目的地バス停名
    """
    try:
        # ユーザーIDを取得
        user_id = event.source.user_id

        day_type = get_day_type()
        routes = search_routes(from_stop, to_stop, day_type=day_type)

        # 検索成功時のみ履歴保存（API呼び出し成功後）
        if routes:
            add_search_history(user_id, from_stop, to_stop)

        logger.info(f"[DEBUG] Search routes returned {len(routes) if routes else 0} results")

        # 終バス判定: 結果が0件、または最初のバスが2時間以上先の場合
        is_last_bus_passed = False

        if not routes or len(routes) == 0:
            # 結果が0件の場合、終バス後の可能性があるため翌日始バスを検索
            # 現在時刻が21時以降または深夜5時以前の場合、始バスを検索
            now = datetime.now(JST)
            current_hour = now.hour

            if current_hour >= 21 or current_hour < 5:
                logger.info(f"No routes found at {now.strftime('%H:%M')}. Searching for first bus...")

                # 翌日の日付とday_typeを計算
                tomorrow = now + timedelta(days=1)
                tomorrow_day_type = get_day_type(tomorrow)

                # 翌日の始バスを検索（05:00から検索）
                routes = search_routes(from_stop, to_stop, day_type=tomorrow_day_type, current_time="05:00")

                # 始バス検索でも結果がない場合は、真に経路が存在しない
                if routes and len(routes) > 0:
                    is_last_bus_passed = True
                else:
                    logger.info("No routes found even for first bus. Route may not exist.")
                    is_last_bus_passed = False

        elif routes and len(routes) > 0:
            # 結果がある場合、最初のバスの出発時刻をチェック
            first_departure_time = routes[0].get("departure_time", "")
            try:
                now = datetime.now(JST)
                dep_time = datetime.strptime(first_departure_time, "%H:%M:%S")
                dep_datetime = now.replace(hour=dep_time.hour, minute=dep_time.minute, second=0)

                minutes_until_departure = int((dep_datetime - now).total_seconds() / 60)

                # 出発時刻が30分以上過去の場合、翌日と見なす
                # （数秒～数分の誤差では翌日扱いにしない）
                if minutes_until_departure < -30:
                    dep_datetime += timedelta(days=1)
                    minutes_until_departure = int((dep_datetime - now).total_seconds() / 60)

                # 2時間（120分）以上先かつ夜間時間帯の場合のみ終バス後と判定
                # （日中に2時間以上先のバスがある場合は終バス扱いしない）
                current_hour = now.hour
                is_night_time = current_hour >= 21 or current_hour < 5
                if minutes_until_departure > 120 and is_night_time:
                    is_last_bus_passed = True
                    logger.info(f"Last bus has passed. Next bus in {minutes_until_departure} minutes")
            except:
                pass  # 時刻解析エラーは無視

        # Phase 5: 各ルートのリアルタイム情報を取得
        # routesがNoneの場合は空リストに正規化（Bug #1修正）
        routes = routes or []
        for route in routes:
            trip_id = route.get("trip_id")
            departure_stop_id = route.get("departure_stop_id")
            if trip_id:
                # バスの現在位置を取得（時刻表ベース）
                location_data = get_trip_location(trip_id, departure_stop_id=departure_stop_id)

                # Flex Message用のrealtime_info形式に変換
                realtime_info = convert_location_to_realtime_info(location_data, route)

                # ルート情報にrealtime_infoを追加
                if realtime_info:
                    route["realtime_info"] = realtime_info
                    logger.info(f"Added realtime info for trip {trip_id}: {realtime_info.get('status')}")

        # Phase 3: Flex Message返信
        flex_contents = create_bus_routes_flex(routes, from_stop, to_stop)

        # 終バス後の場合、テキストメッセージと一緒に返信
        if is_last_bus_passed:
            send_text_and_flex_reply(
                event,
                "🌙 本日のバス運行は終了しています。\n翌日の始バスをご案内します。",
                "バス検索結果",
                flex_contents,
                from_stop=from_stop,
                to_stop=to_stop
            )
        else:
            send_flex_reply(event, "バス検索結果", flex_contents, user_id,
                           from_stop=from_stop, to_stop=to_stop)

    except BusAPIError as e:
        logger.error(f"Bus API error: {e}")
        send_text_reply(event, f"⚠️ {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error in execute_bus_search: {e}")
        send_text_reply(event, "⚠️ エラーが発生しました。もう一度お試しください。")


def format_routes_as_text(routes: list, from_stop: str, to_stop: str) -> str:
    """
    路線情報をテキスト形式にフォーマット

    Args:
        routes: 路線情報のリスト
        from_stop: 出発地バス停名
        to_stop: 目的地バス停名

    Returns:
        フォーマットされたテキスト
    """
    lines = [f"🚌 {from_stop} → {to_stop}\n"]

    for i, route in enumerate(routes[:3], 1):
        route_name = route.get("route_name", "不明")
        dep_time = format_time(route.get("departure_time", ""))
        arr_time = format_time(route.get("arrival_time", ""))
        travel_time = route.get("travel_time_minutes", 0)
        dep_stop_desc = route.get("departure_stop_desc", from_stop)
        arr_stop_desc = route.get("arrival_stop_desc", to_stop)

        lines.append(f"{i}. {route_name}")
        lines.append(f"   出発: {dep_time} ({dep_stop_desc})")
        lines.append(f"   到着: {arr_time} ({arr_stop_desc})")
        lines.append(f"   所要時間: {travel_time}分")
        if i < len(routes[:3]):
            lines.append("")

    return "\n".join(lines)


def format_time(time_str: str) -> str:
    """
    時刻フォーマット HH:MM:SS → HH:MM

    Args:
        time_str: 時刻文字列（HH:MM:SS形式）

    Returns:
        フォーマットされた時刻（HH:MM形式）
    """
    if not time_str:
        return "不明"

    parts = time_str.split(":")
    if len(parts) >= 2:
        return f"{parts[0]}:{parts[1]}"
    return time_str


def handle_destination_input(event, session: dict):
    """
    目的地入力を処理

    Args:
        event: LINE Webhookイベント
        session: ユーザーセッション情報
    """
    user_id = event.source.user_id
    user_message = event.message.text

    # セッションタイムスタンプを更新（タイムアウト防止）
    update_session_timestamp(user_id)

    # キャンセルコマンド
    if is_cancel_command(user_message):
        clear_user_session(user_id)
        send_text_reply(event, "キャンセルしました。")
        return

    # 目的地として解析
    origin_stop = session.get("origin_stop")
    destination_stop = user_message.strip()

    # 空の入力チェック
    if not destination_stop:
        fail_count = increment_fail_count(user_id)
        if fail_count >= MAX_FAIL_COUNT:
            clear_user_session(user_id)
            send_help_message(event)
            return

        send_text_reply(event, "目的地のバス停名を入力してください。\n（キャンセルする場合は「キャンセル」と入力）")
        return

    # 目的地バス停の存在を確認
    try:
        if not validate_stop_exists(destination_stop):
            fail_count = increment_fail_count(user_id)
            if fail_count >= MAX_FAIL_COUNT:
                clear_user_session(user_id)
                send_text_reply(event, f"⚠️ 停留所「{destination_stop}」が見つかりません。\n\n検索を中止しました。最初からやり直してください。")
                return

            send_text_reply(event, f"⚠️ 停留所「{destination_stop}」が見つかりません。\n\n正しいバス停名を入力してください。")
            return
    except BusAPIError as e:
        logger.error(f"Error validating destination stop: {e}")
        send_text_reply(event, f"⚠️ {str(e)}")
        return

    # セッションクリアして検索実行
    clear_user_session(user_id)
    execute_bus_search(event, origin_stop, destination_stop)


def send_destination_prompt(event, user_id: str):
    """
    目的地入力を促す

    Args:
        event: LINE Webhookイベント
        user_id: LINEユーザーID
    """
    # ヘルプ + お気に入り + キャンセルのQuickReply
    quick_reply = create_default_quick_reply(user_id, include_cancel=True)

    send_text_reply(
        event,
        "どこまで行きますか？\nバス停名を入力してください。",
        quick_reply=quick_reply
    )


def send_help_message(event):
    """
    ヘルプメッセージを送信

    Args:
        event: LINE Webhookイベント
    """
    help_text = (
        "🚌 京都市バス検索Bot\n\n"
        "【使い方】\n"
        "出発地と目的地をスペースで区切って入力してください。\n\n"
        "例:\n"
        "• 四条河原町 京都駅\n"
        "• 四条河原町から京都駅\n"
        "• 四条河原町→京都駅\n\n"
        "出発地だけを入力すると、目的地を聞かれます。\n\n"
        "【位置情報から検索】\n"
        "📍 位置情報を送信すると、周辺のバス停から選択できます。\n"
        "「周辺バス停」と入力しても案内が表示されます。\n\n"
        "【お気に入り機能】\n"
        "• お気に入り一覧\n"
        "• お気に入り登録 出発地 目的地\n"
        "• お気に入り削除 番号\n\n"
        "※現在時刻をもとに検索します。"
    )

    # ヘルプ専用のQuick Reply（機能ボタン）
    help_quick_reply = QuickReply(items=[
        QuickReplyItem(action=MessageAction(label="⭐ お気に入り登録", text="お気に入り登録")),
        QuickReplyItem(action=MessageAction(label="📍 周辺バス停", text="周辺バス停")),
        QuickReplyItem(action=MessageAction(label="🕐 時刻表", text="時刻表")),
        QuickReplyItem(action=MessageAction(label="ℹ️ データについて", text="データについて")),
    ])

    send_text_reply(event, help_text, quick_reply=help_quick_reply)


def send_data_attribution(event):
    """
    公共交通オープンデータの出典・利用規約情報を送信

    Args:
        event: LINE Webhookイベント
    """
    text = (
        "📋 データについて\n\n"
        "本botが利用する公共交通データは、公共交通オープンデータセンター"
        "において提供されるものです。\n\n"
        "公共交通事業者により提供されたデータを元にしていますが、"
        "必ずしも正確・完全なものとは限りません。\n\n"
        "本botの表示内容について、公共交通事業者への"
        "直接のお問い合わせはご遠慮ください。\n\n"
        "本botに関するお問い合わせ:\n"
        "kmhcna@kmchan.jp"
    )
    send_text_reply(event, text)


def send_nearby_stops_prompt(event):
    """
    位置情報送信を促すメッセージを送信

    Args:
        event: LINE Webhookイベント
    """
    send_text_reply(
        event,
        "📍 周辺のバス停を検索します。\n\n"
        "LINEの「+」ボタンから「位置情報」を選択して、現在地を送信してください。"
    )


def send_timetable_not_implemented(event):
    """
    時刻表検索の未実装メッセージを送信

    Args:
        event: LINE Webhookイベント
    """
    send_text_reply(
        event,
        "⚠️ この機能はまだ作成していません。\n\n"
        "今後のアップデートをお待ちください。"
    )


# ============================================================================
# お気に入り機能
# ============================================================================


def handle_favorite_route_input(event, session: dict):
    """
    お気に入りルート入力を処理（waiting_for_favorite_route状態）

    Args:
        event: LINE Webhookイベント
        session: ユーザーセッション情報
    """
    user_id = event.source.user_id
    user_message = event.message.text

    # セッションタイムスタンプを更新（タイムアウト防止）
    update_session_timestamp(user_id)

    # キャンセルコマンド
    if is_cancel_command(user_message):
        clear_user_session(user_id)
        send_text_reply(event, "キャンセルしました。")
        return

    # ルートとして解析
    parsed = parse_bus_search_message(user_message)

    # キャンセルボタンのみのQuick Reply（セッション継続中用）
    cancel_qr = QuickReply(items=[
        QuickReplyItem(action=MessageAction(label="キャンセル", text="キャンセル"))
    ])

    if not parsed:
        fail_count = increment_fail_count(user_id)
        if fail_count >= MAX_FAIL_COUNT:
            clear_user_session(user_id)
            send_text_reply(event, "入力形式が正しくありません。最初からやり直してください。")
            return
        send_text_reply(
            event,
            "⚠️ 入力形式が正しくありません。\n\n"
            "例: 「四条河原町 京都駅」\n"
            "（キャンセルする場合は「キャンセル」と入力）",
            quick_reply=cancel_qr
        )
        return

    from_stop = parsed.get("from_stop")
    to_stop = parsed.get("to_stop")

    # 出発地のみの場合
    if not to_stop:
        fail_count = increment_fail_count(user_id)
        if fail_count >= MAX_FAIL_COUNT:
            clear_user_session(user_id)
            send_text_reply(event, "入力形式が正しくありません。最初からやり直してください。")
            return
        send_text_reply(
            event,
            "⚠️ 出発地と目的地の両方を入力してください。\n\n"
            "例: 「四条河原町 京都駅」\n"
            "（キャンセルする場合は「キャンセル」と入力）",
            quick_reply=cancel_qr
        )
        return

    # バス停の存在確認
    try:
        if not validate_stop_exists(from_stop):
            send_text_reply(event, f"⚠️ 停留所「{from_stop}」が見つかりません。", quick_reply=cancel_qr)
            return
        if not validate_stop_exists(to_stop):
            send_text_reply(event, f"⚠️ 停留所「{to_stop}」が見つかりません。", quick_reply=cancel_qr)
            return
    except BusAPIError as e:
        send_text_reply(event, f"⚠️ {str(e)}", quick_reply=cancel_qr)
        return

    # セッションクリア
    clear_user_session(user_id)

    # お気に入り追加
    success = add_favorite(user_id, from_stop, to_stop)
    if success:
        send_text_reply(
            event,
            f"⭐ お気に入りに登録しました！\n\n{from_stop} → {to_stop}"
        )
    else:
        if is_favorite(user_id, from_stop, to_stop):
            send_text_reply(
                event,
                f"⚠️ すでにお気に入りに登録されています。\n\n{from_stop} → {to_stop}"
            )
        else:
            send_text_reply(
                event,
                f"⚠️ お気に入りは最大{MAX_FAVORITES}件までです。\n\n"
                "不要なお気に入りを削除してから登録してください。"
            )


def handle_favorite_command(event, parsed_command: dict):
    """
    お気に入りコマンドを処理

    Args:
        event: LINE Webhookイベント
        parsed_command: parse_favorite_command()の結果
    """
    user_id = event.source.user_id
    action = parsed_command.get("action")

    if action == "list":
        # お気に入り一覧表示
        favorites = get_favorites(user_id)
        if not favorites:
            send_text_reply(
                event,
                "⭐ お気に入りはまだ登録されていません。\n\n"
                "登録方法:\n「お気に入り登録 出発地 目的地」"
            )
            return

        lines = ["⭐ お気に入り一覧\n"]
        for i, fav in enumerate(favorites, 1):
            lines.append(f"{i}. {fav['from_stop']} → {fav['to_stop']}")
        lines.append(f"\n({len(favorites)}/{MAX_FAVORITES}件)")
        lines.append("\n削除: 「お気に入り削除 番号」")

        # Quick Replyでお気に入り検索を提供
        quick_reply = create_favorites_quick_reply(favorites)
        send_text_reply(event, "\n".join(lines), quick_reply=quick_reply)

    elif action == "add":
        from_stop = parsed_command.get("from_stop")
        to_stop = parsed_command.get("to_stop")

        # バス停の存在を確認
        try:
            if not validate_stop_exists(from_stop):
                send_text_reply(event, f"⚠️ 停留所「{from_stop}」が見つかりません。")
                return
            if not validate_stop_exists(to_stop):
                send_text_reply(event, f"⚠️ 停留所「{to_stop}」が見つかりません。")
                return
        except BusAPIError as e:
            send_text_reply(event, f"⚠️ {str(e)}")
            return

        # お気に入り追加
        success = add_favorite(user_id, from_stop, to_stop)
        if success:
            send_text_reply(
                event,
                f"⭐ お気に入りに登録しました！\n\n{from_stop} → {to_stop}"
            )
        else:
            # 上限か重複かを判定
            if is_favorite(user_id, from_stop, to_stop):
                send_text_reply(
                    event,
                    f"⚠️ すでにお気に入りに登録されています。\n\n{from_stop} → {to_stop}"
                )
            else:
                send_text_reply(
                    event,
                    f"⚠️ お気に入りは最大{MAX_FAVORITES}件までです。\n\n"
                    "不要なお気に入りを削除してから登録してください。\n"
                    "「お気に入り一覧」で確認できます。"
                )

    elif action == "remove":
        from_stop = parsed_command.get("from_stop")
        to_stop = parsed_command.get("to_stop")

        success = remove_favorite(user_id, from_stop, to_stop)
        if success:
            send_text_reply(
                event,
                f"⭐ お気に入りから削除しました。\n\n{from_stop} → {to_stop}"
            )
        else:
            send_text_reply(
                event,
                f"⚠️ お気に入りに登録されていません。\n\n{from_stop} → {to_stop}"
            )

    elif action == "remove_by_index":
        index = parsed_command.get("index")
        favorites = get_favorites(user_id)

        if 1 <= index <= len(favorites):
            fav = favorites[index - 1]
            success = remove_favorite(user_id, fav["from_stop"], fav["to_stop"])
            if success:
                send_text_reply(
                    event,
                    f"⭐ お気に入りから削除しました。\n\n{fav['from_stop']} → {fav['to_stop']}"
                )
            else:
                send_text_reply(event, "⚠️ 削除に失敗しました。")
        else:
            send_text_reply(
                event,
                f"⚠️ 番号が正しくありません。1〜{len(favorites)}の番号を指定してください。"
            )


def create_favorites_quick_reply(favorites: list) -> QuickReply:
    """
    お気に入りルートのQuickReplyを作成

    Args:
        favorites: お気に入りルートのリスト

    Returns:
        QuickReply object
    """
    items = []

    for fav in favorites[:5]:
        from_stop = fav.get("from_stop", "")
        to_stop = fav.get("to_stop", "")

        # ラベル: "⭐出発地→目的地"
        label = f"⭐{from_stop}→{to_stop}"
        if len(label) > 18:
            label = f"⭐{from_stop[:6]}→{to_stop[:6]}"

        # 送信テキスト: "出発地 目的地"
        text = f"{from_stop} {to_stop}"

        items.append(
            QuickReplyItem(
                action=MessageAction(label=label, text=text)
            )
        )

    return QuickReply(items=items) if items else None


# ============================================================================
# 返信ヘルパー関数
# ============================================================================


def send_text_reply(event, text: str, quick_reply=None, include_default_qr: bool = True):
    """
    テキストメッセージを返信

    Args:
        event: LINE Webhookイベント
        text: 返信テキスト
        quick_reply: QuickReplyオブジェクト（オプション、指定時は優先）
        include_default_qr: デフォルトQuickReplyを含めるか（デフォルト: True）
    """
    try:
        user_id = event.source.user_id

        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            message = TextMessage(text=text)

            # Quick Replyの設定
            if quick_reply:
                # 明示的に指定された場合はそれを使用
                message.quick_reply = quick_reply
            elif include_default_qr:
                # デフォルトQuickReplyを使用（ヘルプ + お気に入り）
                message.quick_reply = create_default_quick_reply(user_id)

            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[message]
                )
            )
        logger.info(f"Replied to {event.source.user_id}")
    except Exception as e:
        logger.error(f"Failed to reply: {e}")


def send_flex_reply(event, alt_text: str, contents: dict, user_id: str = None,
                    from_stop: str = None, to_stop: str = None):
    """
    Flex Messageを返信（デフォルトQuickReply付き）

    Args:
        event: LINE Webhookイベント
        alt_text: 代替テキスト
        contents: Flex Messageの内容（辞書形式）
        user_id: ユーザーID（QuickReply用）
        from_stop: 出発地（逆方向検索ボタン用）
        to_stop: 目的地（逆方向検索ボタン用）
    """
    try:
        # user_idが渡されていない場合はeventから取得
        if not user_id:
            user_id = event.source.user_id

        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            flex_message = FlexMessage(
                alt_text=alt_text,
                contents=FlexContainer.from_dict(contents)
            )

            # QuickReplyを作成（逆方向検索 + ヘルプ + お気に入り）
            quick_reply_items = []

            # 逆方向検索ボタン（from_stop, to_stopがある場合）
            if from_stop and to_stop:
                quick_reply_items.append(
                    QuickReplyItem(
                        action=MessageAction(
                            label="🔄 逆方向を検索",
                            text=f"{to_stop} {from_stop}"
                        )
                    )
                )

            # デフォルトQuickReplyの項目を追加
            default_qr = create_default_quick_reply(user_id)
            if default_qr and default_qr.items:
                quick_reply_items.extend(default_qr.items)

            flex_message.quick_reply = QuickReply(items=quick_reply_items)

            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[flex_message]
                )
            )
        logger.info(f"Replied Flex to {event.source.user_id}")
    except Exception as e:
        logger.error(f"Failed to reply Flex: {e}")


def send_text_and_flex_reply(event, text: str, alt_text: str, flex_contents: dict,
                             from_stop: str = None, to_stop: str = None):
    """
    テキストメッセージとFlex Messageを同時に返信

    Args:
        event: LINE Webhookイベント
        text: テキストメッセージ
        alt_text: Flex Messageの代替テキスト
        flex_contents: Flex Messageの内容（辞書形式）
        from_stop: 出発地（逆方向検索ボタン用）
        to_stop: 目的地（逆方向検索ボタン用）
    """
    try:
        user_id = event.source.user_id

        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            text_message = TextMessage(text=text)
            flex_message = FlexMessage(
                alt_text=alt_text,
                contents=FlexContainer.from_dict(flex_contents)
            )

            # QuickReplyを作成（逆方向検索 + ヘルプ + お気に入り）
            quick_reply_items = []

            # 逆方向検索ボタン
            if from_stop and to_stop:
                quick_reply_items.append(
                    QuickReplyItem(
                        action=MessageAction(
                            label="🔄 逆方向を検索",
                            text=f"{to_stop} {from_stop}"
                        )
                    )
                )

            # デフォルトQuickReplyの項目を追加
            default_qr = create_default_quick_reply(user_id)
            if default_qr and default_qr.items:
                quick_reply_items.extend(default_qr.items)

            flex_message.quick_reply = QuickReply(items=quick_reply_items)

            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[text_message, flex_message]
                )
            )
        logger.info(f"Replied Text+Flex to {event.source.user_id}")
    except Exception as e:
        logger.error(f"Failed to reply Text+Flex: {e}")


def create_default_quick_reply(user_id: str = None, include_cancel: bool = False) -> QuickReply:
    """
    デフォルトのQuickReplyを作成（ヘルプ + お気に入り）

    Args:
        user_id: ユーザーID（お気に入り表示用）
        include_cancel: キャンセルボタンを含めるか

    Returns:
        QuickReply object
    """
    items = []

    # 1. 使い方ボタン（最優先）
    items.append(
        QuickReplyItem(
            action=MessageAction(label="❓ 使い方", text="使い方")
        )
    )

    # 2. お気に入りを表示（最大4件）
    if user_id:
        favorites = get_favorites(user_id)
        for fav in favorites[:4]:
            from_stop = fav.get("from_stop", "")
            to_stop = fav.get("to_stop", "")

            # ラベル: "⭐出発地→目的地" - 20文字制限に対応
            label = f"⭐{from_stop}→{to_stop}"
            if len(label) > 20:
                # 出発地と目的地を均等に切り詰め
                max_each = (20 - 3) // 2 - 1  # ⭐と→で3文字、…で1文字ずつ
                label = f"⭐{from_stop[:max_each]}…→{to_stop[:max_each]}…"

            text = f"{from_stop} {to_stop}"

            items.append(
                QuickReplyItem(
                    action=MessageAction(label=label, text=text)
                )
            )

    # 3. キャンセルボタン（セッション中など）
    if include_cancel:
        items.append(
            QuickReplyItem(
                action=MessageAction(label="キャンセル", text="キャンセル")
            )
        )

    return QuickReply(items=items)
