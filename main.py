import os, threading, requests
from flask import Flask, request

app = Flask(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID", "")
HEADERS = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}

def send_tg(msg, chat_id=None):
    try:
        cid = str(chat_id or CHAT_ID)
        if not cid: return
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                      data={"chat_id": cid, "text": msg, "parse_mode": "Markdown"}, timeout=15)
    except: pass

def get_live_data(sym):
    spot = 0; prev = 0; atm = 0
    y_map = {"NIFTY": "%5ENSEI", "BANKNIFTY": "%5ENSEBANK", "SENSEX": "%5EBSESN"}
    y_sym = y_map.get(sym, "%5ENSEI")
    try:
        yr = requests.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{y_sym}", headers=HEADERS, timeout=10).json()
        meta = yr['chart']['result'][0]['meta']
        spot = float(meta['regularMarketPrice'])
        prev = float(meta['previousClose'])
        gap = 50 if sym == "NIFTY" else 100
        atm = int(round(spot / gap) * gap)
    except:
        return 0,0,0,None,None,None

    apis = [
        f"https://option-chain-data-cf.swarajsaaj.com/?symbol={sym}",
        f"https://nse-data.codebuckets.in/api/option-chain?type=Indices&symbol={sym}"
    ]
    for api_url in apis:
        try:
            r = requests.get(api_url, headers=HEADERS, timeout=15)
            if r.status_code!= 200: continue
            j = r.json()
            data_list = j.get('records', {}).get('data', []) or j.get('data', [])
            if not data_list and isinstance(j.get('data'), dict):
                data_list = j['data'].get('records', {}).get('data', []) or j['data'].get('data', [])
            for d in data_list:
                strike = d.get('strikePrice')
                if strike is None: continue
                if int(float(strike)) == atm:
                    ce = d.get('CE', {}); pe = d.get('PE', {})
                    ce_ltp = ce.get('lastPrice'); pe_ltp = pe.get('lastPrice')
                    if ce_ltp and float(ce_ltp) > 0:
                        print(f"FOUND REAL {api_url} {atm} CE:{ce_ltp} PE:{pe_ltp}")
                        return spot, prev, atm, {"lastPrice": float(ce_ltp)}, {"lastPrice": float(pe_ltp)}, "NSE REAL LIVE"
        except Exception as e:
            print(f"API {api_url} fail: {e}")
            continue
    return 0,0,0,None,None,None

def send_smart_signals(sym, chat_id=None):
    spot, prev, atm, ce_data, pe_data, source = get_live_data(sym)
    if not ce_data:
        send_tg(f"⚠️ *{sym} NSE BUSY - Try after 1 min* /{sym.lower()}", chat_id)
        return
    change = ((spot-prev)/prev*100) if prev else 0
    trend = "BULLISH" if change > 0.6 else "BEARISH" if change < -0.6 else "SIDEWAYS"
    msg = f"📊 *{sym} {atm} | Spot: {int(spot)} ({change:+.2f}%) ✅ {source}*\nTrend: {trend}\n\n🟢 {atm} CE Live: {ce_data['lastPrice']}\n🔴 {atm} PE Live: {pe_data['lastPrice']}"
    send_tg(msg, chat_id)

@app.route('/')
def home(): return "NSE REAL LIVE BOT OK"

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    if not data: return "ok"
    chat_id = None; text = ""
    if 'message' in data:
        chat_id = data['message']['chat']['id']
        text = data['message'].get('text','').lower()
    elif 'callback_query' in data:
        chat_id = data['callback_query']['message']['chat']['id']
        text = data['callback_query']['data'].lower()
    if not chat_id: return "ok"
    if 'sensex' in text: threading.Thread(target=send_smart_signals, args=("SENSEX", chat_id)).start()
    elif 'bank' in text: threading.Thread(target=send_smart_signals, args=("BANKNIFTY", chat_id)).start()
    else: threading.Thread(target=send_smart_signals, args=("NIFTY", chat_id)).start()
    return "ok"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
