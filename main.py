import os, requests, time, threading, json, urllib.parse
from datetime import datetime
from flask import Flask

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
app = Flask(__name__)

@app.route('/')
def home(): return "BOT LIVE - " + datetime.now().strftime('%H:%M:%S')
@app.route('/test')
def test(): send_menu(); return "OK"

def send_tg(msg, reply_markup=None):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        data = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}
        if reply_markup: data["reply_markup"] = json.dumps(reply_markup)
        requests.post(url, data=data, timeout=20)
    except: pass

def send_menu():
    kb = {"inline_keyboard": [[{"text":"📈 NIFTY","callback_data":"NIFTY"},{"text":"🏦 BANKNIFTY","callback_data":"BANKNIFTY"}],[{"text":"🔥 SENSEX","callback_data":"SENSEX"},{"text":"🧪 TEST","callback_data":"TEST"}]]}
    send_tg("👇 *SELECT:*", kb)

def get_spot(symbol):
    try:
        m = {"NIFTY":"^NSEI","BANKNIFTY":"^NSEBANK"}
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{m.get(symbol,'^NSEI')}?interval=1m&range=1d"
        r = requests.get(url, headers={"User-Agent":"Mozilla/5.0"}, timeout=10).json()
        return float(r['chart']['result'][0]['meta']['regularMarketPrice'])
    except: return None

def get_real(symbol, spot):
    step = 100 if symbol=="BANKNIFTY" else 50
    atm = round(spot / step) * step
    nse_url = f"https://www.nseindia.com/api/option-chain-indices?symbol={symbol}"
    encoded = urllib.parse.quote(nse_url, safe='')
    try:
        url = f"https://api.allorigins.win/raw?url={encoded}"
        r = requests.get(url, timeout=15)
        if r.status_code == 200:
            data = r.json()
            for row in data['records']['data']:
                if row.get('strikePrice') == atm:
                    ce = row.get('CE')
                    if ce and ce.get('lastPrice',0) > 2:
                        return float(ce['lastPrice']), atm, "CE"
    except: pass
    try:
        url = f"https://api.allorigins.win/get?url={encoded}"
        r = requests.get(url, timeout=15).json()
        data = json.loads(r.get('contents','{}'))
        for row in data.get('records',{}).get('data',[]):
            if row.get('strikePrice') == atm:
                ce = row.get('CE')
                if ce and ce.get('lastPrice',0) > 2:
                    return float(ce['lastPrice']), atm, "CE"
    except: pass
    return None, atm, "CE"

def format_msg(sym, strike, price, spot, typ):
    if not price:
        return f"🔥 *{sym} {strike} {typ}*\n📍 SPOT: {spot}\n\n⏳ Fetching... try again in 10 sec"
    sl = int(price * 0.75); t1 = int(price * 1.10); t2 = int(price * 1.20); t3 = int(price * 1.30)
    return f"🔥 *{sym} {strike} {typ}*\n\n💰 ENTRY: {price}\n🛑 SL: {sl}\n🎯 T1: {t1}\n🎯 T2: {t2}\n🎯 T3: {t3}\n\n📍 SPOT: {spot}\n⏰ {datetime.now().strftime('%H:%M:%S')}"

def bot_loop():
    time.sleep(10)
    send_tg("✅ *BOT LIVE*")
    send_menu()
    while True:
        try:
            for sym in ["NIFTY","BANKNIFTY"]:
                spot = get_spot(sym)
                if not spot: continue
                price, strike, typ = get_real(sym, spot)
                if price: send_tg(format_msg(sym, strike, price, spot, typ))
            time.sleep(180)
        except: time.sleep(60)

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
                    requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/answerCallbackQuery", data={"callback_query_id":cq["id"],"text":f"{data}"})
                    if data=="TEST":
                        n=get_spot("NIFTY"); b=get_spot("BANKNIFTY")
                        send_tg(f"📊 NIFTY {n} | ATM {round(n/50)*50}\n📊 BANKNIFTY {b} | ATM {round(b/100)*100}")
                    elif data in ["NIFTY","BANKNIFTY","SENSEX"]:
                        spot=get_spot(data)
                        price,strike,typ=get_real(data,spot)
                        send_tg(format_msg(data,strike,price,spot,typ))
                    send_menu()
            time.sleep(2)
        except: time.sleep(5)

threading.Thread(target=bot_loop, daemon=True).start()
threading.Thread(target=tg_polling, daemon=True).start()
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
