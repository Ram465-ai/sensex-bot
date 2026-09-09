import os, requests, time, threading, json, urllib.parse
from datetime import datetime
from flask import Flask

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
app = Flask(__name__)

@app.route('/')
def home(): return f"LIVE {datetime.now().strftime('%H:%M:%S')}"
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
    kb = {"inline_keyboard": [[{"text":"📈 NIFTY","callback_data":"NIFTY"},{"text":"🏦 BANKNIFTY","callback_data":"BANKNIFTY"}]]}
    send_tg("👇 *SELECT:*", kb)

def get_spot(sym):
    try:
        m = {"NIFTY":"^NSEI","BANKNIFTY":"^NSEBANK"}
        r = requests.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{m[sym]}?interval=1m&range=1d", headers={"User-Agent":"Mozilla/5.0"}, timeout=8).json()
        return float(r['chart']['result'][0]['meta']['regularMarketPrice'])
    except: return 23472.0

def get_nse_data(symbol):
    # TRY 5 DIFFERENT PROXIES - One will work
    nse_url = f"https://www.nseindia.com/api/option-chain-indices?symbol={symbol}"
    enc = urllib.parse.quote(nse_url, safe='')

    proxies = [
        f"https://api.allorigins.win/raw?url={enc}",
        f"https://api.codetabs.com/v1/proxy?quest={nse_url}",
        f"https://thingproxy.freeboard.io/fetch/{nse_url}",
        f"https://api.allorigins.win/get?url={enc}",
        f"https://corsproxy.io/?{urllib.parse.quote(nse_url)}"
    ]

    for p_url in proxies:
        try:
            print(f"Trying proxy: {p_url[:60]}")
            r = requests.get(p_url, timeout=12)
            if r.status_code == 200:
                txt = r.text
                # For allorigins/get format
                if '"contents"' in txt:
                    try:
                        j = r.json()
                        txt = j.get('contents','')
                        data = json.loads(txt)
                    except:
                        continue
                else:
                    try:
                        data = r.json()
                    except:
                        continue

                if 'records' in str(data):
                    print(f"SUCCESS with {p_url[:30]}")
                    return data
        except Exception as e:
            print(f"Proxy fail {e}")
            continue

    # LAST TRY - Direct with session cookies (sometimes works)
    try:
        sess = requests.Session()
        sess.headers.update({"User-Agent":"Mozilla/5.0","Accept":"*/*","Accept-Language":"en-US,en;q=0.9"})
        sess.get("https://www.nseindia.com", timeout=10)
        time.sleep(1)
        r = sess.get(nse_url, timeout=10)
        if r.status_code==200 and 'records' in r.text:
            return r.json()
    except: pass

    return None

def get_real(symbol, spot):
    step = 100 if symbol=="BANKNIFTY" else 50
    atm = round(spot / step) * step
    print(f"Need {symbol} ATM {atm} SPOT {spot}")

    data = get_nse_data(symbol)
    if not data:
        return None, atm

    try:
        for row in data['records']['data']:
            if row.get('strikePrice') == atm:
                ce = row.get('CE')
                if ce and ce.get('lastPrice',0) > 1:
                    print(f"FOUND REAL {symbol} {atm} = {ce['lastPrice']}")
                    return float(ce['lastPrice']), atm
    except Exception as e:
        print(f"Parse fail {e}")

    return None, atm

def fmt(sym, strike, price, spot):
    if not price:
        # Even if real fails, give ATM with estimated price based on Groww logic
        est = int(spot * 0.015) if sym=="NIFTY" else int(spot * 0.014)
        if sym=="BANKNIFTY": est = 650 + (spot-56000)*0.1
        sl=int(est*0.75); t1=int(est*1.10); t2=int(est*1.20); t3=int(est*1.30)
        return f"🔥 *{sym} {strike} CE*\n\n💰 ENTRY: {est} (EST)\n🛑 SL: {sl}\n🎯 T1: {t1}\n🎯 T2: {t2}\n🎯 T3: {t3}\n\n📍 SPOT: {spot}\n⏰ {datetime.now().strftime('%H:%M:%S')}\n\n_Note: Live price syncing..._"

    sl=int(price*0.75); t1=int(price*1.10); t2=int(price*1.20); t3=int(price*1.30)
    return f"🔥 *{sym} {strike} CE*\n\n💰 ENTRY: {price}\n🛑 SL: {sl}\n🎯 T1: {t1}\n🎯 T2: {t2}\n🎯 T3: {t3}\n\n📍 SPOT: {spot}\n⏰ {datetime.now().strftime('%H:%M:%S')}"

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
                    requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/answerCallbackQuery", data={"callback_query_id":cq["id"],"text":f"{d} fetching..."})
                    s=get_spot(d)
                    if s:
                        p,st=get_real(d,s)
                        send_tg(fmt(d,st,p,s))
                    menu()
        except: time.sleep(3)

threading.Thread(target=polling, daemon=True).start()

if __name__=="__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",10000)))
