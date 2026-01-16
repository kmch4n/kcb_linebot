import logging
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
)
from storage import add_search_history, get_top_searches
from session import (
    get_user_session,
    start_waiting_for_destination_session,
    clear_user_session,
    increment_fail_count,
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

    # 1. セッション処理（目的地入力待ち）
    session = get_user_session(user_id)
    if session and session.get("state") == "waiting_for_destination":
        handle_destination_input(event, session)
        return

    # 2. ヘルプコマンド
    if is_help_command(user_message):
        send_help_message(event)
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

    # 4. デフォルト: オウム返し
    reply_text = f"あなたのメッセージ: {user_message}"
    send_text_reply(event, reply_text)


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

        # ラベル: "バス停名 (距離m)"
        label = f"{stop_name} ({int(distance)}m)"

        # 送信テキスト: バス停名のみ
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
        from datetime import datetime

        # ユーザーIDを取得
        user_id = event.source.user_id

        # 検索履歴を保存
        add_search_history(user_id, from_stop, to_stop)

        day_type = get_day_type()
        routes = search_routes(from_stop, to_stop, day_type=day_type)

        logger.info(f"[DEBUG] Search routes returned {len(routes) if routes else 0} results")

        # 終バス判定: 結果が0件、または最初のバスが2時間以上先の場合
        is_last_bus_passed = False

        if not routes or len(routes) == 0:
            # 結果が0件の場合、終バス後の可能性があるため翌日始バスを検索
            # 現在時刻が21時以降または深夜5時以前の場合、始バスを検索
            now = datetime.now()
            current_hour = now.hour

            if current_hour >= 21 or current_hour < 5:
                logger.info(f"No routes found at {now.strftime('%H:%M')}. Searching for first bus...")

                # 翌日の始バスを検索（05:00から検索）
                routes = search_routes(from_stop, to_stop, day_type=day_type, current_time="05:00")

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
                now = datetime.now()
                dep_time = datetime.strptime(first_departure_time, "%H:%M:%S")
                dep_datetime = now.replace(hour=dep_time.hour, minute=dep_time.minute, second=0)

                minutes_until_departure = int((dep_datetime - now).total_seconds() / 60)

                # 出発時刻が30分以上過去の場合、翌日と見なす
                # （数秒～数分の誤差では翌日扱いにしない）
                if minutes_until_departure < -30:
                    from datetime import timedelta
                    dep_datetime += timedelta(days=1)
                    minutes_until_departure = int((dep_datetime - now).total_seconds() / 60)

                # 2時間（120分）以上先の場合は終バス後と判定
                if minutes_until_departure > 120:
                    is_last_bus_passed = True
                    logger.info(f"Last bus has passed. Next bus in {minutes_until_departure} minutes")
            except:
                pass  # 時刻解析エラーは無視

        # Phase 5: 各ルートのリアルタイム情報を取得
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
                flex_contents
            )
        else:
            send_flex_reply(event, "バス検索結果", flex_contents, user_id)

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
    # Phase 1: シンプルなテキスト返信
    # Phase 2: Quick Replyでお気に入り表示を追加予定
    quick_reply_items = [
        QuickReplyItem(action=MessageAction(label="キャンセル", text="キャンセル"))
    ]
    quick_reply = QuickReply(items=quick_reply_items)

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
        "※現在時刻をもとに検索します。"
    )
    send_text_reply(event, help_text)


# ============================================================================
# 返信ヘルパー関数
# ============================================================================


def send_text_reply(event, text: str, quick_reply=None):
    """
    テキストメッセージを返信

    Args:
        event: LINE Webhookイベント
        text: 返信テキスト
        quick_reply: QuickReplyオブジェクト（オプション）
    """
    try:
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            message = TextMessage(text=text)
            if quick_reply:
                message.quick_reply = quick_reply

            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[message]
                )
            )
        logger.info(f"Replied to {event.source.user_id}")
    except Exception as e:
        logger.error(f"Failed to reply: {e}")


def send_flex_reply(event, alt_text: str, contents: dict, user_id: str = None):
    """
    Flex Messageを返信（トップ3検索のQuickReply付き）

    Args:
        event: LINE Webhookイベント
        alt_text: 代替テキスト
        contents: Flex Messageの内容（辞書形式）
        user_id: ユーザーID（QuickReply用）
    """
    try:
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            flex_message = FlexMessage(
                alt_text=alt_text,
                contents=FlexContainer.from_dict(contents)
            )

            # トップ3検索のQuickReplyを作成
            if user_id:
                quick_reply = create_top_searches_quick_reply(user_id)
                if quick_reply:
                    flex_message.quick_reply = quick_reply

            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[flex_message]
                )
            )
        logger.info(f"Replied Flex to {event.source.user_id}")
    except Exception as e:
        logger.error(f"Failed to reply Flex: {e}")


def send_text_and_flex_reply(event, text: str, alt_text: str, flex_contents: dict):
    """
    テキストメッセージとFlex Messageを同時に返信

    Args:
        event: LINE Webhookイベント
        text: テキストメッセージ
        alt_text: Flex Messageの代替テキスト
        flex_contents: Flex Messageの内容（辞書形式）
    """
    try:
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            text_message = TextMessage(text=text)
            flex_message = FlexMessage(
                alt_text=alt_text,
                contents=FlexContainer.from_dict(flex_contents)
            )
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[text_message, flex_message]
                )
            )
        logger.info(f"Replied Text+Flex to {event.source.user_id}")
    except Exception as e:
        logger.error(f"Failed to reply Text+Flex: {e}")


def create_top_searches_quick_reply(user_id: str) -> QuickReply:
    """
    トップ3検索履歴のQuickReplyを作成

    Args:
        user_id: ユーザーID

    Returns:
        QuickReply object（履歴がない場合はNone）
    """
    top_searches = get_top_searches(user_id, limit=3)

    if not top_searches:
        return None

    items = []
    for search in top_searches:
        from_stop = search.get("from_stop", "")
        to_stop = search.get("to_stop", "")
        count = search.get("count", 0)

        # ラベル: "出発地→目的地 (回数)"
        label = f"{from_stop}→{to_stop}"
        if len(label) > 18:
            # 長すぎる場合は短縮
            label = f"{from_stop[:7]}→{to_stop[:7]}"

        # 送信テキスト: "出発地 目的地"
        text = f"{from_stop} {to_stop}"

        items.append(
            QuickReplyItem(
                action=MessageAction(
                    label=label,
                    text=text
                )
            )
        )

    return QuickReply(items=items) if items else None
