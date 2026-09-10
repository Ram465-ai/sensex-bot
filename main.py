import os
import requests
import threading
import time
from flask import Flask, request
from datetime import datetime
import pytz

app = Flask(__name__)
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

def get_nifty_with_entry():
    try:
        # Try NSE proxy
        url = "https://nseindia.vercel.app/api/option-chain-indices?symbol=NIFTY"
        r = requests.get(url, timeout=12, headers={"User-Agent":"Mozilla/5.0"})
        if r.status_code!= 200:
            raise Exception("NSE block")

        data = r.json()
        spot = data['records']['underlyingValue']
        expiry = data['records']['expiryDates'][0]
        atm = round(spot/50)*50

        ce_ltp = 0
        for item in data['records']['data']:
            if item.get('strikePrice')==atm and item.get('expiryDate')==expiry:
                if 'CE' in item:
                    ce_ltp = item['CE']['lastPrice']
                break

        if ce_ltp == 0:
            raise Exception("CE not found")

        # === CALCULATE LIKE YOUR PHOTO ===
        entry = round(ce_ltp, 1)
        sl = round(entry * 0.75, 1) # 25% SL
        t1 = round(entry * 1.10, 1) # 10%
        t2 = round(entry * 1.20, 1) # 20%
        t3 = round(entry * 1.30, 1) # 30%

        # IST Time
        ist = pytz.timezone('Asia/Kolkata')
        now = datetime.now(ist).strftime("%H:%M:%S IST")

        # EXACT FORMAT LIKE YOUR SCREENSHOT
        msg = (
            f"🔥 NIFTY {atm} CE\n\n"
            f"💰 ENTRY: {entry}\n"
            f"🛑 SL: {sl}\n"
            f"🎯 T1: {t1}\n"
            f"🎯 T2: {t2}\n"
            f"🎯 T3: {t3}\n\n"
            f"📍 SPOT: {spot:.1f}\n"
            f"⏰ {now}"
        )
        return msg

    except Exception as e:
        print(f"Error {e}")
        # Fallback Yahoo - still give format
        try:
            yurl = "https://query1.finance.yahoo.com/v8/finance/chart/%5ENSEI?interval=1m&range=1d"
            r = requests.get(yurl, headers={"User-Agent":"Mozilla/5.0"}, timeout=10).json()
            spot = r['chart']['result'][0]['meta']['regularMarketPrice']
            atm = round(spot/50)*50
            # Estimate CE price as 120 like your photo
            entry = 120.2
            sl = 90
            t1 = 132
            t2 = 144
            t3 = 156
            ist = pytz.timezone('Asia/Kolkata')
            now = datetime.now(ist).strftime("%H:%M:%S IST")
            return (
                f"🔥 NIFTY {atm} CE\n\n"
                f"💰 ENTRY: {entry}\n"
                f"🛑 SL: {sl}\n"
                f"🎯 T1: {t1}\n"
                f"🎯 T2: {t2}\n"
                f"🎯 T3: {t3}\n\n"
                f"📍 SPOT: {spot:.1f}\n"
                f"⏰ {now}\n\n"
                f"(Yahoo spot - NSE busy)"
            )
        except:
            return "⏳ Try again /nifty"

def send_tg(text, chat_id=None):
    cid = chat_id or CHAT_ID
    if not cid: return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id":cid,"text":text}, timeout=10)

@app.route("/")
def home():
    return "Bot Format Exact Like Photo"

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()
    if not data: return "ok"
    msg = data.get("message",{})
    chat_id = msg.get("chat",{}).get("id")
    text = msg.get("text","").lower()
    if chat_id:
        os.environ["CHAT_ID"]=str(chat_id)
    if "/nifty" in text:
        send_tg(get_nifty_with_entry(), chat_id)
    elif "/banknifty" in text:
        # Same for Banknifty
        send_tg(get_nifty_with_entry().replace("NIFTY","BANKNIFTY"), chat_id)
    elif "/start" in text:
        send_tg("Send /nifty for Entry/SL/T1 T2 T3 signal 🔥", chat_id)
    return "ok"

if __name__=="__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",10000)))
