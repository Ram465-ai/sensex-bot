import os, requests, time, threading, json, random
from datetime import datetime
from flask import Flask

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

app = Flask(__name__)

@app.route('/')
def home():
    return "BOT LIVE FINAL - " + datetime.now().strftime('%H:%M:%S')

@app.route('/test')
def test():
    send_menu()
    return "MENU SENT"

def send_tg(msg, reply_markup=None):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        data = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}
        if reply_markup:
            data["reply_markup"] = json.dumps(reply_markup)
        requests.post(url, data=data, timeout=15)
        print(f"SENT: {msg[:60]}")
    except Exception as e:
        print(f"TG Error: {e}")

def send_menu():
    keyboard = {
        "inline_keyboard": [
            [{"text": "📈 NIFTY", "callback_data": "NIFTY"}, {"text": "🏦 BANKNIFTY", "callback_data": "BANKNIFTY"}],
            [{"text": "🔥 SENSEX", "callback_data": "SENSEX"}, {"text": "🧪 TEST", "callback_data": "TEST"}]
        ]
    }
    send_tg("👇 *SELECT INDEX FOR SIGNAL:*", keyboard)

# YAHOO - 100% WORKING SPOT
def get_spot_yahoo(symbol):
    try:
        y_map = {"NIFTY": "^NSEI", "BANKNIFTY": "^NSEBANK", "SENSEX": "^BSESN"}
        y_sym = y_map.get(symbol, "^NSEI")
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{y_sym}?interval=1m&range=1d"
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers, timeout=10).json()
        spot = r['chart']['result'][0]['meta']['regularMarketPrice']
        return float(spot)
    except Exception as e:
        print(f"Yahoo Error {symbol}: {e}")
        return None

# NSE CHAIN WITH 3 RETRY
def get_nse_signals(symbol, spot):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0",
            "Accept": "application/json",
            "Referer": "https://www.nseindia.com/option-chain"
        }
        s = requests.Session()
        s.headers.update(headers)
        s.get("https://www.nseindia.com", timeout=15)
        time.sleep(1)
        s.get("https://www.nseindia.com/option-chain", timeout=15)
        time.sleep(1)
        url = f"https://www.nseindia.com/api/option-chain-indices?symbol={symbol}"
        r = s.get(url, timeout=15)
        if r.status_code!= 200:
            time.sleep(2)
            r = s.get(url, timeout=15)
        if r.status_code!= 200:
            print(f"NSE FAIL {symbol} {r.status_code}")
            return []
        data = r.json()
        atm = round(spot / 100) * 100
        sigs=[]
        for row in data['records']['data']:
            if abs(row.get('strikePrice',0)-atm) <= 300:
                ce=row.get('CE'); pe=row.get('PE')
                if ce and ce.get('pChange',0)>2 and ce.get('lastPrice',0)>10:
                    sigs.append(("CE",row['strikePrice'],ce['lastPrice']))
                if pe and pe.get('pChange',0)>2 and pe.get('lastPrice',0)>10:
                    sigs.append(("PE",row['strikePrice'],pe['lastPrice']))
        return sigs
    except Exception as e:
        print(f"NSE Signal Error {symbol}: {e}")
        return []

def bot_loop():
    time.sleep(10)
    send_tg("✅ *BOT LIVE FINAL - AUTOMATIC MODE STARTED*\n\nPrati 3 mins ki signal auto ga vastadi!")
    time.sleep(2)
    send_menu()
    while True:
        try:
            for sym in ["NIFTY", "BANKNIFTY"]:
                spot = get_spot_yahoo(sym)
                if not spot:
                    continue
                print(f"AUTO CHECK {sym} {spot}")
                sigs = get_nse_signals(sym, spot)
                if sigs:
                    for typ, strike, price in sigs[:2]:
                        sl=int(price*0.70); t1=int(price*1.35); t2=int(price*1.8)
                        msg=f"🔥 *{sym} {strike} {typ} AUTO SIGNAL*\n\n💰 ENTRY: {price}\n🛑 SL: {sl}\n🎯 T1: {t1}\n🎯 T2: {t2}\n\n📍 SPOT: {spot}\n⏰ {datetime.now().strftime('%H:%M:%S')}"
                        send_tg(msg)
                        time.sleep(2)
                else:
                    # Even if no CE/PE signal, send SPOT update every 30 mins to prove alive
                    if random.randint(1,10)==1:
                        send_tg(f"📍 *{sym} LIVE: {spot}*\nNo strong CE/PE now, watching...")
            time.sleep(180) # 3 mins
        except Exception as e:
            print(f"Loop Error: {e}")
            time.sleep(60)

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
                        n_spot=get_spot_yahoo("NIFTY")
                        b_spot=get_spot_yahoo("BANKNIFTY")
                        send_tg(f"🧪 *TEST OK ✅*\n\n📈 NIFTY: {n_spot}\n🏦 BANKNIFTY: {b_spot}\n\nBot 100% LIVE")
                    elif data in ["NIFTY","BANKNIFTY","SENSEX"]:
                        spot=get_spot_yahoo(data)
                        if not spot:
                            send_tg(f"⚠️ {data} spot fail")
                            continue
                        sigs=get_nse_signals(data, spot) if data!="SENSEX" else []
                        if sigs:
                            typ,strike,price=sigs[0]
                            sl=int(price*0.70); t1=int(price*1.35)
                            send_tg(f"🔥 *{data} {strike} {typ}*\nENTRY {price} SL {sl} T1 {t1}\nSPOT {spot}")
                        else:
                            send_tg(f"📍 *{data} SPOT: {spot}*\nStrong signal ledu ippudu. Auto mode lo wait cheyyi.")
                    send_menu()
            time.sleep(2)
        except Exception as e:
            print(f"Poll Error {e}"); time.sleep(5)

threading.Thread(target=bot_loop, daemon=True).start()
threading.Thread(target=tg_polling, daemon=True).start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
