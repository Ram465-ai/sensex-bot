import os, requests, time, threading, json
from datetime import datetime
from flask import Flask

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

app = Flask(__name__)

@app.route('/')
def home():
    return "BOT LIVE 40% AIM - " + datetime.now().strftime('%H:%M:%S')

@app.route('/test')
def test():
    send_menu()
    return "MENU SENT OK"

def send_tg(msg, reply_markup=None):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        data = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}
        if reply_markup:
            data["reply_markup"] = json.dumps(reply_markup)
        requests.post(url, data=data, timeout=15)
        print(f"SENT: {msg[:80]}")
    except Exception as e:
        print(f"TG Error: {e}")

def send_menu():
    keyboard = {
        "inline_keyboard": [
            [{"text": "📈 NIFTY", "callback_data": "NIFTY"}, {"text": "🏦 BANKNIFTY", "callback_data": "BANKNIFTY"}],
            [{"text": "🔥 SENSEX", "callback_data": "SENSEX"}, {"text": "🧪 TEST", "callback_data": "TEST"}]
        ]
    }
    send_tg("👇 *SELECT INDEX (40% AIM):*", keyboard)

def get_spot_yahoo(symbol):
    try:
        y_map = {"NIFTY": "^NSEI", "BANKNIFTY": "^NSEBANK", "SENSEX": "^BSESN"}
        y_sym = y_map.get(symbol, "^NSEI")
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{y_sym}?interval=1m&range=1d"
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10).json()
        return float(r['chart']['result'][0]['meta']['regularMarketPrice'])
    except Exception as e:
        print(f"Yahoo Error {symbol}: {e}")
        return None

def get_momentum(symbol):
    try:
        y_map = {"NIFTY": "^NSEI", "BANKNIFTY": "^NSEBANK", "SENSEX": "^BSESN"}
        y_sym = y_map.get(symbol, "^NSEI")
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{y_sym}?interval=5m&range=1d"
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10).json()
        closes = r['chart']['result'][0]['indicators']['quote'][0]['close']
        closes = [c for c in closes if c]
        if len(closes) < 3: return 0
        # last 2 candles change
        pct = (closes[-1] - closes[-2]) / closes[-2] * 100
        return pct
    except:
        return 0

def get_nse_signals(symbol, spot):
    try:
        # 1. MOMENTUM FILTER - 0.12% kanna thakkuva unte skip
        mom = get_momentum(symbol)
        if abs(mom) < 0.12:
            print(f"SKIP {symbol} WEAK MOM {mom}")
            return []

        # 2. NSE FETCH
        headers = {"User-Agent": "Mozilla/5.0 Chrome/120.0", "Accept": "application/json", "Referer": "https://www.nseindia.com/option-chain"}
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
            print(f"NSE FAIL {symbol}")
            return []

        data = r.json()
        atm = round(spot / 50) * 50

        for row in data['records']['data']:
            if abs(row.get('strikePrice',0) - atm) <= 100:
                ce = row.get('CE')
                pe = row.get('PE')
                # CE - UP momentum
                if mom > 0 and ce and 80 <= ce.get('lastPrice',0) <= 280:
                    if ce.get('pChange',0) > 0 and ce.get('totalTradedVolume',0) > 1000:
                        return [("CE", row['strikePrice'], ce['lastPrice'], mom)]
                # PE - DOWN momentum
                if mom < 0 and pe and 80 <= pe.get('lastPrice',0) <= 280:
                    if pe.get('pChange',0) > 0 and pe.get('totalTradedVolume',0) > 1000:
                        return [("PE", row['strikePrice'], pe['lastPrice'], mom)]
        return []
    except Exception as e:
        print(f"NSE Filter Error {e}")
        return []

def format_signal(sym, typ, strike, price, spot, mom):
    sl = int(price * 0.65) # -35% SL
    t1 = int(price * 1.40) # +40%
    t2 = int(price * 1.55) # +55%
    return f"🔥 *{sym} {strike} {typ} - 40% AIM*\n\n💰 ENTRY: {price}\n🛑 SL: {sl} (-35%)\n🎯 T1: {t1} (+40%)\n🎯 T2: {t2} (+55%)\n\n📍 SPOT: {spot}\n📊 MOM: {mom:.2f}% {'🟢' if mom>0 else '🔴'}\n⏰ {datetime.now().strftime('%H:%M:%S')}\n\n_⚠️ Paper trade first, not financial advice_"

def bot_loop():
    time.sleep(10)
    send_tg("✅ *BOT LIVE - 40% PROFIT AIM MODE*\n\nFilter: Momentum + OI + 80-280rs premium\nRojuki 3-6 quality signals vastai!")
    time.sleep(2)
    send_menu()
    while True:
        try:
            for sym in ["NIFTY", "BANKNIFTY"]:
                spot = get_spot_yahoo(sym)
                if not spot: continue
                print(f"CHECK {sym} {spot}")
                sigs = get_nse_signals(sym, spot)
                if sigs:
                    for typ, strike, price, mom in sigs:
                        send_tg(format_signal(sym, typ, strike, price, spot, mom))
                        time.sleep(3)
            time.sleep(180)
        except Exception as e:
            print(f"Loop Error {e}")
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
                        n=get_spot_yahoo("NIFTY"); b=get_spot_yahoo("BANKNIFTY")
                        send_tg(f"🧪 *TEST OK - 40% MODE*\n\n📈 NIFTY: {n}\n🏦 BANKNIFTY: {b}\n\nBot ready!")
                    elif data in ["NIFTY","BANKNIFTY","SENSEX"]:
                        spot=get_spot_yahoo(data)
                        if not spot:
                            send_tg("⚠️ Spot fail, retry")
                            continue
                        sigs=get_nse_signals(data, spot) if data!="SENSEX" else []
                        if sigs:
                            typ,strike,price,mom=sigs[0]
                            send_tg(format_signal(data, typ, strike, price, spot, mom))
                        else:
                            send_tg(f"📍 *{data} SPOT: {spot}*\n\nIppudu strong momentum ledu, 40% kosam wait chestunna. Auto lo vastadi.")
                    send_menu()
            time.sleep(2)
        except Exception as e:
            print(f"Poll Error {e}"); time.sleep(5)

threading.Thread(target=bot_loop, daemon=True).start()
threading.Thread(target=tg_polling, daemon=True).start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
