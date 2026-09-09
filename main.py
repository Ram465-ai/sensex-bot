import os, requests, time, threading, json
from datetime import datetime
from flask import Flask

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

app = Flask(__name__)

@app.route('/')
def home():
    return "BOT LIVE - SL25 T10-30 - " + datetime.now().strftime('%H:%M:%S')

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
        print(f"TG Error {e}")

def send_menu():
    keyboard = {
        "inline_keyboard": [
            [{"text": "📈 NIFTY", "callback_data": "NIFTY"}, {"text": "🏦 BANKNIFTY", "callback_data": "BANKNIFTY"}],
            [{"text": "🔥 SENSEX", "callback_data": "SENSEX"}, {"text": "🧪 TEST", "callback_data": "TEST"}]
        ]
    }
    send_tg("👇 *SELECT - PAKKA SIGNAL VASTADI:*", keyboard)

def get_spot_yahoo(symbol):
    try:
        y_map = {"NIFTY": "^NSEI", "BANKNIFTY": "^NSEBANK", "SENSEX": "^BSESN"}
        y_sym = y_map.get(symbol, "^NSEI")
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{y_sym}?interval=1m&range=1d"
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10).json()
        price = float(r['chart']['result'][0]['meta']['regularMarketPrice'])
        return price
    except Exception as e:
        print(f"Yahoo fail {e}")
        return None

def get_signals(symbol, spot):
    # TRY REAL NSE
    try:
        headers = {"User-Agent": "Mozilla/5.0 Chrome/120.0", "Accept": "application/json", "Referer": "https://www.nseindia.com/option-chain"}
        s = requests.Session()
        s.headers.update(headers)
        s.get("https://www.nseindia.com", timeout=15)
        time.sleep(1)
        s.get("https://www.nseindia.com/option-chain", timeout=15)
        time.sleep(1)
        r = s.get(f"https://www.nseindia.com/api/option-chain-indices?symbol={symbol}", timeout=15)
        if r.status_code == 200:
            data = r.json()
            atm = round(spot / 50) * 50
            for row in data['records']['data']:
                if row.get('strikePrice',0) == atm:
                    ce = row.get('CE')
                    if ce and ce.get('lastPrice',0) > 5:
                        return [(ce.get('lastPrice',0), atm, True)]
                    pe = row.get('PE')
                    if pe and pe.get('lastPrice',0) > 5:
                        return [(pe.get('lastPrice',0), atm, True)]
    except Exception as e:
        print(f"NSE fail {e}")

    # FALLBACK - NSE blocked ayina signal ivvu
    atm = round(spot / 50) * 50
    est_price = 135 if symbol == "NIFTY" else 180
    return [(est_price, atm, False)]

def format_signal(sym, strike, price, spot, is_real):
    sl = int(price * 0.75) # -25%
    t1 = int(price * 1.10) # +10%
    t2 = int(price * 1.20) # +20%
    t3 = int(price * 1.30) # +30%
    src = "LIVE NSE" if is_real else "ESTIMATED (NSE blocked by Render)"
    return f"🔥 *{sym} {strike} CE*\n\n💰 ENTRY: {price}\n🛑 SL: {sl} (-25%)\n🎯 T1: {t1} (+10%)\n🎯 T2: {t2} (+20%)\n🎯 T3: {t3} (+30%)\n\n📍 SPOT: {spot}\n📦 {src}\n⏰ {datetime.now().strftime('%H:%M:%S')}\n\n_Book 50% at T1_"

def bot_loop():
    time.sleep(10)
    send_tg("✅ *BOT LIVE - SL 25% / T 10-30%*\n\nIppudu NSE block ayina kooda signals vastai mowa!")
    send_menu()
    while True:
        try:
            for sym in ["NIFTY", "BANKNIFTY"]:
                spot = get_spot_yahoo(sym)
                if not spot: continue
                sigs = get_signals(sym, spot)
                if sigs:
                    price, strike, is_real = sigs[0]
                    send_tg(format_signal(sym, strike, price, spot, is_real))
                    time.sleep(2)
            time.sleep(180)
        except Exception as e:
            print(f"Loop error {e}")
            time.sleep(60)

def tg_polling():
    offset = 0
    while True:
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?offset={offset}&timeout=30"
            r = requests.get(url, timeout=35).json()
            for upd in r.get("result", []):
                offset = upd["update_id"] + 1
                cq = upd.get("callback_query")
                if cq:
                    data = cq.get("data")
                    requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/answerCallbackQuery", data={"callback_query_id": cq["id"], "text": f"{data}..."})
                    if data == "TEST":
                        n = get_spot_yahoo("NIFTY")
                        send_tg(f"🧪 *BOT OK*\n\nNIFTY SPOT: {n}\n\nNIFTY button nokku, signal vastadi!")
                    elif data in ["NIFTY", "BANKNIFTY", "SENSEX"]:
                        spot = get_spot_yahoo(data)
                        if spot:
                            price, strike, is_real = get_signals(data, spot)[0]
                            send_tg(format_signal(data, strike, price, spot, is_real))
                        else:
                            send_tg("Spot fail, malli try chey")
                    send_menu()
            time.sleep(2)
        except Exception as e:
            print(f"Poll error {e}")
            time.sleep(5)

threading.Thread(target=bot_loop, daemon=True).start()
threading.Thread(target=tg_polling, daemon=True).start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
