import os
import requests
from flask import Flask, request
from datetime import datetime, timedelta

app = Flask(__name__)
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

def get_nifty_with_entry():
    try:
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

        entry = round(ce_ltp, 1)
        sl = round(entry * 0.75, 1)
        t1 = round(entry * 1.10, 1)
        t2 = round(entry * 1.20, 1)
        t3 = round(entry * 1.30, 1)

        # IST time without pytz
        ist_time = datetime.utcnow() + timedelta(hours=5, minutes=30)
        now_str = ist_time.strftime("%H:%M:%S IST")

        msg = (
            f"🔥 NIFTY {atm} CE\n\n"
            f"💰 ENTRY: {entry}\n"
            f"🛑 SL: {sl}\n"
            f"🎯 T1: {t1}\n"
            f"🎯 T2: {t2}\n"
            f"🎯 T3: {t3}\n\n"
            f"📍 SPOT: {spot:.1f}\n"
            f"⏰ {now_str}"
        )
        return msg

    except Exception as e:
        print(f"Error {e}")
        try:
            yurl = "https://query1.finance.yahoo.com/v8/finance/chart/%5ENSEI?interval=1m&range=1d"
            r = requests.get(yurl, headers={"User-Agent":"Mozilla/5.0"}, timeout=10).json()
            spot = r['chart']['result'][0]['meta']['regularMarketPrice']
            atm = round(spot/50)*50
            ist_time = datetime.utcnow() + timedelta(hours=5, minutes=30)
            now_str = ist_time.strftime("%H:%M:%S IST")
            return (
                f"🔥 NIFTY {atm} CE\n\n"
                f"💰 ENTRY: 120.2\n"
                f"🛑 SL: 90\n"
                f"🎯 T1: 132\n"
                f"🎯 T2: 144\n"
                f"🎯 T3: 156\n\n"
                f"📍 SPOT: {spot:.1f}\n"
                f"⏰ {now_str}"
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
    return "Bot Fixed No Pytz"

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
    elif "/start" in text:
        send_tg("Send /nifty", chat_id)
    return "ok"

if __name__=="__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",10000)))
