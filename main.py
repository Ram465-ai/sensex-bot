import os, requests, time, threading
from datetime import datetime
from flask import Flask

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

app = Flask(__name__)
@app.route('/')
def home():
    return "BOT LIVE - NIFTY BANKNIFTY"

def send_tg(msg):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": CHAT_ID, "text": msg}, timeout=15)
    except:
        pass

def get_data(symbol):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        s = requests.Session()
        s.get("https://www.nseindia.com", headers=headers, timeout=10)
        url = f"https://www.nseindia.com/api/option-chain-indices?symbol={symbol}"
        data = s.get(url, headers=headers, timeout=10).json()
        spot = data['records']['underlyingValue']
        atm = round(spot / 100) * 100
        for row in data['records']['data']:
            if row.get('strikePrice') == atm:
                sigs = []
                ce = row.get('CE')
                pe = row.get('PE')
                if ce and ce.get('pChange', 0) > 2:
                    sigs.append(("CE", atm, ce))
                if pe and pe.get('pChange', 0) > 2:
                    sigs.append(("PE", atm, pe))
                return spot, sigs
        return spot, []
    except:
        return None, []

def bot_loop():
    time.sleep(5)
    send_tg("BOT STARTED")
    while True:
        for sym in ["NIFTY", "BANKNIFTY"]:
            spot, signals = get_data(sym)
            if not spot:
                continue
            for typ, strike, d in signals:
                entry = d['lastPrice']
                sl = int(entry * 0.75)
                t1 = int(entry * 1.4)
                t2 = int(entry * 1.8)
                msg = f"""{sym} {strike} {typ}
ENTRY {entry}
SL {sl}
T1 {t1}
T2 {t2}
SPOT {spot}
TIME {datetime.now().strftime('%H:%M')}"""
                send_tg(msg)
                time.sleep(2)
        time.sleep(900)

threading.Thread(target=bot_loop, daemon=True).start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
