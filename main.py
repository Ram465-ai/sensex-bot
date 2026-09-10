import os, threading, requests, time, datetime
from flask import Flask, request

app = Flask(__name__)
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID", "")
MY_URL = os.environ.get("MY_URL", "")
HEADERS = {"User-Agent": "Mozilla/5.0"}

def send_tg(msg, chat_id=None):
    try:
        cid = str(chat_id or CHAT_ID)
        if not cid: return
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                      data={"chat_id": cid, "text": msg, "parse_mode": "Markdown"}, timeout=15)
    except: pass

def is_market_open():
    now = datetime.datetime.utcnow() + datetime.timedelta(hours=5, minutes=30)
    if now.weekday() >= 5: return False
    return (9,15) <= (now.hour, now.minute) <= (15,35)

def get_live_data(sym):
    spot=0; prev=0; atm=0
    y_map = {"NIFTY":"%5ENSEI","BANKNIFTY":"%5ENSEBANK","SENSEX":"%5EBSESN"}
    y_sym = y_map.get(sym,"%5ENSEI")
    try:
        yr = requests.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{y_sym}", headers=HEADERS, timeout=10).json()
        meta = yr['chart']['result'][0]['meta']
        spot=float(meta['regularMarketPrice']); prev=float(meta['previousClose'])
        gap=50 if sym=="NIFTY" else 100
        atm=int(round(spot/gap)*gap)
    except:
        return 0,0,0,None,None,None

    # YAHOO OPTIONS - Works on Render USA - Real Live
    try:
        oj = requests.get(f"https://query1.finance.yahoo.com/v7/finance/options/{y_sym}", headers=HEADERS, timeout=15).json()
        result = oj.get('optionChain',{}).get('result',[{}])[0]
        opts = result.get('options',[{}])[0]
        calls = opts.get('calls',[]); puts = opts.get('puts',[])
        ce_data=None; pe_data=None
        for c in calls:
            if int(c.get('strike',0))==atm:
                ce_data={"lastPrice":float(c.get('lastPrice',0) or c.get('bid',0))}
        for p in puts:
            if int(p.get('strike',0))==atm:
                pe_data={"lastPrice":float(p.get('lastPrice',0) or p.get('bid',0))}
        if ce_data and ce_data['lastPrice']>0:
            print(f"YAHOO LIVE {atm} CE:{ce_data['lastPrice']}")
            return spot,prev,atm,ce_data,pe_data,"YAHOO REAL LIVE"

        # If ATM not found, take nearest strike
        if calls:
            nearest = min(calls, key=lambda x: abs(x.get('strike',0)-atm))
            atm = nearest.get('strike',atm)
            ce_data={"lastPrice":float(nearest.get('lastPrice',0))}
            pe_nearest = min(puts, key=lambda x: abs(x.get('strike',0)-atm))
            pe_data={"lastPrice":float(pe_nearest.get('lastPrice',0))}
            return spot,prev,atm,ce_data,pe_data,"YAHOO REAL LIVE"
    except Exception as e:
        print(f"Yahoo opt fail {e}")

    return 0,0,0,None,None,None

def send_smart_signals(sym, chat_id=None, auto=False):
    spot,prev,atm,ce_data,pe_data,source = get_live_data(sym)
    if not ce_data:
        print(f"{sym} data not ready, skipping auto" if auto else f"{sym} BUSY")
        if not auto:
            send_tg(f"⏳ *{sym} data syncing* - try after 1 min /{sym.lower()}", chat_id)
        return False

    change=((spot-prev)/prev*100) if prev else 0
    trend="BULLISH" if change>0.6 else "BEARISH" if change<-0.6 else "SIDEWAYS"
    tag="🤖 AUTO" if auto else "📊"

    msg = f"{tag} *{sym} {atm} | Spot: {int(spot)} ({change:+.2f}%) ✅ {source}*\nTrend: {trend}\n--------------------------\n\n"
    msg += f"🟢 {atm} CE - {'CMP' if trend=='BULLISH' else 'DIP'}\nLive: {ce_data['lastPrice']} | Entry: {round(ce_data['lastPrice']*0.85,1)}\nSL:{round(ce_data['lastPrice']*0.6,1)} T1:{round(ce_data['lastPrice']*1.25,1)}\n\n"
    msg += f"🔴 {atm} PE - {'CMP' if trend=='BEARISH' else 'DIP'}\nLive: {pe_data['lastPrice']} | Entry: {round(pe_data['lastPrice']*0.85,1)}\nSL:{round(pe_data['lastPrice']*0.6,1)} T1:{round(pe_data['lastPrice']*1.25,1)}"
    send_tg(msg, chat_id)
    return True

def auto_loop():
    print("Auto loop started - 15 min")
    while True:
        try:
            if is_market_open() and CHAT_ID:
                print("Sending auto signals")
                for sym in ["NIFTY","BANKNIFTY","SENSEX"]:
                    send_smart_signals(sym, CHAT_ID, auto=True)
                    time.sleep(5)
                time.sleep(900) # 15 min
            else:
                time.sleep(60)
        except Exception as e:
            print(f"auto error {e}"); time.sleep(60)

@app.route('/')
def home(): return "Auto Bot Running"

@app.route('/webhook', methods=['POST'])
def webhook():
    data=request.get_json()
    if not data: return "ok"
    chat_id = data.get('message',{}).get('chat',{}).get('id')
    text = data.get('message',{}).get('text','').lower()
    if not chat_id: return "ok"
    # Save CHAT_ID if not set
    if chat_id:
        os.environ["CHAT_ID"]=str(chat_id)
    if 'sensex' in text: threading.Thread(target=send_smart_signals, args=("SENSEX",chat_id)).start()
    elif 'bank' in text: threading.Thread(target=send_smart_signals, args=("BANKNIFTY",chat_id)).start()
    else: threading.Thread(target=send_smart_signals, args=("NIFTY",chat_id)).start()
    return "ok"

def set_webhook():
    time.sleep(2)
    try:
        if MY_URL and BOT_TOKEN:
            requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook?url={MY_URL}/webhook", timeout=10)
    except: pass

threading.Thread(target=set_webhook, daemon=True).start()
threading.Thread(target=auto_loop, daemon=True).start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",10000)))
