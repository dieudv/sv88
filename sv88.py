import json
import pandas as pd
import requests
import os
import re
from datetime import datetime, timedelta, timezone

# === Cấu hình ===
API_URL = "https://be.sb21.net/api/v2/getEvent?timeRange=today&sportType=1_1&sportId=1&oddsStyle=ma&pinLeague=false"
HEADERS = {
    "accept": "application/json",
    "content-type": "application/json",
    "lng": "vi"
}
OUTPUT_DIR = "matches"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# === Hàm tiện ích ===
def sanitize_filename(s):
    return re.sub(r'[\\/*?:"<>|]', "_", s).replace(" ", "_")

def parse_utc_time(iso_string):
    return datetime.strptime(iso_string, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)

def get_time_and_score(match_time_str, match):
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    match_time = parse_utc_time(match_time_str)
    delta = now - match_time

    score = match.get("4", {})
    home_score = score.get("0", 0)
    away_score = score.get("1", 0)
    hi1_home = score.get("5", 0)
    hi1_away = score.get("6", 0)
    score_str = f"{home_score}-{away_score}"

    minute_in_half = int(match.get("6", 0) / 1000 / 60)
    hi1_played = hi1_home + hi1_away > 0
    match_started = delta >= timedelta(seconds=0)

    # Trận chưa bắt đầu
    if delta < timedelta(minutes=-15):
        return now.strftime("%H:%M"), "-"
    elif timedelta(minutes=-15) <= delta < timedelta(seconds=0):
        return "Trước trận", "-"

    # Trận đã bắt đầu nhưng phút hiệp là 0 → vẫn xem là 0'
    if not hi1_played:
        if minute_in_half <= 45:
            return f"1H {minute_in_half}'", score_str
        else:
            return "Hết H1", score_str
    else:
        if minute_in_half <= 50:
            return f"2H {minute_in_half}'", score_str
        else:
            return "Chung cuộc", score_str

def extract_odds(odds_list):
    if not odds_list:
        return None, None, None
    try:
        text = odds_list[0]
        matches = re.findall(r'([\d\.]+)\*\d+h|([\d\.]+)\*\d+a|([\d\.]+)\*\d+d', text)
        home = away = draw = None
        for h, a, d in matches:
            if h: home = h
            if a: away = a
            if d: draw = d
        return home, away, draw
    except Exception as e:
        print(f"Lỗi extract_odds: {e}")
        return None, None, None

def file_has_final_csv(filepath):
    try:
        if not os.path.exists(filepath):
            return False
        df_old = pd.read_csv(filepath)
        return "Chung cuộc" in df_old["Thời điểm"].values
    except Exception as e:
        print(f"[ERROR] Lỗi kiểm tra file {filepath}: {e}")
        return False

def append_to_csv(filepath, df):
    if not os.path.exists(filepath):
        df.to_csv(filepath, index=False, mode='w', encoding='utf-8-sig')
    else:
        if file_has_final_csv(filepath):
            print(f"[SKIP] {filepath} đã có dòng 'Chung cuộc'")
            return
        df.to_csv(filepath, index=False, header=False, mode='a', encoding='utf-8-sig')

# === Gọi API ===
try:
    response = requests.get(API_URL, headers=HEADERS)
    response.raise_for_status()
    data = response.json()
    competitions = data[0]
    competitions.extend(data[1])
    with open('data.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
except Exception as e:
    print(f"[ERROR] Không thể lấy dữ liệu từ API: {e}")
    competitions = []

# === Xử lý từng trận ===
for comp in competitions:
    comp_name = comp.get("1", "UnknownLeague")
    matches = comp.get("2", [])

    for match in matches:
        if "16" in match or match.get("17", False):
            continue

        try:
            time_label, score = get_time_and_score(match.get("0", ""), match)
            home = match.get("2", "Home")
            away = match.get("3", "Away")
            odds = match.get("7", {})

            odds_1x2 = extract_odds(odds.get("1", []))
            ou = extract_odds(odds.get("3", []))
            hc = extract_odds(odds.get("5", []))

            row = {
                "Thời điểm": time_label,
                "Tỉ số": score,
                "Kèo chấp": hc[0],
                "Odds Real": hc[1],
                "Odds Pachuca": hc[2],
                "T/X": ou[0],
                "Odds Tài": ou[1],
                "Odds Xỉu": ou[2],
                "1X2 - Real": odds_1x2[0],
                "1X2 - Hòa": odds_1x2[2],
                "1X2 - Pachuca": odds_1x2[1]
            }

            df = pd.DataFrame([row])
            filename = sanitize_filename(f"{comp_name} - {home} vs {away}.csv")
            filepath = os.path.join(OUTPUT_DIR, filename)
            append_to_csv(filepath, df)

        except Exception as e:
            print(f"[ERROR] Trận {match.get('2')} vs {match.get('3')}: {e}")