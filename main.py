import os, requests, time, threading, json
from datetime import datetime
from flask import Flask

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

app = Flask(__name__)

@app.route('/')
def home():
    return "BOT LIVE - " + datetime.now().strftime('%H:%M:%S')

@app.route('/test')
def test():
    send_menu()
    return "MENU SENT - Check Telegram"

def send_tg(msg, reply_markup=None):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        data = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}
        if reply_markup:
            data["reply_markup"] = json.dumps(reply_markup)
        requests.post(url, data=data, timeout=15)
    except Exception as e:
        print(f"TG Error {e}")

def send_menu():
    keyboard = {
        "inline_keyboard": [
            [{"text": "📈 NIFTY", "callback_data": "NIFTY"}, {"text": "🏦 BANKNIFTY", "callback_data": "BANKNIFTY"}],
            [{"text": "🔥 SENSEX", "callback_data": "SENSEX"}, {"text": "🧪 TEST", "callback_data": "TEST"}]
        ]
    }
    send_tg("👇 *SELECT INDEX:*\nNifty / Banknifty / Sensex", keyboard)

def get_data(symbol):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0",
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://www.nseindia.com/option-chain",
            "Accept-Language": "en-US,en;q=0.9"
        }
        s = requests.Session()
        s.headers.update(headers)
        s.get("https://www.nseindia.com/option-chain", timeout=20)
        time.sleep(2)
        url = f"https://www.nseindia.com/api/option-chain-indices?symbol={symbol}"
        r = s.get(url, timeout=20)
        if r.status_code!= 200:
            time.sleep(2)
            r = s.get(url, timeout=20)
        data = r.json()
        spot = data['records']['underlyingValue']
        print(f"{symbol} SPOT {spot}")
        atm = round(spot / 100) * 100
        sigs=[]
        for row in data['records']['data']:
            if abs(row.get('strikePrice',0)-atm) <= 200:
                ce=row.get('CE'); pe=row.get('PE')
                if ce and ce.get('pChange',0)>1.5 and ce.get('lastPrice',0)>5:
                    sigs.append(("CE",row['strikePrice'],ce))
                if pe and pe.get('pChange',0)>1.5 and pe.get('lastPrice',0)>5:
                    sigs.append(("PE",row['strikePrice'],pe))
        return spot,sigs
    except Exception as e:
        print(f"Error {symbol}: {e}")
        return None,[]

def bot_loop():
    time.sleep(10)
    send_tg("✅ *BOT LIVE WITH NAVIGATION*")
    time.sleep(2)
    send_menu()
    while True:
        try:
            for sym in ["NIFTY", "BANKNIFTY"]:
                spot, signals = get_data(sym)
                if not spot: continue
                for typ, strike, d in signals:
                    entry=d['lastPrice']
                    sl=int(entry*0.70); t1=int(entry*1.3); t2=int(entry*1.7)
                    msg=f"🔥 *{sym} {strike} {typ}*\n\n💰 ENTRY: {entry}\n🛑 SL: {sl}\n🎯 T1: {t1}\n🎯 T2: {t2}\n📍 SPOT: {spot}"
                    send_tg(msg); time.sleep(3)
            time.sleep(300)
        except Exception as e:
            print(f"Loop Error {e}"); time.sleep(60)

def tg_polling():
    offset=0
    while True:
        try:
            url=f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?offset={offset}&timeout=30"
            r=requests.get(url, timeout=35).json()
            for upd in r.get("result", []):
                offset=upd["update_id"]+1
                cq=upd.get("callback_query")
                if cq:
                    data=cq.get("data")
                    requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/answerCallbackQuery", data={"callback_query_id": cq["id"], "text": f"{data} Checking..."})
                    if data=="TEST":
                        send_tg("🧪 *TEST OK ✅*\nBot 100% Working")
                    elif data in ["NIFTY","BANKNIFTY"]:
                        send_tg(f"🔍 *{data} Checking...*")
                        spot,sigs=get_data(data)
                        if sigs:
                            typ,strike,d=sigs[0]
                            send_tg(f"🔥 *{data} {strike} {typ}*\nENTRY {d['lastPrice']}\nSPOT {spot}")
                        else:
                            send_tg(f"📍 *{data} SPOT: {spot}*\nNo strong signal now")
                    else:
                        send_tg(f"🔥 *{data} Coming Soon!*")
                    send_menu()
            time.sleep(2)
        except Exception as e:
            print(f"Poll Error {e}"); time.sleep(5)

threading.Thread(target=bot_loop, daemon=True).start()
threading.Thread(target=tg_polling, daemon=True).start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
