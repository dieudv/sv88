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

os.makedirs("matches", exist_ok=True)


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


def extract_handicap_and_odds(odds_list):
    if not odds_list:
        return None, None, None, None
    try:
        text = odds_list[0]
        parts = text.split()
        handicap = parts[0]
        home_odds = re.findall(r'([-\d.]+)\*\d+h', text)
        away_odds = re.findall(r'([-\d.]+)\*\d+a', text)
        home = float(home_odds[0]) if home_odds else None
        away = float(away_odds[0]) if away_odds else None

        # Đội dưới là âm của handicap nếu là dạng số, còn nếu là dạng 0-0.5 thì thêm dấu trừ
        under_handicap = (
            f"-{handicap}" if not str(handicap).startswith('-') else str(handicap).replace("-", "")
        )
        return handicap, home, under_handicap, away
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


response = requests.get(API_URL, headers=HEADERS)
data = response.json()
competitions = data[0] + data[1]

for comp in competitions:
    comp_name = comp.get("1", "Unknown")
    for match in comp.get("2", []):
        if "16" in match or match.get("17", False):
            continue

        home = match.get("2", "home")
        away = match.get("3", "away")
        filename = sanitize_filename(f"{comp_name} - {home} vs {away}.csv")
        filepath = os.path.join("matches", filename)

        time_label = get_time_label(match.get("0"), match)
        score = match.get("4", {})
        score_str = f"{score.get('0', 0)} - {score.get('1', 0)}"

        odds = match.get("7", {})

        hc = extract_handicap_and_odds(odds.get("5", []))
        ou = extract_handicap_and_odds(odds.get("3", []))
        _1x2 = extract_odds_from_text(odds.get("1", [""])[0]) if "1" in odds else (None, None, None)

        # check all elements not empty
        if not all([hc[0], hc[1], hc[2], hc[3], ou[0], ou[1], ou[3], _1x2[0], _1x2[1], _1x2[2]]):
            continue

        new_row = [
            time_label,
            hc[0], hc[1],  # kèo chấp trên, odds trên
            hc[2], hc[3],  # kèo chấp dưới, odds dưới
            ou[0], ou[1], ou[3],  # T/X, odds tài, odds xỉu
            _1x2[0], _1x2[2], _1x2[1]  # 1X2 - 1, X, 2
        ]

        last_row = read_last_row(filepath)
        if should_log(new_row, last_row):
            with open(filepath, 'a', encoding='utf-8', newline='') as f:
                writer = csv.writer(f)
                if os.path.getsize(filepath) == 0:
                    writer.writerow([
                        "Thời gian", "Kèo chấp (tên đội trên)", "Odds (đội trên)",
                        "Kèo chấp (tên đội dưới)", "Odds (đội dưới)", "Tài/Xỉu", "Odds Tài",
                        "Odds Xỉu", "1X2 - 1", "1X2 - X", "1X2 - 2"
                    ])

                writer.writerow(new_row)
                break