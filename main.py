import os, threading, requests, time, datetime
from flask import Flask, request

app = Flask(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID", "")
MY_URL = os.environ.get("MY_URL", "")
HEADERS = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}

def send_tg(msg, chat_id=None):
    try:
        cid = str(chat_id or CHAT_ID)
        if not cid: return
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                      data={"chat_id": cid, "text": msg, "parse_mode": "Markdown"}, timeout=15)
    except Exception as e:
        print(f"TG fail {e}")

def is_market_open():
    now = datetime.datetime.utcnow() + datetime.timedelta(hours=5, minutes=30)
    if now.weekday() >= 5: return False
    if now.hour < 9 or now.hour > 15: return False
    if now.hour == 9 and now.minute < 15: return False
    if now.hour == 15 and now.minute > 35: return False
    return True

def get_live_data(sym):
    spot = 0; prev = 0; atm = 0
    y_map = {"NIFTY": "%5ENSEI", "BANKNIFTY": "%5ENSEBANK", "SENSEX": "%5EBSESN"}
    y_sym = y_map.get(sym, "%5ENSEI")

    # 1. Spot from Yahoo
    try:
        yr = requests.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{y_sym}", headers=HEADERS, timeout=10).json()
        meta = yr['chart']['result'][0]['meta']
        spot = float(meta['regularMarketPrice'])
        prev = float(meta['previousClose'])
        gap = 50 if sym == "NIFTY" else 100
        atm = int(round(spot / gap) * gap)
    except:
        return 0,0,0,None,None,None

    # 2. Option LTP - 3 sources, most reliable first
    # Source A: Yahoo Options (works on Render)
    try:
        or_url = f"https://query1.finance.yahoo.com/v7/finance/options/{y_sym}"
        oj = requests.get(or_url, headers=HEADERS, timeout=15).json()
        opts = oj.get('optionChain', {}).get('result', [{}])[0].get('options', [{}])[0]
        calls = opts.get('calls', [])
        puts = opts.get('puts', [])
        ce_data = None; pe_data = None
        for c in calls:
            if int(c.get('strike', 0)) == atm:
                ce_data = {"lastPrice": float(c.get('lastPrice', 0) or c.get('bid', 0))}
        for p in puts:
            if int(p.get('strike', 0)) == atm:
                pe_data = {"lastPrice": float(p.get('lastPrice', 0) or p.get('bid', 0))}
        if ce_data and ce_data['lastPrice'] > 0:
            print(f"YAHOO REAL {atm} CE:{ce_data['lastPrice']}")
            return spot, prev, atm, ce_data, pe_data, "YAHOO REAL LIVE"
    except Exception as e:
        print(f"Yahoo opt fail: {e}")

    # Source B: Public proxies
    apis = [
        f"https://option-chain-data-cf.swarajsaaj.com/?symbol={sym}",
        f"https://nse-data.codebuckets.in/api/option-chain?type=Indices&symbol={sym}"
    ]
    for api_url in apis:
        try:
            r = requests.get(api_url, headers=HEADERS, timeout=15)
            if r.status_code!= 200: continue
            j = r.json()
            data_list = j.get('records', {}).get('data', []) or j.get('data', []) or []
            if isinstance(j.get('data'), dict):
                data_list = j['data'].get('records', {}).get('data', []) or j['data'].get('data', [])
            for d in data_list:
                if int(float(d.get('strikePrice', 0) or 0)) == atm:
                    ce = d.get('CE', {}); pe = d.get('PE', {})
                    if ce.get('lastPrice'):
                        return spot, prev, atm, {"lastPrice": float(ce['lastPrice'])}, {"lastPrice": float(pe['lastPrice'])}, "NSE REAL LIVE"
        except: continue

    return 0,0,0,None,None,None

def send_smart_signals(sym, chat_id=None, auto=False):
    spot, prev, atm, ce_data, pe_data, source = get_live_data(sym)
    if not ce_data:
        if not auto: # Only show BUSY if user manually typed
            send_tg(f"⚠️ *{sym} NSE BUSY* - Trying next cycle", chat_id)
        return False

    change = ((spot-prev)/prev*100) if prev else 0
    trend = "BULLISH" if change > 0.6 else "BEARISH" if change < -0.6 else "SIDEWAYS"
    tag = "🤖 AUTO" if auto else "📊"

    msg = f"{tag} *{sym} {atm} | Spot: {int(spot)} ({change:+.2f}%) ✅ {source}*\n"
    msg += f"Trend: {trend}\n--------------------------\n\n"
    msg += f"🟢 {atm} CE - {'CMP' if trend=='BULLISH' else 'DIP'}\nLive: {ce_data['lastPrice']} | Entry: {round(ce_data['lastPrice']*0.85,1)}\nSL:{round(ce_data['lastPrice']*0.7,1)} T1:{round(ce_data['lastPrice']*1.2,1)}\n\n"
    msg += f"🔴 {atm} PE - {'CMP' if trend=='BEARISH' else 'DIP'}\nLive: {pe_data['lastPrice']} | Entry: {round(pe_data['lastPrice']*0.85,1)}\nSL:{round(pe_data['lastPrice']*0.7,1)} T1:{round(pe_data['lastPrice']*1.2,1)}"
    send_tg(msg, chat_id)
    return True

# AUTO LOOP - Runs every 15 min during market
def auto_loop():
    print("Auto loop started")
    while True:
        try:
            if is_market_open() and CHAT_ID:
                print("Market open - sending auto signals")
                send_smart_signals("NIFTY", CHAT_ID, auto=True)
                time.sleep(5)
                send_smart_signals("BANKNIFTY", CHAT_ID, auto=True)
                time.sleep(5)
                send_smart_signals("SENSEX", CHAT_ID, auto=True)
                # Sleep 15 min
                time.sleep(900)
            else:
                time.sleep(60)
        except Exception as e:
            print(f"Auto loop error {e}")
            time.sleep(60)

@app.route('/')
def home(): return "Auto Bot Live"

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    if not data: return "ok"
    chat_id = None; text = ""
    if 'message' in data:
        chat_id = data['message']['chat']['id']
        text = data['message'].get('text','').lower()
        # Save chat_id automatically
        if chat_id and not CHAT_ID:
            os.environ["CHAT_ID"] = str(chat_id)
    elif 'callback_query' in data:
        chat_id = data['callback_query']['message']['chat']['id']
        text = data['callback_query']['data'].lower()
    if not chat_id: return "ok"
    if 'sensex' in text: threading.Thread(target=send_smart_signals, args=("SENSEX", chat_id)).start()
    elif 'bank' in text: threading.Thread(target=send_smart_signals, args=("BANKNIFTY", chat_id)).start()
    else: threading.Thread(target=send_smart_signals, args=("NIFTY", chat_id)).start()
    return "ok"

def set_webhook():
    time.sleep(3)
    try:
        if MY_URL:
            requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook?url={MY_URL}/webhook", timeout=10)
    except: pass

# Start threads
threading.Thread(target=set_webhook, daemon=True).start()
threading.Thread(target=auto_loop, daemon=True).start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
