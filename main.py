import os, requests, time, threading, json
from datetime import datetime
from flask import Flask

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
app = Flask(__name__)

@app.route('/')
def home(): return "BOT LIVE BYPASS - " + datetime.now().strftime('%H:%M:%S')
@app.route('/test')
def test(): send_menu(); return "MENU SENT"

def send_tg(msg, reply_markup=None):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        data = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}
        if reply_markup: data["reply_markup"] = json.dumps(reply_markup)
        requests.post(url, data=data, timeout=15)
    except: pass

def send_menu():
    keyboard = {"inline_keyboard": [[{"text":"📈 NIFTY","callback_data":"NIFTY"},{"text":"🏦 BANKNIFTY","callback_data":"BANKNIFTY"}],[{"text":"🔥 SENSEX","callback_data":"SENSEX"},{"text":"🧪 TEST","callback_data":"TEST"}]]}
    send_tg("👇 *SELECT - NSE BYPASS MODE:*", keyboard)

def get_spot(symbol):
    try:
        m = {"NIFTY":"^NSEI","BANKNIFTY":"^NSEBANK","SENSEX":"^BSESN"}
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{m.get(symbol,'^NSEI')}?interval=1m&range=1d"
        r = requests.get(url, headers={"User-Agent":"Mozilla/5.0"}, timeout=10).json()
        return float(r['chart']['result'][0]['meta']['regularMarketPrice'])
    except: return None

def get_real_price_BYPASS(symbol, spot):
    step = 100 if symbol == "BANKNIFTY" else 50
    atm = round(spot / step) * step
    print(f"Need {symbol} ATM {atm} for SPOT {spot}")

    # METHOD 1: NiftyTrader API - Render lo block kaadu!
    try:
        url = f"https://webapi.niftytrader.in/webapi/option/fatch-option-chain?symbol={symbol}&expiryDate="
        # For NIFTY/BANKNIFTY expiry auto
        r = requests.get(url, headers={"User-Agent":"Mozilla/5.0"}, timeout=10).json()
        print(f"NiftyTrader response {symbol}: {str(r)[:200]}")
        # Try parse
        for item in r.get('data', {}).get('options', []) if isinstance(r.get('data'), dict) else r.get('result', {}).get('optionChain', [])[:100]:
            strike = item.get('strikePrice') or item.get('strike_price')
            if strike == atm:
                price = item.get('lastPrice') or item.get('ltp') or item.get('last_price')
                if price and float(price) > 2:
                    return float(price), atm, "CE", True
    except Exception as e:
        print(f"NiftyTrader1 fail {e}")

    # METHOD 2: Another NiftyTrader endpoint
    try:
        url = f"https://api.niftytrader.in/api/option-chain?symbol={symbol}"
        r = requests.get(url, headers={"User-Agent":"Mozilla/5.0"}, timeout=10).json()
        print(f"API2 {symbol} got")
        if isinstance(r, dict) and 'data' in r:
            for row in r['data'][:100]:
                if row.get('strikePrice') == atm:
                    price = row.get('CE',{}).get('lastPrice') or row.get('lastPrice')
                    if price:
                        return float(price), atm, "CE", True
    except Exception as e:
        print(f"Method2 fail {e}")

    # METHOD 3: TrueData via nse bypass proxy
    try:
        import cloudscraper
        scraper = cloudscraper.create_scraper()
        scraper.get("https://www.nseindia.com", timeout=10)
        r = scraper.get(f"https://www.nseindia.com/api/option-chain-indices?symbol={symbol}", timeout=15)
        if r.status_code == 200:
            data = r.json()
            for row in data['records']['data']:
                if row.get('strikePrice') == atm:
                    ce = row.get('CE')
                    if ce and ce.get('lastPrice',0) > 2:
                        return ce['lastPrice'], atm, "CE", True
    except Exception as e:
        print(f"Cloudscraper final fail {e}")

    # LAST FALLBACK: Spot batti realistic price - fake 180 kaadu, spot% basis
    # NIFTY ATM ~ 0.55% of spot, BANKNIFTY ~ 0.45%
    est = int(spot * 0.0055) if symbol=="NIFTY" else int(spot * 0.0045)
    if est < 10: est = 50
    print(f"Using EST {est} for {symbol}")
    return float(est), atm, "CE", False

def format_msg(sym, strike, price, spot, typ, is_real):
    sl = int(price * 0.75); t1 = int(price * 1.10); t2 = int(price * 1.20); t3 = int(price * 1.30)
    src = "✅ REAL (Bypass)" if is_real else "⚠️ EST (NSE blocked)"
    return f"🔥 *{sym} {strike} {typ}*\n\n💰 ENTRY: {price}\n🛑 SL: {sl} (-25%)\n🎯 T1: {t1} (+10%)\n🎯 T2: {t2} (+20%)\n🎯 T3: {t3} (+30%)\n\n📍 SPOT: {spot}\n📦 {src}\n⏰ {datetime.now().strftime('%H:%M:%S')}"

def bot_loop():
    time.sleep(10)
    send_tg("✅ *BYPASS MODE ON - Ippudu block undadu!*")
    send_menu()
    while True:
        try:
            for sym in ["NIFTY","BANKNIFTY"]:
                spot = get_spot(sym)
                if not spot: continue
                price, strike, typ, is_real = get_real_price_BYPASS(sym, spot)
                if price:
                    send_tg(format_msg(sym, strike, price, spot, typ, is_real))
            time.sleep(180)
        except Exception as e:
            print(e); time.sleep(60)

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
                    requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/answerCallbackQuery", data={"callback_query_id":cq["id"],"text":f"{data}..."})
                    if data=="TEST":
                        n=get_spot("NIFTY"); b=get_spot("BANKNIFTY")
                        send_tg(f"🧪 *BYPASS TEST*\n\nNIFTY {n} -> {round(n/50)*50}\nBANKNIFTY {b} -> {round(b/100)*100}")
                    elif data in ["NIFTY","BANKNIFTY","SENSEX"]:
                        spot=get_spot(data)
                        price,strike,typ,is_real=get_real_price_BYPASS(data,spot)
                        send_tg(format_msg(data,strike,price,spot,typ,is_real))
                    send_menu()
            time.sleep(2)
        except Exception as e:
            print(f"Poll {e}"); time.sleep(5)

threading.Thread(target=bot_loop, daemon=True).start()
threading.Thread(target=tg_polling, daemon=True).start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
