import os, requests, time, threading, json
from datetime import datetime
from flask import Flask

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

app = Flask(__name__)

@app.route('/')
def home():
    return "BOT LIVE FIXED - " + datetime.now().strftime('%H:%M:%S')

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
    except Exception as e:
        print(f"TG Error: {e}")

def send_menu():
    keyboard = {
        "inline_keyboard": [
            [{"text": "📈 NIFTY", "callback_data": "NIFTY"}, {"text": "🏦 BANKNIFTY", "callback_data": "BANKNIFTY"}],
            [{"text": "🔥 SENSEX", "callback_data": "SENSEX"}, {"text": "🧪 TEST", "callback_data": "TEST"}]
        ]
    }
    send_tg("👇 *CLICK CHEY - PAKKA SIGNAL VASTADI:*", keyboard)

def get_spot_yahoo(symbol):
    try:
        y_map = {"NIFTY": "^NSEI", "BANKNIFTY": "^NSEBANK", "SENSEX": "^BSESN"}
        y_sym = y_map.get(symbol, "^NSEI")
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{y_sym}?interval=1m&range=1d"
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10).json()
        price = float(r['chart']['result'][0]['meta']['regularMarketPrice'])
        print(f"SPOT {symbol} = {price}")
        return price
    except Exception as e:
        print(f"Yahoo Error: {e}")
        return None

def get_nse_signals(symbol, spot):
    try:
        headers = {"User-Agent": "Mozilla/5.0 Chrome/120.0", "Accept": "application/json", "Referer": "https://www.nseindia.com/option-chain"}
        s = requests.Session()
        s.headers.update(headers)
        s.get("https://www.nseindia.com", timeout=15)
        time.sleep(1)
        s.get("https://www.nseindia.com/option-chain", timeout=15)
        time.sleep(1)
        url = f"https://www.nseindia.com/api/option-chain-indices?symbol={symbol}"
        r = s.get(url, timeout=15)
        print(f"NSE {symbol} Status {r.status_code}")
        if r.status_code!= 200:
            return []
        data = r.json()
        atm = round(spot / 50) * 50
        # ATM strike exact match
        for row in data['records']['data']:
            if row.get('strikePrice',0) == atm:
                ce = row.get('CE')
                pe = row.get('PE')
                # CE & PE rendu ivvu
                result = []
                if ce and ce.get('lastPrice',0) > 5:
                    result.append(("CE", atm, ce['lastPrice']))
                if pe and pe.get('lastPrice',0) > 5:
                    result.append(("PE", atm, pe['lastPrice']))
                if result:
                    print(f"FOUND {symbol} {result}")
                    return result
        # ATM dorakkapothe daggara strike
        for row in data['records']['data']:
            if abs(row.get('strikePrice',0) - atm) <= 50:
                ce = row.get('CE')
                if ce and ce.get('lastPrice',0) > 5:
                    return [("CE", row['strikePrice'], ce['lastPrice'])]
        return []
    except Exception as e:
        print(f"NSE Error {e}")
        return []

def format_signal(sym, typ, strike, price, spot):
    sl = int(price * 0.75) # -25%
    t1 = int(price * 1.10) # +10%
    t2 = int(price * 1.20) # +20%
    t3 = int(price * 1.30) # +30%
    return f"🔥 *{sym} {strike} {typ} LIVE*\n\n💰 ENTRY: {price}\n🛑 SL: {sl} (-25%)\n🎯 T1: {t1} (+10%)\n🎯 T2: {t2} (+20%)\n🎯 T3: {t3} (+30%)\n\n📍 SPOT: {spot}\n⏰ {datetime.now().strftime('%H:%M:%S')}"

def bot_loop():
    time.sleep(10)
    send_tg("✅ *BOT FIXED - Ippudu pakka signals vastai mowa!*\n\nPrati 2 mins ki NIFTY/BANKNIFTY check chestadi.")
    send_menu()
    while True:
        try:
            for sym in ["NIFTY", "BANKNIFTY"]:
                spot = get_spot_yahoo(sym)
                if not spot: continue
                sigs = get_nse_signals(sym, spot)
                for typ, strike, price in sigs:
                    send_tg(format_signal(sym, typ, strike, price, spot))
                    time.sleep(2)
            time.sleep(120) # 2 mins ki okasari
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
                    requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/answerCallbackQuery", data={"callback_query_id": cq["id"], "text": f"{data} loading..."})
                    if data=="TEST":
                        n=get_spot_yahoo("NIFTY")
                        send_tg(f"🧪 *BOT OK*\n\n📈 NIFTY SPOT: {n}\n\nIppudu NIFTY button nokku, signal vastadi!")
                    elif data in ["NIFTY","BANKNIFTY","SENSEX"]:
                        spot=get_spot_yahoo(data)
                        if not spot:
                            send_tg("⚠️ Spot fail, malli nokku")
                        else:
                            sigs=get_nse_signals(data, spot)
                            if sigs:
                                for typ,strike,price in sigs:
                                    send_tg(format_signal(data, typ, strike, price, spot))
                            else:
                                send_tg(f"📍 {data} SPOT {spot} - NSE data raledu, 1 min lo malli try chey")
                    send_menu()
            time.sleep(2)
        except Exception as e:
            print(f"Poll Error {e}"); time.sleep(5)

threading.Thread(target=bot_loop, daemon=True).start()
threading.Thread(target=tg_polling, daemon=True).start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
