import os, requests, threading, time, json
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
        print(f"Err {e}", flush=True)
    return "OK"

def send_tg(msg, kb=None):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        data = {"chat_id": CHAT_ID, "text": msg}
        if kb: data["reply_markup"] = json.dumps(kb)
        requests.post(url, data=data, timeout=10)
    except Exception as e:
        print(f"Send fail {e}", flush=True)

def menu():
    kb = {"inline_keyboard": [[{"text":"📈 NIFTY","callback_data":"NIFTY"},{"text":"🏦 BANKNIFTY","callback_data":"BANKNIFTY"}]]}
    send_tg("👇 Select Index:", kb)

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
        s = requests.Session()
        s.headers.update({"User-Agent":"Mozilla/5.0","Accept":"application/json","Referer":"https://www.nseindia.com/option-chain"})
        s.get("https://www.nseindia.com/option-chain", timeout=5)
        time.sleep(1)
        r = s.get(f"https://www.nseindia.com/api/option-chain-indices?symbol={sym}", timeout=5).json()
        for row in r.get('records',{}).get('data',[]):
            if row.get('strikePrice')==atm:
                ce = row.get('CE',{}).get('lastPrice')
                if ce and ce>5:
                    return float(ce), atm
    except Exception as e:
        print(f"NSE Fail {e}", flush=True)
    return None, atm

def send_signal(sym):
    spot = get_spot(sym)
    price, strike = get_price(sym, spot)
    now = datetime.now(IST).strftime('%H:%M:%S')
    if price is None:
        send_tg(f"⚠️ {sym} {strike} CE\n\nMarket is closed. Live premium unavailable.\n\n📍 Spot: {spot}\n⏰ {now} IST\n\nTry again at 9:15 AM.")
        menu()
        return
    sl=int(price*0.75); t1=int(price*1.10); t2=int(price*1.20); t3=int(price*1.30)
    msg = f"🔥 {sym} {strike} CE - BUY AT CMP\n\n💰 CMP: {price}\n🛑 Stop Loss: {sl}\n🎯 Target 1: {t1}\n🎯 Target 2: {t2}\n🎯 Target 3: {t3}\n\n📍 Spot Price: {spot}\n⏰ Time: {now} IST\n\n✅ Buy at Market Price"
    send_tg(msg)
    menu()

def auto_set_webhook():
    time.sleep(2)
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook?url={MY_URL}/webhook"
        r = requests.get(url, timeout=10).json()
        print(f"WEBHOOK SET {r}", flush=True)
    except Exception as e:
        print(f"WH Fail {e}", flush=True)

threading.Thread(target=auto_set_webhook, daemon=True).start()
print("=== BOT STARTED CMP MODE ===", flush=True)

if __name__=="__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",10000)))
