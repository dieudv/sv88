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
    "lng": "vi",
}
OUTPUT_DIR = "matches"
os.makedirs(OUTPUT_DIR, exist_ok=True)


# === Hàm tiện ích ===
def sanitize_filename(name: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', "_", name).replace(" ", "_")


def parse_utc_time(iso_string: str) -> datetime:
    return datetime.strptime(iso_string, "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc
    )


def extract_main_odds(odds_list: list[str]) -> tuple[str, str, str]:
    if not odds_list:
        return None, None, None
    try:
        text = odds_list[0]
        matches = re.findall(r"([\d\.]+)\*\d+h|([\d\.]+)\*\d+a|([\d\.]+)\*\d+d", text)
        home = away = draw = None
        for h, a, d in matches:
            if h:
                home = h
            if a:
                away = a
            if d:
                draw = d
        return home, away, draw
    except Exception as e:
        print(f"[LỖI] extract_main_odds: {e}")
        return None, None, None


def get_match_status(match_time: str, match_data: dict) -> tuple[str, str]:
    now = datetime.now(timezone.utc)
    match_start = parse_utc_time(match_time)
    delta = now - match_start

    score = match_data.get("4", {})
    home_score = score.get("0", 0)
    away_score = score.get("1", 0)
    hi1_home = score.get("5", 0)
    hi1_away = score.get("6", 0)
    score_str = f"{home_score}-{away_score}"

    elapsed_ms = match_data.get("6", 0)
    minute = int(elapsed_ms / 1000 / 60)

    if delta < timedelta(minutes=-15):
        return now.strftime("%H:%M"), "-"
    elif -15 <= delta.total_seconds() < 0:
        return "Trước trận", "-"

    if elapsed_ms == 0 and delta >= timedelta(seconds=0):
        return "1H 0'", score_str

    hi1_played = (hi1_home + hi1_away) > 0

    if not hi1_played:
        if minute <= 45:
            return f"1H {minute}'", score_str
        return "Hết H1", score_str
    else:
        if minute <= 50:
            return f"2H {minute}'", score_str
        return "Chung cuộc", score_str


def file_already_has_final(filepath: str) -> bool:
    if not os.path.exists(filepath):
        return False
    try:
        df = pd.read_csv(filepath)
        return "Chung cuộc" in df["Thời điểm"].values
    except Exception as e:
        print(f"[LỖI] Kiểm tra file {filepath}: {e}")
        return False


def write_match_to_csv(filepath: str, df: pd.DataFrame):
    if file_already_has_final(filepath):
        print(f"[BỎ QUA] Đã có 'Chung cuộc' trong {filepath}")
        return

    header = not os.path.exists(filepath)
    df.to_csv(filepath, mode="a", index=False, header=header, encoding="utf-8-sig")


# === Lấy dữ liệu từ API ===
def fetch_match_data():
    try:
        res = requests.get(API_URL, headers=HEADERS)
        res.raise_for_status()
        data = res.json()
        competitions = data[0] + data[1]
        with open("data.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return competitions
    except Exception as e:
        print(f"[LỖI] Không thể lấy dữ liệu: {e}")
        return []


# === Xử lý dữ liệu từng trận ===
def process_matches():
    competitions = fetch_match_data()
    for comp in competitions:
        league_name = comp.get("1", "Unknown")
        matches = comp.get("2", [])

        for match in matches:
            if "16" in match or match.get("17", False):
                continue  # Bỏ kèo phụ

            try:
                match_time = match.get("0", "")
                home = match.get("2", "Home")
                away = match.get("3", "Away")
                odds = match.get("7", {})

                time_label, score = get_match_status(match_time, match)
                odds_1x2 = extract_main_odds(odds.get("1", []))
                ou = extract_main_odds(odds.get("3", []))
                hc = extract_main_odds(odds.get("5", []))

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
                    "1X2 - Pachuca": odds_1x2[1],
                }

                df = pd.DataFrame([row])
                filename = sanitize_filename(f"{league_name} - {home} vs {away}.csv")
                filepath = os.path.join(OUTPUT_DIR, filename)
                write_match_to_csv(filepath, df)

            except Exception as e:
                print(f"[LỖI] Trận {match.get('2')} vs {match.get('3')}: {e}")


if __name__ == "__main__":
    process_matches()
