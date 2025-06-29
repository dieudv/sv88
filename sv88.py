import json
import pandas as pd
import os
import re
from datetime import datetime, timedelta
from openpyxl import load_workbook

# Tạo thư mục xuất
os.makedirs("matches", exist_ok=True)

def append_to_excel(filepath, df):
    from openpyxl import load_workbook

    if not os.path.exists(filepath):
        # File chưa tồn tại → ghi mới
        df.to_excel(filepath, index=False)
    else:
        # Mở workbook và tính số dòng đang có
        book = load_workbook(filepath)
        sheet = book.active
        start_row = sheet.max_row

        # Ghi thêm từ dòng tiếp theo
        with pd.ExcelWriter(filepath, engine='openpyxl', mode='a', if_sheet_exists='overlay') as writer:
            df.to_excel(writer, index=False, header=False, startrow=start_row)

def sanitize_filename(s):
    return re.sub(r'[\\/*?:"<>|]', "_", s).replace(" ", "_")

def extract_odds(odds_list):
    if not odds_list:
        return None, None, None
    try:
        text = odds_list[0]
        # Regex tìm giá trị + hậu tố
        matches = re.findall(r'([\d\.]+)\*\d+h|([\d\.]+)\*\d+a|([\d\.]+)\*\d+d', text)
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
        print(f"Lỗi extract_odds: {e}")
        return None, None, None

# Load dữ liệu JSON
with open("data.json", "r", encoding="utf-8") as f:
    data = json.load(f)

competitions = data[0]

for comp in competitions:
    comp_name = comp.get("1", "UnknownLeague")
    matches = comp.get("2", [])

    for match in matches:
        # Bỏ kèo phụ
        if "16" in match or match.get("17", False):
            continue

        try:
            match_time_str = match.get("0", "")
            match_time = datetime.strptime(match_time_str, "%Y-%m-%dT%H:%M:%SZ")
            now = datetime.utcnow()

            # Gán thời điểm
            delta = match_time - now
            if timedelta(minutes=0) < delta <= timedelta(minutes=15):
                time_label = "Trước trận"
            else:
                time_label = now.strftime("%H:%M")

            home = match.get("2", "Home")
            away = match.get("3", "Away")
            score = f"{match.get('4', {}).get('0', 0)}-{match.get('4', {}).get('1', 0)}"
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
            filename = sanitize_filename(f"{comp_name} - {home} vs {away}.xlsx")
            filepath = os.path.join("matches", filename)
            append_to_excel(filepath, df)

        except Exception as e:
            print(f"Lỗi trận {match.get('2')} vs {match.get('3')}: {e}")
