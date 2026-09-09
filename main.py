import os, requests, time, threading, json, urllib.parse
from datetime import datetime
from flask import Flask

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
app = Flask(__name__)

@app.route('/')
def home(): return f"BOT LIVE {datetime.now().strftime('%H:%M:%S')}"
@app.route('/test')
def test(): send_menu(); return "OK"

def send_tg(msg, kb=None):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        data = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}
        if kb: data["reply_markup"] = json.dumps(kb)
        requests.post(url, data=data, timeout=10)
    except: pass

def menu():
    kb = {"inline_keyboard": [[{"text":"📈 NIFTY","callback_data":"NIFTY"},{"text":"🏦 BANKNIFTY","callback_data":"BANKNIFTY"}],[{"text":"🧪 TEST","callback_data":"TEST"}]]}
    send_tg("👇 *SELECT:*", kb)

def spot(sym):
    try:
        m = {"NIFTY":"^NSEI","BANKNIFTY":"^NSEBANK"}
        r = requests.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{m[sym]}?interval=1m&range=1d", headers={"User-Agent":"Mozilla/5.0"}, timeout=8).json()
        return float(r['chart']['result'][0]['meta']['regularMarketPrice'])
    except: return None

def real_price(sym, s):
    step = 100 if sym=="BANKNIFTY" else 50
    atm = round(s/step)*step
    enc = urllib.parse.quote(f"https://www.nseindia.com/api/option-chain-indices?symbol={sym}", safe='')
    try:
        r = requests.get(f"https://api.allorigins.win/raw?url={enc}", timeout=12)
        if r.status_code==200:
            for row in r.json()['records']['data']:
                if row.get('strikePrice')==atm and row.get('CE',{}).get('lastPrice',0)>2:
                    return row['CE']['lastPrice'], atm
    except: pass
    return None, atm

def fmt(sym, strike, price, s):
    if not price:
        return f"🔥 *{sym} {strike} CE*\n📍 SPOT: {s}\n\n⏳ Try again 10 sec"
    sl=int(price*0.75); t1=int(price*1.10); t2=int(price*1.20); t3=int(price*1.30)
    return f"🔥 *{sym} {strike} CE*\n\n💰 ENTRY: {price}\n🛑 SL: {sl}\n🎯 T1: {t1}\n🎯 T2: {t2}\n🎯 T3: {t3}\n\n📍 SPOT: {s}\n⏰ {datetime.now().strftime('%H:%M:%S')}"

def loop():
    time.sleep(8)
    send_tg("✅ *BOT LIVE*")
    menu()

def polling():
    off=0
    while True:
        try:
            r=requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?offset={off}&timeout=25", timeout=30).json()
            for u in r.get("result",[]):
                off=u["update_id"]+1
                cq=u.get("callback_query")
                if cq:
                    d=cq.get("data")
                    requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/answerCallbackQuery", data={"callback_query_id":cq["id"],"text":d})
                    if d=="TEST":
                        n=spot("NIFTY"); b=spot("BANKNIFTY")
                        send_tg(f"📊 NIFTY {n} ATM {round(n/50)*50}\n📊 BANK {b} ATM {round(b/100)*100}")
                    elif d in ["NIFTY","BANKNIFTY"]:
                        s=spot(d); p,st=real_price(d,s)
                        send_tg(fmt(d,st,p,s))
                    menu()
        except: time.sleep(3)

threading.Thread(target=loop, daemon=True).start()
threading.Thread(target=polling, daemon=True).start()

if __name__=="__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",10000)))
