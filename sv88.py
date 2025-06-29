import json
import pandas as pd
import os
from datetime import datetime
import re

# Tạo thư mục lưu kết quả nếu chưa có
os.makedirs("matches", exist_ok=True)

def sanitize_filename(s):
    # Loại bỏ ký tự không hợp lệ trong tên file
    return re.sub(r'[\\/*?:"<>|]', "_", s).replace(" ", "_")

def extract_odds(odds_list):
    if not odds_list:
        return None, None, None
    try:
        first = odds_list[0].split()
        return first[0], first[1].split("*")[0], first[2].split("*")[0]
    except:
        return None, None, None

# Load JSON từ file
with open("data.json", "r", encoding="utf-8") as f:
    data = json.load(f)

competitions = data[0]

for comp in competitions:
    comp_name = comp.get("1", "UnknownLeague")
    matches = comp.get("2", [])

    for match in matches:
        try:
            match_time = match.get("0", "")
            time_str = match_time[11:16]
            home = match.get("2", "Home")
            away = match.get("3", "Away")
            score = f"{match.get('4', {}).get('0', 0)}-{match.get('4', {}).get('1', 0)}"
            odds = match.get("7", {})

            odds_1x2 = extract_odds(odds.get("1", []))
            ou = extract_odds(odds.get("3", []))
            hc = extract_odds(odds.get("5", []))

            row = {
                "Giải đấu": comp_name,
                "Thời điểm": time_str,
                "Tỉ số": score,
                "Đội nhà": home,
                "Đội khách": away,
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

            # Tạo tên file: "Giải đấu - Đội A vs Đội B.xlsx"
            filename = sanitize_filename(f"{comp_name} - {home} vs {away}.xlsx")
            filepath = os.path.join("matches", filename)
            df.to_excel(filepath, index=False)
        except Exception as e:
            print(f"Lỗi trận đấu giữa {match.get('2')} và {match.get('3')}: {e}")
