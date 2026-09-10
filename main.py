import os
import requests
import threading
import time
from flask import Flask, request
from datetime import datetime

app = Flask(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
DHAN_CLIENT_ID = os.getenv("DHAN_CLIENT_ID")
DHAN_ACCESS_TOKEN = os.getenv("DHAN_ACCESS_TOKEN")
MY_URL = os.getenv("MY_URL")

# Dhan headers
def dhan_headers():
    return {
        "access-token": DHAN_ACCESS_TOKEN,
        "client-id": DHAN_CLIENT_ID,
        "Content-Type": "application/json"
    }

# 1. Get Expiry List - CORRECT V2 URL
def get_dhan_expiry(underlying_scrip, underlying_seg):
    try:
        url = "https://api.dhan.co/v2/optionchain/expirylist"
        payload = {
            "UnderlyingScrip": underlying_scrip,
            "UnderlyingSeg": underlying_seg
        }
        r = requests.post(url, headers=dhan_headers(), json=payload, timeout=15)
        print(f"Dhan expiry response {underlying_scrip}: {r.status_code} {r.text[:500]}")
        if r.status_code == 200:
            j = r.json()
            if 'data' in j and len(j['data']) > 0:
                return j['data'][0] # e.g. "2026-09-12"
        return None
    except Exception as e:
        print(f"Expiry error: {e}")
        return None

# 2. Get Index Spot LTP (NIFTY/BANKNIFTY/SENSEX)
def get_index_ltp(underlying_scrip, underlying_seg):
    try:
        url = "https://api.dhan.co/v2/marketfeed/ltp"
        # For Index, exchange is IDX_I
        seg_key = "IDX_I" if underlying_seg == "IDX_I" else "NSE_FNO"
        # Dhan needs Security ID for index: 13=NIFTY, 25=BANKNIFTY, 51=SENSEX
        payload = { seg_key: [underlying_scrip] } if seg_key == "IDX_I" else {"IDX_I": [underlying_scrip]}
        # Correct format for IDX_I is IDX_I
        payload = {"IDX_I": [underlying_scrip]}
        r = requests.post(url, headers=dhan_headers(), json=payload, timeout=10)
        print(f"Index LTP {underlying_scrip}: {r.text[:500]}")
        if r.status_code == 200:
            j = r.json()
            # response structure: data -> IDX_I -> {id: {last_price}}
            data = j.get('data', {})
            idx_data = data.get('IDX_I', {})
            if str(underlying_scrip) in idx_data:
                return idx_data[str(underlying_scrip)]['last_price']
            # sometimes key is int
            for k,v in idx_data.items():
                return v['last_price']
        return None
    except Exception as e:
        print(f"Index LTP error: {e}")
        return None

# 3. Get Option LTP by strike
def get_option_ltp(underlying_scrip, underlying_seg, expiry, strike, opt_type):
    try:
        # Get option chain
        url = "https://api.dhan.co/v2/optionchain"
        payload = {
            "UnderlyingScrip": underlying_scrip,
            "UnderlyingSeg": underlying_seg,
            "Expiry": expiry
        }
        r = requests.post(url, headers=dhan_headers(), json=payload, timeout=15)
        if r.status_code!= 200:
            print(f"Option chain failed: {r.text[:1000]}")
            return None

        j = r.json()
        oc_list = j.get('data', {}).get('oc', {})

        # oc is dict: strike -> {ce, pe}
        # Dhan format: {"25000": {"ce": {securityId...}, "pe": {...}}}
        target_sec_id = None
        # Try dict format
        if isinstance(oc_list, dict):
            s_key = str(float(strike)) if f"{strike}.0" in oc_list else str(strike)
            # find closest
            for k, v in oc_list.items():
                try:
                    if int(float(k)) == int(strike):
                        if opt_type == "CE" and 'ce' in v:
                            target_sec_id = v['ce'].get('securityId')
                        elif opt_type == "PE" and 'pe' in v:
                            target_sec_id = v['pe'].get('securityId')
                        break
                except:
                    continue
        elif isinstance(oc_list, list): # old format
            for item in oc_list:
                if int(float(item.get('strikePrice',0))) == int(strike) and item.get('optionType') == opt_type:
                    target_sec_id = item.get('securityId')
                    break

        if not target_sec_id:
            print(f"Strike {strike} {opt_type} not found")
            return None

        # Get LTP for that security
        ltp_url = "https://api.dhan.co/v2/marketfeed/ltp"
        ltp_payload = {"NSE_FNO": [int(target_sec_id)]}
        ltp_r = requests.post(ltp_url, headers=dhan_headers(), json=ltp_payload, timeout=10)
        ltp_j = ltp_r.json()
        ltp = ltp_j['data']['NSE_FNO'][str(target_sec_id)]['last_price']
        return ltp

    except Exception as e:
        print(f"Option LTP error {strike}{opt_type}: {e}")
        return None

def send_telegram(text, chat_id=None):
    try:
        cid = chat_id or CHAT_ID
        if not cid:
            return
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": cid, "text": text, "parse_mode": "Markdown"}, timeout=10)
    except Exception as e:
        print(f"Telegram send error: {e}")

def build_msg(index_name, scrip, seg):
    expiry = get_dhan_expiry(scrip, seg)
    if not expiry:
        return f"⏳ {index_name} expiry syncing - try again 1 min /{index_name.lower()}"

    spot = get_index_ltp(scrip, seg) or 0
    atm = round(spot / 50) * 50 if index_name!= "SENSEX" else round(spot / 100) * 100

    # Get ATM CE PE
    ce_ltp = get_option_ltp(scrip, seg, expiry, atm, "CE")
    pe_ltp = get_option_ltp(scrip, seg, expiry, atm, "PE")

    if ce_ltp is None:
        return f"⏳ {index_name} connecting Dhan... Try again 30 sec /{index_name.lower()}"

    ce_str = f"{ce_ltp:.2f}"
    pe_str = f"{pe_ltp:.2f}" if pe_ltp else "N/A"

    msg = f"📊 *{index_name} {expiry}*\n"
    msg += f"Spot: {spot:.2f} | ATM: {atm}\n\n"
    msg += f"🟢 CE {atm}: {ce_str}\n"
    msg += f"🔴 PE {atm}: {pe_str}\n\n"
    msg += f"✅ DHAN REAL LIVE"
    return msg

@app.route("/")
def home():
    return "Bot Live - Dhan V2"

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json()
        if not data:
            return "ok"
        message = data.get("message", {})
        chat_id = message.get("chat", {}).get("id")
        text = message.get("text", "").lower()

        if not text:
            return "ok"

        # Save chat_id automatically
        global CHAT_ID
        if chat_id:
            os.environ["CHAT_ID"] = str(chat_id)

        if "/nifty" in text:
            msg = build_msg("NIFTY", 13, "IDX_I")
            send_telegram(msg, chat_id)
        elif "/banknifty" in text:
            msg = build_msg("BANKNIFTY", 25, "IDX_I")
            send_telegram(msg, chat_id)
        elif "/sensex" in text:
            msg = build_msg("SENSEX", 51, "IDX_I")
            send_telegram(msg, chat_id)
        elif "/start" in text:
            send_telegram("Welcome! Use /nifty /banknifty /sensex", chat_id)

        return "ok"
    except Exception as e:
        print(f"Webhook error: {e}")
        return "ok"

# Auto loop for 10 min signals
def auto_loop():
    while True:
        try:
            now = datetime.now()
            # Market hours 9:15 to 15:30 IST Mon-Fri
            if now.weekday() < 5 and 9 <= now.hour < 16:
                if CHAT_ID:
                    msg = build_msg("NIFTY", 13, "IDX_I")
                    send_telegram(f"🔔 Auto 10min\n{msg}")
            time.sleep(600) # 10 min
        except Exception as e:
            print(f"Auto loop error: {e}")
            time.sleep(60)

threading.Thread(target=auto_loop, daemon=True).start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
