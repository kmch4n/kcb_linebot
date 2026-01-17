import re
from typing import Optional, Dict


def contains_japanese(text: str) -> bool:
    """
    文字列に日本語（ひらがな、カタカナ、漢字）が含まれているか判定

    Args:
        text: 判定対象の文字列

    Returns:
        日本語が含まれている場合True
    """
    return bool(re.search(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]', text))


def parse_bus_search_message(text: str) -> Optional[Dict[str, str]]:
    """
    ユーザーメッセージから出発地・目的地を抽出

    対応パターン:
    1. "四条河原町から京都駅" または "四条河原町から京都駅まで"
    2. "四条河原町→京都駅"
    3. "四条河原町 京都駅" (スペース区切り、各2文字以上)
    4. "四条河原町" (出発地のみ、2文字以上、日本語含む)

    Args:
        text: ユーザーのメッセージ

    Returns:
        {"from_stop": "出発地", "to_stop": "目的地"} の辞書
        目的地がない場合は {"from_stop": "出発地"} のみ
        パターンに一致しない場合は None
    """
    text = text.strip()

    # パターン1: "AからB" または "AからBまで"
    match = re.match(r"^(.+?)から(.+?)(?:まで)?$", text)
    if match:
        from_stop = match.group(1).strip()
        to_stop = match.group(2).strip()
        if from_stop and to_stop:
            return {"from_stop": from_stop, "to_stop": to_stop}

    # パターン2: "A→B"
    match = re.match(r"^(.+?)→(.+?)$", text)
    if match:
        from_stop = match.group(1).strip()
        to_stop = match.group(2).strip()
        if from_stop and to_stop:
            return {"from_stop": from_stop, "to_stop": to_stop}

    # パターン3: "A B" (スペース区切り、各2文字以上)
    match = re.match(r"^(.{2,})\s+(.{2,})$", text)
    if match:
        from_stop = match.group(1).strip()
        to_stop = match.group(2).strip()
        # 両方が存在し、空白文字のみでないことを確認
        if from_stop and to_stop and not from_stop.isspace() and not to_stop.isspace():
            return {"from_stop": from_stop, "to_stop": to_stop}

    # パターン4: 単一バス停名（2文字以上、日本語含む）
    if len(text) >= 2 and contains_japanese(text):
        return {"from_stop": text}

    # どのパターンにも一致しない
    return None


def is_command_keyword(text: str) -> bool:
    """
    コマンドキーワードかどうか判定

    Args:
        text: 判定対象の文字列

    Returns:
        コマンドキーワードの場合True
    """
    text = text.strip().lower()
    command_keywords = [
        "設定", "せってい",
        "ヘルプ", "へるぷ", "help",
        "使い方", "つかいかた",
        "登録", "とうろく",
        "一覧", "いちらん",
        "削除", "さくじょ",
        "キャンセル", "きゃんせる", "やめる"
    ]
    return text in command_keywords


def is_help_command(text: str) -> bool:
    """
    ヘルプコマンドかどうか判定

    Args:
        text: 判定対象の文字列

    Returns:
        ヘルプコマンドの場合True
    """
    text = text.strip().lower()
    help_keywords = [
        "ヘルプ", "へるぷ", "help",
        "使い方", "つかいかた"
    ]
    return text in help_keywords


def is_setting_command(text: str) -> bool:
    """
    設定コマンドかどうか判定

    Args:
        text: 判定対象の文字列

    Returns:
        設定コマンドの場合True
    """
    text = text.strip().lower()
    setting_keywords = [
        "設定", "せってい"
    ]
    return text in setting_keywords


def is_cancel_command(text: str) -> bool:
    """
    キャンセルコマンドかどうか判定

    Args:
        text: 判定対象の文字列

    Returns:
        キャンセルコマンドの場合True
    """
    text = text.strip().lower()
    cancel_keywords = [
        "キャンセル", "きゃんせる", "やめる"
    ]
    return text in cancel_keywords


def is_favorite_command(text: str) -> bool:
    """
    お気に入りコマンドかどうか判定

    Args:
        text: 判定対象の文字列

    Returns:
        お気に入りコマンドの場合True
    """
    text = text.strip()
    favorite_keywords = [
        "お気に入り", "おきにいり",
    ]
    return any(text.startswith(kw) for kw in favorite_keywords)


def parse_favorite_command(text: str) -> Optional[Dict[str, str]]:
    """
    お気に入りコマンドを解析

    対応パターン:
    1. "お気に入り登録 四条河原町 京都駅" -> {"action": "add", "from_stop": "...", "to_stop": "..."}
    2. "お気に入り一覧" -> {"action": "list"}
    3. "お気に入り削除 四条河原町 京都駅" -> {"action": "remove", "from_stop": "...", "to_stop": "..."}
    4. "お気に入り削除 1" -> {"action": "remove_by_index", "index": 1}

    Args:
        text: ユーザーのメッセージ

    Returns:
        解析結果の辞書、またはNone
    """
    text = text.strip()

    # パターン1: "お気に入り登録 出発地 目的地"
    match = re.match(r"^(?:お気に入り登録|おきにいり登録)\s+(.+?)\s+(.+?)$", text)
    if match:
        return {
            "action": "add",
            "from_stop": match.group(1).strip(),
            "to_stop": match.group(2).strip()
        }

    # パターン2: "お気に入り一覧"
    if text in ["お気に入り一覧", "おきにいり一覧", "お気に入り", "おきにいり"]:
        return {"action": "list"}

    # パターン3: "お気に入り削除 出発地 目的地"
    match = re.match(r"^(?:お気に入り削除|おきにいり削除)\s+(.+?)\s+(.+?)$", text)
    if match:
        return {
            "action": "remove",
            "from_stop": match.group(1).strip(),
            "to_stop": match.group(2).strip()
        }

    # パターン4: "お気に入り削除 番号"
    match = re.match(r"^(?:お気に入り削除|おきにいり削除)\s+(\d+)$", text)
    if match:
        return {
            "action": "remove_by_index",
            "index": int(match.group(1))
        }

    return None
