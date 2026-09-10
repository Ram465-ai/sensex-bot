import os
import requests
import threading
import time
from flask import Flask, request
from datetime import datetime

app = Flask(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# NSE Session
session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/option-chain"
})

def get_nse_data(symbol):
    try:
        session.get("https://www.nseindia.com/option-chain", timeout=10)
        time.sleep(0.5)
        url = f"https://www.nseindia.com/api/option-chain-indices?symbol={symbol}"
        r = session.get(url, timeout=10)
        if r.status_code == 200:
            return r.json()
        print(f"NSE {symbol} status {r.status_code}")
        return None
    except Exception as e:
        print(f"NSE error {symbol}: {e}")
        return None

def build_msg(index_name):
    try:
        # Symbol mapping
        nse_symbol = "NIFTY" if index_name == "NIFTY" else "BANKNIFTY" if index_name == "BANKNIFTY" else "NIFTY"

        if index_name == "SENSEX":
            # SENSEX from BSE
            try:
                r = requests.get("https://api.bseindia.com/BseIndiaAPI/api/ComHeader/w?quotetype=EQ&scripcode=16", headers={"User-Agent":"Mozilla/5.0"}, timeout=10).json()
                spot = float(r.get('CurrRate', 0))
                atm = round(spot/100)*100
                # For SENSEX we can't get option chain free, give spot only + NIFTY signal
                msg = f"📊 *SENSEX Spot*\nSpot: {spot:.2f} | ATM: {atm}\n\n"
                msg += f"For SENSEX Options, use Dhan Data API (₹499).\n"
                msg += f"Free bot gives NIFTY/BANKNIFTY signals.\nUse /nifty /banknifty\n"
                return msg
            except:
                return "⏳ SENSEX BSE syncing... try /nifty"

        data = get_nse_data(nse_symbol)
        if not data or 'records' not in data:
            return f"⏳ {index_name} NSE syncing... try again 10 sec /{index_name.lower()}"

        spot = data['records']['underlyingValue']
        expiry = data['records']['expiryDates'][0]
        atm = round(spot / 50) * 50
        if index_name == "BANKNIFTY":
            atm = round(spot / 100) * 100

        ce_data = None
        pe_data = None

        # Find ATM data
        for item in data['records']['data']:
            if item.get('strikePrice') == atm and item.get('expiryDate') == expiry:
                ce_data = item.get('CE')
                pe_data = item.get('PE')
                break

        if not ce_data and not pe_data:
            return f"⏳ {index_name} ATM {atm} not found..."

        ce_ltp = ce_data['lastPrice'] if ce_data else 0
        pe_ltp = pe_data['lastPrice'] if pe_data else 0
        ce_oi = ce_data['openInterest'] if ce_data else 0
        pe_oi = pe_data['openInterest'] if pe_data else 0
        ce_high = ce_data.get('dayHigh', ce_ltp) if ce_data else ce_ltp
        pe_high = pe_data.get('dayHigh', pe_ltp) if pe_data else pe_ltp

        # === ENTRY LOGIC - SMART BUY SIGNAL ===
        # 1. OI Logic
        oi_bias = "BULLISH" if pe_oi > ce_oi else "BEARISH"
        pcr = round(pe_oi / ce_oi, 2) if ce_oi > 0 else 0

        signal_text = ""
        if pcr > 1.1: # More PE OI = Support = Bullish -> Buy CE
            entry = round(ce_high + 1, 1) if ce_high > ce_ltp else round(ce_ltp * 1.03, 1)
            sl = round(entry * 0.65, 1) # 35% SL
            t1 = round(entry * 1.4, 1)
            t2 = round(entry * 2.0, 1)
            signal_text = (
                f"🟢 *BUY {atm} CE*\n"
                f"Entry: Above {entry}\n"
                f"SL: {sl} (-35%)\n"
                f"T1: {t1} | T2: {t2}\n"
                f"Logic: PCR {pcr} Bullish + PE OI High\n"
            )
        elif pcr < 0.9: # More CE OI = Resistance = Bearish -> Buy PE
            entry = round(pe_high + 1, 1) if pe_high > pe_ltp else round(pe_ltp * 1.03, 1)
            sl = round(entry * 0.65, 1)
            t1 = round(entry * 1.4, 1)
            t2 = round(entry * 2.0, 1)
            signal_text = (
                f"🔴 *BUY {atm} PE*\n"
                f"Entry: Above {entry}\n"
                f"SL: {sl} (-35%)\n"
                f"T1: {t1} | T2: {t2}\n"
                f"Logic: PCR {pcr} Bearish + CE OI High\n"
            )
        else:
            # Sideways - give both
            ce_entry = round(ce_ltp * 1.04, 1)
            pe_entry = round(pe_ltp * 1.04, 1)
            signal_text = (
                f"⚪ *SIDEWAYS - Wait for Breakout*\n"
                f"Buy CE above {ce_entry} | SL {round(ce_entry*0.65,1)}\n"
                f"Buy PE above {pe_entry} | SL {round(pe_entry*0.65,1)}\n"
                f"Logic: PCR {pcr} Neutral\n"
            )

        msg = f"📊 *{index_name} {expiry}*\n"
        msg += f"Spot: {spot:.2f} | ATM: {atm} | PCR: {pcr}\n"
        msg += f"CE LTP: {ce_ltp} | OI: {ce_oi/1000:.1f}k\n"
        msg += f"PE LTP: {pe_ltp} | OI: {pe_oi/1000:.1f}k\n\n"
        msg += signal_text + "\n"
        msg += f"✅ NSE LIVE - Free, No Dhan needed"

        return msg

    except Exception as e:
        print(f"Build error {index_name}: {e}")
        return f"⏳ {index_name} parsing error - try again /{index_name.lower()}"

def send_telegram(text, chat_id=None):
    try:
        cid = chat_id or CHAT_ID
        if not cid:
            print("No CHAT_ID")
            return
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {"chat_id": cid, "text": text, "parse_mode": "Markdown"}
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"TG send error: {e}")

@app.route("/")
def home():
    return "Bot Live NSE + Entry Signals V3"

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json()
        if not data:
            return "ok"
        message = data.get("message", {})
        chat_id = message.get("chat", {}).get("id")
        text = message.get("text", "").lower()

        if chat_id:
            os.environ["CHAT_ID"] = str(chat_id)

        if "/nifty" in text:
            msg = build_msg("NIFTY")
            send_telegram(msg, chat_id)
        elif "/banknifty" in text or "/bn" in text:
            msg = build_msg("BANKNIFTY")
            send_telegram(msg, chat_id)
        elif "/sensex" in text:
            msg = build_msg("SENSEX")
            send_telegram(msg, chat_id)
        elif "/start" in text:
            send_telegram("Welcome Uday!\n/nifty - Nifty with Buy Entry\n/banknifty - BankNifty\nBot is FREE - No Dhan ₹499 needed", chat_id)

        return "ok"
    except Exception as e:
        print(f"Webhook error: {e}")
        return "ok"

def auto_loop():
    while True:
        try:
            now = datetime.now()
            # 9:15 to 15:30 Mon-Fri
            if now.weekday() < 5 and 9 <= now.hour <= 15:
                if CHAT_ID and BOT_TOKEN:
                    if now.minute % 15 == 0: # every 15 min
                        msg = build_msg("NIFTY")
                        send_telegram(f"🔔 *15 Min Auto*\n{msg}")
            time.sleep(60)
        except Exception as e:
            print(f"Auto loop error: {e}")
            time.sleep(60)

threading.Thread(target=auto_loop, daemon=True).start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
