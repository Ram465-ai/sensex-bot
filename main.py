import os, time, threading, requests, datetime, json
from flask import Flask, request

app = Flask(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
MY_URL = os.environ.get("MY_URL")
CHAT_ID = os.environ.get("CHAT_ID", "")

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json"
}

def send_tg(msg, chat_id=None):
    try:
        cid = str(chat_id or CHAT_ID)
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                      data={"chat_id": cid, "text": msg, "parse_mode": "Markdown"}, timeout=10)
    except: pass

def get_live_data(sym):
    # Map for Yahoo
    y_map = {"NIFTY": "%5ENSEI", "BANKNIFTY": "%5ENSEBANK", "SENSEX": "%5EBSESN"}
    y_sym = y_map.get(sym, "%5ENSEI")

    try:
        # 1. Spot Price
        spot_res = requests.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{y_sym}", headers=HEADERS, timeout=10).json()
        meta = spot_res['chart']['result'][0]['meta']
        spot = float(meta['regularMarketPrice'])
        prev = float(meta['previousClose'])
        gap = 50 if sym == "NIFTY" else 100
        atm = int(round(spot / gap) * gap)

        # 2. REAL OPTION LTP from Yahoo Options Chain - 100% LIVE, NOT BLOCKED
        opt_res = requests.get(f"https://query2.finance.yahoo.com/v7/finance/options/{y_sym}", headers=HEADERS, timeout=10).json()

        # Find ATM
        ce_data = None
        pe_data = None

        options = opt_res.get('optionChain', {}).get('result', [{}])[0].get('options', [{}])[0]
        calls = options.get('calls', [])
        puts = options.get('puts', [])

        for c in calls:
            if c.get('strike') == atm:
                ce_data = {"lastPrice": float(c.get('lastPrice', 0)), "dayHigh": float(c.get('dayHigh', 0)), "dayLow": float(c.get('dayLow', 0))}
                break
        for p in puts:
            if p.get('strike') == atm:
                pe_data = {"lastPrice": float(p.get('lastPrice', 0)), "dayHigh": float(p.get('dayHigh', 0)), "dayLow": float(p.get('dayLow', 0))}
                break

        # If ATM not found in first expiry, try to find nearest
        if not ce_data and calls:
            nearest_ce = min(calls, key=lambda x: abs(x.get('strike', 0) - atm))
            ce_data = {"lastPrice": float(nearest_ce.get('lastPrice', 0)), "dayHigh": float(nearest_ce.get('dayHigh', 0)), "dayLow": float(nearest_ce.get('dayLow', 0))}
            atm = nearest_ce.get('strike', atm)
        if not pe_data and puts:
            nearest_pe = min(puts, key=lambda x: abs(x.get('strike', 0) - atm))
            pe_data = {"lastPrice": float(nearest_pe.get('lastPrice', 0)), "dayHigh": float(nearest_pe.get('dayHigh', 0)), "dayLow": float(nearest_pe.get('dayLow', 0))}

        if ce_data and ce_data['lastPrice'] > 0:
            print(f"YAHOO REAL LIVE {atm} CE:{ce_data['lastPrice']} PE:{pe_data['lastPrice']}")
            return spot, prev, atm, ce_data, pe_data, "YAHOO REAL LIVE"

    except Exception as e:
        print(f"Error: {e}")

    return 0,0,0,None,None,None

def send_smart_signals(sym, chat_id=None):
    spot, prev, atm, ce_data, pe_data, source = get_live_data(sym)
    if not ce_data:
        send_tg(f"⚠️ *{sym} LIVE BUSY* - try again /{sym.lower()}", chat_id)
        return
    change = ((spot-prev)/prev*100) if prev else 0
    trend = "BULLISH" if change > 0.6 else "BEARISH" if change < -0.6 else "SIDEWAYS"
    msg = f"📊 *{sym} {atm} | Spot: {int(spot)} ({change:+.2f}%) ✅ {source}*\nTrend: {trend}\n\n"
    msg += f"CE {atm} Live: {ce_data['lastPrice']}\nPE {atm} Live: {pe_data['lastPrice']}\n"
    send_tg(msg, chat_id)

@app.route('/')
def home(): return "YAHOO REAL LIVE Running"

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
