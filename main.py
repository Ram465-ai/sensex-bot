import os, requests, threading, time, json, urllib.parse
from datetime import datetime, timezone, timedelta
from flask import Flask, request

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
MY_URL = "https://sensex-bot-b7b7.onrender.com"
IST = timezone(timedelta(hours=5, minutes=30))

app = Flask(__name__)

@app.route('/')
def home():
    return f"BOT LIVE {datetime.now(IST).strftime('%H:%M:%S')} IST"

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = request.get_json()
        print(f"WEBHOOK HIT: {data}", flush=True)
        cq = data.get("callback_query")
        if cq:
            d = cq.get("data")
            try:
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/answerCallbackQuery", data={"callback_query_id":cq["id"],"text":d}, timeout=5)
            except: pass
            threading.Thread(target=send_signal, args=(d,), daemon=True).start()
        else:
            msg = data.get("message",{}).get("text","").upper()
            if msg in ["NIFTY","BANKNIFTY"]:
                threading.Thread(target=send_signal, args=(msg,), daemon=True).start()
    except Exception as e:
        print(f"Webhook error {e}", flush=True)
    return "OK"

def send_tg(msg, kb=None):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        data = {"chat_id": CHAT_ID, "text": msg}
        if kb:
            data["reply_markup"] = json.dumps(kb)
        r = requests.post(url, data=data, timeout=10)
        print(f"SEND TG RESULT: {r.text}", flush=True)
    except Exception as e:
        print(f"Send fail {e}", flush=True)

def menu():
    kb = {"inline_keyboard": [[{"text":"📈 NIFTY","callback_data":"NIFTY"},{"text":"🏦 BANKNIFTY","callback_data":"BANKNIFTY"}]]}
    send_tg("👇 SELECT:", kb)

def get_spot(sym):
    try:
        m = {"NIFTY":"^NSEI","BANKNIFTY":"^NSEBANK"}
        r = requests.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{m[sym]}?interval=1m&range=1d", headers={"User-Agent":"Mozilla/5.0"}, timeout=5).json()
        return float(r['chart']['result'][0]['meta']['regularMarketPrice'])
    except:
        return 23431.5 if sym=="NIFTY" else 56295.55

def get_price(sym, spot):
    atm = round(spot / (100 if sym=="BANKNIFTY" else 50)) * (100 if sym=="BANKNIFTY" else 50)
    try:
        nse_url = f"https://www.nseindia.com/api/option-chain-indices?symbol={sym}"
        enc = urllib.parse.quote(nse_url, safe='')
        r = requests.get(f"https://api.allorigins.win/raw?url={enc}", timeout=8)
        if r.status_code==200:
            for row in r.json().get('records',{}).get('data',[]):
                if row.get('strikePrice')==atm and row.get('CE',{}).get('lastPrice',0)>5:
                    return float(row['CE']['lastPrice']), atm
    except: pass
    est = 800 + (spot-56295)*0.8 if sym=="BANKNIFTY" else 120 + (spot-23431)*0.5
    return round(max(30, est),1), atm

def send_signal(sym):
    spot = get_spot(sym)
    price, strike = get_price(sym, spot)
    sl=int(price*0.75); t1=int(price*1.10); t2=int(price*1.20); t3=int(price*1.30)
    now = datetime.now(IST).strftime('%H:%M:%S')
    msg = f"🔥 {sym} {strike} CE\n\n💰 ENTRY: {price}\n🛑 SL: {sl}\n🎯 T1: {t1}\n🎯 T2: {t2}\n🎯 T3: {t3}\n\n📍 SPOT: {spot}\n⏰ {now} IST"
    send_tg(msg)
    menu()

def auto_set_webhook():
    time.sleep(2)
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook?url={MY_URL}/webhook"
        r = requests.get(url, timeout=10).json()
        print(f"WEBHOOK SET RESULT === {r}", flush=True)
    except Exception as e:
        print(f"WEBHOOK FAIL {e}", flush=True)

threading.Thread(target=auto_set_webhook, daemon=True).start()
print("=== BOT STARTED ===", flush=True)

if __name__=="__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",10000)))
