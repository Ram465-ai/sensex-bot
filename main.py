import os, threading, requests, time, datetime
from flask import Flask, request

app = Flask(__name__)
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID", "")
MY_URL = os.environ.get("MY_URL", "")
DHAN_CLIENT_ID = os.environ.get("DHAN_CLIENT_ID")
DHAN_ACCESS_TOKEN = os.environ.get("DHAN_ACCESS_TOKEN")

def send_tg(msg, chat_id=None):
    try:
        cid = str(chat_id or CHAT_ID)
        if not cid: return
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                      data={"chat_id": cid, "text": msg, "parse_mode": "Markdown"}, timeout=15)
    except Exception as e: print(e)

def is_market_open():
    now = datetime.datetime.utcnow() + datetime.timedelta(hours=5, minutes=30)
    if now.weekday()>=5: return False
    return (9,15) <= (now.hour, now.minute) <= (15,35)

def get_live_data(sym):
    spot=0; prev=0; atm=0
    # 1. Spot from Yahoo
    try:
        y_map = {"NIFTY":"%5ENSEI","BANKNIFTY":"%5ENSEBANK","SENSEX":"%5EBSESN"}
        yr = requests.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{y_map.get(sym,'%5ENSEI')}", headers={"User-Agent":"Mozilla/5.0"}, timeout=10).json()
        meta = yr['chart']['result'][0]['meta']
        spot=float(meta['regularMarketPrice']); prev=float(meta['previousClose'])
        gap=50 if sym=="NIFTY" else 100 if sym=="BANKNIFTY" else 100
        atm=int(round(spot/gap)*gap)
    except: return 0,0,0,None,None,None

    # 2. DHAN REAL NSE LTP - Exact 155.65
    try:
        headers = {"access-token": DHAN_ACCESS_TOKEN, "client-id": DHAN_CLIENT_ID}
        scrip_map = {"NIFTY":13, "BANKNIFTY":25, "SENSEX":51}
        scrip = scrip_map.get(sym,13)

        # get expiry
        exp_r = requests.get(f"https://api.dhan.co/v2/optionchain/expirylist",
                             headers=headers,
                             params={"UnderlyingScrip": scrip, "UnderlyingSeg": "IDX_I"}, timeout=10)
        print(f"Dhan expiry {sym}: {exp_r.text[:200]}")
        exps = exp_r.json().get('data', [])
        if exps:
            expiry = exps[0]
            chain_r = requests.get("https://api.dhan.co/v2/optionchain",
                                   headers=headers,
                                   params={"UnderlyingScrip": scrip, "UnderlyingSeg": "IDX_I", "Expiry": expiry}, timeout=15)
            oc = chain_r.json().get('data',{}).get('oc',{})
            for strike_str, vals in oc.items():
                if int(float(strike_str))==atm:
                    ce_price = float(vals.get('ce',{}).get('last_price',0))
                    pe_price = float(vals.get('pe',{}).get('last_price',0))
                    if ce_price>0:
                        print(f"DHAN REAL {sym} {atm} CE {ce_price} PE {pe_price}")
                        return spot, prev, atm, {"lastPrice": ce_price}, {"lastPrice": pe_price}, f"DHAN REAL LIVE {expiry}"
    except Exception as e:
        print(f"Dhan error {e}")

    # 3. Fallback NSE Official
    try:
        sess = requests.Session()
        sess.headers.update({"User-Agent":"Mozilla/5.0"})
        sess.get("https://www.nseindia.com", timeout=5)
        nse_r = sess.get(f"https://www.nseindia.com/api/option-chain-indices?symbol={sym}", timeout=10)
        data = nse_r.json()
        for item in data['records']['data']:
            if item.get('strikePrice')==atm and item.get('expiryDate')==data['records']['expiryDates'][0]:
                ce=item.get('CE',{}); pe=item.get('PE',{})
                if ce.get('lastPrice',0)>0:
                    return spot, prev, atm, {"lastPrice": ce['lastPrice']}, {"lastPrice": pe['lastPrice']}, "NSE OFFICIAL LIVE"
    except: pass

    return 0,0,0,None,None,None

def send_smart_signals(sym, chat_id=None, auto=False):
    spot,prev,atm,ce,pe,source = get_live_data(sym)
    if not ce:
        if not auto: send_tg(f"⏳ *{sym} connecting Dhan...* Try again 30 sec /{sym.lower()}", chat_id)
        return False
    change=((spot-prev)/prev*100) if prev else 0
    trend="BULLISH 🚀" if change>0.6 else "BEARISH 🔻" if change<-0.6 else "SIDEWAYS ↔️"
    tag="🤖 AUTO" if auto else "📊"
    msg = f"{tag} *{sym} {atm} | {int(spot)} ({change:+.2f}%) ✅ {source}*\nTrend: {trend}\n\n🟢 {atm} CE: {ce['lastPrice']}\n🔴 {atm} PE: {pe['lastPrice']}\n\n_Strict SL | Target 1:2_"
    send_tg(msg, chat_id)
    return True

def auto_loop():
    while True:
        try:
            if is_market_open() and CHAT_ID:
                for s in ["NIFTY","BANKNIFTY","SENSEX"]:
                    send_smart_signals(s, CHAT_ID, auto=True)
                    time.sleep(5)
                time.sleep(600) # 10 min
            else: time.sleep(60)
        except Exception as e:
            print(e); time.sleep(60)

@app.route('/')
def home(): return "Dhan Bot Live"

@app.route('/webhook', methods=['POST'])
def webhook():
    data=request.get_json()
    if not data: return "ok"
    chat_id=data.get('message',{}).get('chat',{}).get('id')
    text=data.get('message',{}).get('text','').lower()
    if not chat_id: return "ok"
    os.environ["CHAT_ID"]=str(chat_id)
    if 'sensex' in text: threading.Thread(target=send_smart_signals, args=("SENSEX",chat_id)).start()
    elif 'bank' in text: threading.Thread(target=send_smart_signals, args=("BANKNIFTY",chat_id)).start()
    else: threading.Thread(target=send_smart_signals, args=("NIFTY",chat_id)).start()
    return "ok"

threading.Thread(target=auto_loop, daemon=True).start()
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",10000)))
