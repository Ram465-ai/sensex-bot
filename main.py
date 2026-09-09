import os, requests, time, threading, json
from datetime import datetime
from flask import Flask

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

app = Flask(__name__)

@app.route('/')
def home():
    return "BOT LIVE REAL STRIKES - " + datetime.now().strftime('%H:%M:%S')

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
    send_tg("👇 *SELECT - REAL STRIKE REAL PRICE:*", keyboard)

def get_spot(symbol):
    try:
        m = {"NIFTY": "^NSEI", "BANKNIFTY": "^NSEBANK", "SENSEX": "^BSESN"}
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{m.get(symbol,'^NSEI')}?interval=1m&range=1d"
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10).json()
        price = float(r['chart']['result'][0]['meta']['regularMarketPrice'])
        print(f"SPOT {symbol} = {price}")
        return price
    except Exception as e:
        print(f"Spot fail {e}")
        return None

def get_real_price(symbol, spot):
    try:
        import cloudscraper
        scraper = cloudscraper.create_scraper(browser={'browser':'chrome','platform':'windows'})
        scraper.get("https://www.nseindia.com", timeout=15)
        time.sleep(1.5)
        scraper.get("https://www.nseindia.com/option-chain", timeout=15)
        time.sleep(1.5)
        url = f"https://www.nseindia.com/api/option-chain-indices?symbol={symbol}"
        r = scraper.get(url, timeout=15)
        print(f"NSE {symbol} Status {r.status_code} SPOT {spot}")

        if r.status_code == 200:
            data = r.json()
            step = 100 if symbol == "BANKNIFTY" else 50
            atm = round(spot / step) * step
            print(f"Calculated ATM {symbol} = {atm}")

            # Exact ATM
            for row in data['records']['data']:
                if row.get('strikePrice',0) == atm:
                    ce = row.get('CE')
                    if ce and ce.get('lastPrice',0) > 2:
                        print(f"FOUND REAL {symbol} {atm} CE = {ce['lastPrice']}")
                        return ce['lastPrice'], atm, "CE", True

            # Nearest strike
            for row in data['records']['data']:
                if abs(row.get('strikePrice',0) - atm) <= step:
                    ce = row.get('CE')
                    if ce and ce.get('lastPrice',0) > 2:
                        print(f"FOUND NEAREST {symbol} {row['strikePrice']} CE = {ce['lastPrice']}")
                        return ce['lastPrice'], row['strikePrice'], "CE", True
    except Exception as e:
        print(f"NSE Error {symbol}: {e}")

    # No fake 180/135 - return None to avoid wrong signal
    return None, None, None, False

def format_msg(sym, strike, price, spot, typ, is_real):
    sl = int(price * 0.75) # -25%
    t1 = int(price * 1.10) # +10%
    t2 = int(price * 1.20) # +20%
    t3 = int(price * 1.30) # +30%
    src = "✅ NSE REAL" if is_real else "⚠️ ESTIMATED"
    return f"🔥 *{sym} {strike} {typ}*\n\n💰 ENTRY: {price}\n🛑 SL: {sl} (-25%)\n🎯 T1: {t1} (+10%)\n🎯 T2: {t2} (+20%)\n🎯 T3: {t3} (+30%)\n\n📍 SPOT: {spot}\n📦 {src}\n⏰ {datetime.now().strftime('%H:%M:%S')}\n\n_Book 50% at T1_"

def bot_loop():
    time.sleep(10)
    send_tg("✅ *BOT FIXED - BANKNIFTY STRIKE CORRECTED*\n\nNIFTY = 50 step (23550)\nBANKNIFTY = 100 step (56700)\nReal price only, fake 180 raadu!")
    send_menu()
    while True:
        try:
            for sym in ["NIFTY", "BANKNIFTY"]:
                spot = get_spot(sym)
                if not spot: continue
                price, strike, typ, is_real = get_real_price(sym, spot)
                if price:
                    send_tg(format_msg(sym, strike, price, spot, typ, is_real))
                else:
                    print(f"Skipping {sym} - no real price to avoid fake 56650/180")
            time.sleep(180)
        except Exception as e:
            print(f"Loop Error {e}")
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
                        n = get_spot("NIFTY"); b = get_spot("BANKNIFTY")
                        send_tg(f"🧪 *REAL MODE TEST*\n\n📈 NIFTY SPOT: {n} -> ATM {round(n/50)*50}\n🏦 BANKNIFTY SPOT: {b} -> ATM {round(b/100)*100}\n\nCorrect strikes vastai!")
                    elif data in ["NIFTY", "BANKNIFTY", "SENSEX"]:
                        spot = get_spot(data)
                        price, strike, typ, is_real = get_real_price(data, spot)
                        if price:
                            send_tg(format_msg(data, strike, price, spot, typ, is_real))
                        else:
                            send_tg(f"📍 *{data} SPOT: {spot}*\n\nNSE block avtondi, 1 min lo malli nokku mowa. Thappu strike ivvanu.")
                    send_menu()
            time.sleep(2)
        except Exception as e:
            print(f"Poll Error {e}"); time.sleep(5)

threading.Thread(target=bot_loop, daemon=True).start()
threading.Thread(target=tg_polling, daemon=True).start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
