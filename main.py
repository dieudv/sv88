import os
import re
import csv
import requests
from datetime import datetime, timedelta, timezone

API_URL = "https://be.sb21.net/api/v2/getEvent?timeRange=today&sportType=1_1&sportId=1&oddsStyle=ma&pinLeague=false"
HEADERS = {
    "accept": "application/json",
    "content-type": "application/json",
    "lng": "vi"
}

os.makedirs("sv88", exist_ok=True)


def sanitize_filename(s):
    return re.sub(r'[\\/*?:"<>|]', "_", s).replace(" ", "_")


def parse_utc_time(iso_string):
    return datetime.strptime(iso_string, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def extract_odds_from_text(text):
    matches = re.findall(r'([\d.]+)\*\d+h|([\d.]+)\*\d+a|([\d.]+)\*\d+d', text)
    home = away = draw = None
    for h, a, d in matches:
        if h:
            home = h
        if a:
            away = a
        if d:
            draw = d
    return home, away, draw


def format_handicap(hd):
    try:
        val = float(hd)
    except:
        return hd

    if val * 4 != int(val * 4):
        return hd  # không đúng format, giữ nguyên

    parts = {
        0.25: "0-0.5",
        0.75: "0.5-1",
        1.25: "1-1.5",
        1.75: "1.5-2",
        2.25: "2-2.5",
        2.75: "2.5-3",
        3.25: "3-3.5",
        3.75: "3.5-4",
        4.25: "4-4.5",
        4.75: "4.5-5",
        5.25: "5-5.5",
        5.75: "5.5-6"
    }

    if val in parts:
        return parts[val]
    return str(val)


def parse_handicap_and_odds_with_side_fixed(odds_list):
    if not odds_list:
        return None, None, None, None
    try:
        text = odds_list[0]
        parts = text.split()
        if len(parts) < 2:
            return None, None, None, None

        raw_float = float(parts[0])
        raw_handicap = format_handicap(raw_float)

        home_odds_match = re.search(r'([-\d.]+)\*\d+h', text)
        away_odds_match = re.search(r'([-\d.]+)\*\d+a', text)
        side = parts[-3] if parts[-3] in ["h", "a"] else None  # lấy 'h' hoặc 'a'

        home_odds = float(home_odds_match.group(1)) if home_odds_match else None
        away_odds = float(away_odds_match.group(1)) if away_odds_match else None

        if side == "h":
            handicap_top = raw_handicap
            handicap_bottom = f"-({raw_handicap})"
        elif side == "a":
            handicap_top = f"-({raw_handicap})"
            handicap_bottom = raw_handicap
        else:
            handicap_top = raw_handicap
            handicap_bottom = f"-({raw_handicap})"

        return handicap_top, home_odds, handicap_bottom, away_odds
    except Exception as e:
        print(f"[parse_handicap_and_odds_with_side_fixed ERROR] {e}")
        return None, None, None, None


def extract_handicap_and_odds(odds_list):
    if not odds_list:
        return None, None, None, None
    try:
        text = odds_list[0]
        parts = text.split()
        handicap_str = parts[0]  # giữ nguyên dạng chuỗi

        home_odds = re.findall(r'([-\d.]+)\*\d+h', text)
        away_odds = re.findall(r'([-\d.]+)\*\d+a', text)
        home = float(home_odds[0]) if home_odds else None
        away = float(away_odds[0]) if away_odds else None

        # đội dưới có kèo âm, biểu diễn là -(handicap)
        under_handicap = f"-({handicap_str})"

        return handicap_str, home, under_handicap, away
    except:
        return None, None, None, None


def get_time_label(match_time_str, match):
    match_time = parse_utc_time(match_time_str)
    now = datetime.now(timezone.utc)
    delta = now - match_time
    minute = match.get("6", 0) // 60000

    if minute <= 0:
        return now.astimezone().strftime("%H:%M")
    elif match.get("11") is True:
        return f"2H {minute}'"
    elif match.get("10") == 4:
        return "Hết H1"
    else:
        return f"1H {minute}'"


def read_last_row(filepath):
    if not os.path.exists(filepath):
        return None
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            rows = list(csv.reader(f))
            return rows[-1] if len(rows) >= 2 else None
    except Exception as e:
        print(f"Error reading file {filepath}: {e}")
        return None


def should_log(new_row, last_row):
    if not last_row:
        return True
    try:
        last_home_odds = float(last_row[2])
        last_away_odds = float(last_row[4])
        new_home_odds = float(new_row[2])
        new_away_odds = float(new_row[4])
        return new_home_odds != last_home_odds or new_away_odds != last_away_odds
    except ValueError:
        # Nếu không chuyển được sang float (ví dụ lỗi định dạng), vẫn ghi
        return True


def normalize_handicap_string(hdc: str) -> str:
    if not hdc:
        return ""

    if "-" in hdc and not hdc.startswith("-") and not hdc.startswith("(-"):
        return f"'{hdc}"

    if hdc.startswith("-(") and hdc.endswith(")"):
        inner = hdc[2:-1]
        if "-" in inner:
            return f"'-(%s)" % inner
        try:
            num = float(inner)
            return str(int(num)) if num.is_integer() else str(num)
        except:
            return f"'-(%s)" % inner

    try:
        num = float(hdc)
        return str(int(num)) if num.is_integer() else str(num)
    except:
        return hdc


response = requests.get(API_URL, headers=HEADERS)
data = response.json()
competitions = data[0] + data[1]

for comp in competitions:
    comp_name = comp.get("1", "Unknown")
    for match in comp.get("2", []):
        if "16" in match or match.get("17", False):
            continue

        match_time_utc = parse_utc_time(match.get("0", ""))
        now_utc = datetime.now(timezone.utc)

        # Bỏ qua nếu trận chưa diễn ra và còn hơn 6 tiếng mới bắt đầu
        if match_time_utc - now_utc > timedelta(hours=6):
            continue

        home = match.get("2", "home")
        away = match.get("3", "away")

        local_time_str = match_time_utc.astimezone().strftime("%Y%m%d_%H%M")
        filename = sanitize_filename(f"{local_time_str}_{comp_name} - {home} vs {away}.csv")
        filepath = os.path.join("sv88", filename)

        time_label = get_time_label(match.get("0"), match)
        score = match.get("4", {})
        score_str = f"{score.get('0', 0)} - {score.get('1', 0)}"

        odds = match.get("7", {})

        hc = parse_handicap_and_odds_with_side_fixed(odds.get("5", []))
        ou = parse_handicap_and_odds_with_side_fixed(odds.get("3", []))
        _1x2 = extract_odds_from_text(odds.get("1", [""])[0]) if "1" in odds else (None, None, None)

        # check all elements not empty
        if not all([hc[0], hc[1], hc[2], hc[3], ou[0], ou[1], ou[3], _1x2[0], _1x2[1], _1x2[2]]):
            continue

        new_row = [
            time_label,
            normalize_handicap_string(hc[0]), hc[1],  # kèo chấp trên, odds trên
            normalize_handicap_string(hc[2]), hc[3],  # kèo chấp dưới, odds dưới
            normalize_handicap_string(ou[0]), ou[1], ou[3],  # T/X, odds tài, odds xỉu
            _1x2[0], _1x2[2], _1x2[1]  # 1X2 - 1, X, 2
        ]

        last_row = read_last_row(filepath)
        if should_log(new_row, last_row):
            with open(filepath, 'a', encoding='utf-8-sig', newline='') as f:
                writer = csv.writer(f)
                if os.path.getsize(filepath) == 0:
                    writer.writerow([
                        "Thời gian", "Kèo chấp đội trên", "Odds đội trên",
                        "Kèo chấp đội dưới", "Odds đội dưới", "Tài/Xỉu", "Odds Tài",
                        "Odds Xỉu", "1X2 - 1", "1X2 - X", "1X2 - 2"
                    ])

                writer.writerow(new_row)