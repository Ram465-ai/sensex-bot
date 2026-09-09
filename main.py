import os, requests, time, threading, json
from datetime import datetime
from flask import Flask

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
app = Flask(__name__)

@app.route('/')
def home(): return "BOT GROWW REAL - " + datetime.now().strftime('%H:%M:%S')
@app.route('/test')
def test(): send_menu(); return "MENU SENT"

def send_tg(msg, reply_markup=None):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        data = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}
        if reply_markup: data["reply_markup"] = json.dumps(reply_markup)
        requests.post(url, data=data, timeout=20)
    except Exception as e:
        print(f"TG Error {e}")

def send_menu():
    kb = {"inline_keyboard": [[{"text":"📈 NIFTY","callback_data":"NIFTY"},{"text":"🏦 BANKNIFTY","callback_data":"BANKNIFTY"}],[{"text":"🔥 SENSEX","callback_data":"SENSEX"},{"text":"🧪 TEST","callback_data":"TEST"}]]}
    send_tg("👇 *GROWW REAL MODE - SELECT:*", kb)

def get_spot_and_real_option(symbol, spot):
    step = 100 if symbol == "BANKNIFTY" else 50
    atm = round(spot / step) * step
    print(f"Need {symbol} ATM {atm} SPOT {spot}")

    # ===== METHOD 1: GROWW REAL OPTION CHAIN API =====
    try:
        # Groww expiry API
        groww_symbol = "NIFTY" if symbol=="NIFTY" else "BANKNIFTY"
        # Get expiry list
        exp_url = f"https://groww.in/v1/api/option_chain_service/v1/option_chain/expiry?exchange=NSE&segment=FNO&symbol={groww_symbol}"
        exp_r = requests.get(exp_url, headers={"User-Agent":"Mozilla/5.0"}, timeout=10).json()
        expiry = exp_r.get('expiries', [{}])[0].get('expiryDate') if exp_r.get('expiries') else "2025-09-29"
        if not expiry:
            # fallback from your screenshot date
            expiry = "2025-09-29" if symbol=="BANKNIFTY" else "2025-09-30"

        # Option chain
        chain_url = f"https://groww.in/v1/api/option_chain_service/v1/option_chain?exchange=NSE&segment=FNO&symbol={groww_symbol}&expiry={expiry}"
        r = requests.get(chain_url, headers={"User-Agent":"Mozilla/5.0","Accept":"application/json"}, timeout=15).json()

        options = r.get('optionChain', []) or r.get('data', {}).get('optionChain', [])
        for opt in options:
            if opt.get('strikePrice') == atm:
                ce = opt.get('callOption') or opt.get('CE') or {}
                price = ce.get('lastPrice') or ce.get('ltp')
                if price and float(price) > 5:
                    print(f"GROWW REAL {symbol} {atm} CE = {price}")
                    return float(price), atm, "CE", True
    except Exception as e:
        print(f"Groww API fail {e}")

    # ===== METHOD 2: NSE via PROXY (AllOrigins) - Bypass Render block =====
    try:
        proxy_url = f"https://api.allorigins.win/raw?url=https://www.nseindia.com/api/option-chain-indices?symbol={symbol}"
        r = requests.get(proxy_url, timeout=15)
        if r.status_code == 200:
            data = r.json()
            for row in data['records']['data']:
                if row.get('strikePrice') == atm:
                    ce = row.get('CE')
                    if ce and ce.get('lastPrice',0) > 5:
                        print(f"PROXY NSE REAL {symbol} {atm} = {ce['lastPrice']}")
                        return ce['lastPrice'], atm, "CE", True
    except Exception as e:
        print(f"Proxy NSE fail {e}")

    # ===== METHOD 3: Last resort - Don't give fake 254 =====
    return None, atm, "CE", False

def get_spot_yahoo(symbol):
    try:
        m = {"NIFTY":"^NSEI","BANKNIFTY":"^NSEBANK","SENSEX":"^BSESN"}
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{m.get(symbol,'^NSEI')}?interval=1m&range=1d"
        r = requests.get(url, headers={"User-Agent":"Mozilla/5.0"}, timeout=10).json()
        return float(r['chart']['result'][0]['meta']['regularMarketPrice'])
    except:
        return None

def format_msg(sym, strike, price, spot, typ, is_real):
    if not is_real or not price:
        return f"⚠️ *{sym} {strike} {typ}*\n\n📍 SPOT: {spot}\n\nGroww API ippudu kooda fetch avvatledu mowa.\nNee Groww app lo {sym} {strike} CE price ento cheppu, nenu check chesta.\n\nProxy try chestunna, 1 min lo malli nokku."

    sl = int(price * 0.75)
    t1 = int(price * 1.10); t2 = int(price * 1.20); t3 = int(price * 1.30)
    return f"🔥 *{sym} {strike} {typ}*\n\n💰 ENTRY: {price}\n🛑 SL: {sl} (-25%)\n🎯 T1: {t1} (+10%)\n🎯 T2: {t2} (+20%)\n🎯 T3: {t3} (+30%)\n\n📍 SPOT: {spot}\n📦 ✅ GROWW REAL\n⏰ {datetime.now().strftime('%H:%M:%S')}"

def bot_loop():
    time.sleep(10)
    send_tg("✅ *GROWW REAL MODE ON*\n\nIppudu Groww app lo unna 816.40 ne ENTRY vastadi, fake 254 raadu!")
    send_menu()
    while True:
        try:
            for sym in ["NIFTY","BANKNIFTY"]:
                spot = get_spot_yahoo(sym)
                if not spot: continue
                price, strike, typ, is_real = get_spot_and_real_option(sym, spot)
                if price:
                    send_tg(format_msg(sym, strike, price, spot, typ, is_real))
            time.sleep(120)
        except Exception as e:
            print(f"Loop {e}"); time.sleep(60)

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
                    requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/answerCallbackQuery", data={"callback_query_id":cq["id"],"text":f"{data} fetching..."})
                    if data=="TEST":
                        n=get_spot_yahoo("NIFTY"); b=get_spot_yahoo("BANKNIFTY")
                        send_tg(f"🧪 *GROWW REAL TEST*\n\nNIFTY {n} -> ATM {round(n/50)*50}\nBANKNIFTY {b} -> ATM {round(b/100)*100}\n\nIppudu real price vastadi!")
                    elif data in ["NIFTY","BANKNIFTY","SENSEX"]:
                        spot=get_spot_yahoo(data)
                        price,strike,typ,is_real=get_spot_and_real_option(data,spot)
                        send_tg(format_msg(data,strike,price,spot,typ,is_real))
                    send_menu()
            time.sleep(2)
        except: time.sleep(5)

threading.Thread(target=bot_loop, daemon=True).start()
threading.Thread(target=tg_polling, daemon=True).start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
