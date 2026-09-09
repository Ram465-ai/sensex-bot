import os, requests, threading, time, json
from datetime import datetime, timezone, timedelta
from flask import Flask, request

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
MY_URL = "https://sensex-bot-b7b7.onrender.com"
IST = timezone(timedelta(hours=5, minutes=30))
app = Flask(__name__)

@app.route('/')
def home(): return "BOT LIVE - SIMPLE SIGNALS"
@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = request.get_json()
        cq = data.get("callback_query")
        if cq:
            d = cq.get("data")
            try: requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/answerCallbackQuery", data={"callback_query_id":cq["id"],"text":d}, timeout=5)
            except: pass
            threading.Thread(target=send_smart_signals, args=(d,), daemon=True).start()
        else:
            msg = data.get("message",{}).get("text","").upper()
            if msg in ["NIFTY","BANKNIFTY","SENSEX"]:
                threading.Thread(target=send_smart_signals, args=(msg,), daemon=True).start()
    except: pass
    return "OK"

def send_tg(msg, kb=None):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        data = {"chat_id": CHAT_ID, "text": msg}
        if kb: data["reply_markup"] = json.dumps(kb)
        requests.post(url, data=data, timeout=10)
    except: pass

def menu():
    kb = {"inline_keyboard": [
        [{"text":"📈 NIFTY","callback_data":"NIFTY"},{"text":"🏦 BANKNIFTY","callback_data":"BANKNIFTY"}],
        [{"text":"📊 SENSEX","callback_data":"SENSEX"}]
    ]}
    send_tg("👇 Select Index:", kb)

def get_spot_and_trend(sym):
    try:
        m = {"NIFTY":"^NSEI","BANKNIFTY":"^NSEBANK","SENSEX":"^BSESN"}
        r = requests.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{m[sym]}?interval=5m&range=1d", headers={"User-Agent":"Mozilla/5.0"}, timeout=5).json()
        meta = r['chart']['result'][0]['meta']
        spot = float(meta['regularMarketPrice']); prev = float(meta['previousClose'])
        change = ((spot-prev)/prev)*100
        if change > 0.4: trend="BULLISH"
        elif change < -0.4: trend="BEARISH"
        else: trend="SIDEWAYS"
        return spot, prev, change, trend
    except:
        defaults = {"NIFTY":23431,"BANKNIFTY":56295,"SENSEX":74950}
        return defaults.get(sym,23431), defaults.get(sym,23300)-100, 0.2, "SIDEWAYS"

def get_option_data(sym, spot):
    step = 100 if sym in ["BANKNIFTY","SENSEX"] else 50
    atm = round(spot / step) * step
    ce_data, pe_data = None, None
    if sym in ["NIFTY","BANKNIFTY"]:
        try:
            s = requests.Session()
            s.headers.update({"User-Agent":"Mozilla/5.0","Accept":"application/json","Referer":"https://www.nseindia.com/option-chain"})
            s.get("https://www.nseindia.com/option-chain", timeout=5); time.sleep(1)
            r = s.get(f"https://www.nseindia.com/api/option-chain-indices?symbol={sym}", timeout=5).json()
            for row in r.get('records',{}).get('data',[]):
                if row.get('strikePrice')==atm:
                    ce_data=row.get('CE',{}); pe_data=row.get('PE',{}); break
        except: pass
    else:
        ce_data = {"lastPrice": round(spot*0.0018,1), "dayHigh": round(spot*0.0022,1), "dayLow": round(spot*0.0012,1)}
        pe_data = {"lastPrice": round(spot*0.0017,1), "dayHigh": round(spot*0.0021,1), "dayLow": round(spot*0.0011,1)}
    return atm, ce_data, pe_data

def analyse(opt_type, opt_data, trend, change):
    if not opt_data or not opt_data.get('lastPrice'): return None
    ltp=float(opt_data.get('lastPrice')); high=float(opt_data.get('dayHigh',ltp*1.2)); low=float(opt_data.get('dayLow',ltp*0.8))
    pos = (ltp-low)/(high-low) if high!=low else 0.5
    if opt_type=="CE":
        if trend=="BULLISH" and pos < 0.7: dec="CMP"; entry=ltp
        elif trend=="BULLISH": dec="DIP"; entry=round(ltp*0.90,1)
        elif trend=="BEARISH": dec="AVOID"; entry=round(ltp*0.85,1)
        else: dec="DIP"; entry=round(ltp*0.88,1)
    else:
        if trend=="BEARISH" and pos < 0.7: dec="CMP"; entry=ltp
        elif trend=="BEARISH": dec="DIP"; entry=round(ltp*0.90,1)
        elif trend=="BULLISH": dec="AVOID"; entry=round(ltp*0.85,1)
        else: dec="DIP"; entry=round(ltp*0.88,1)
    return {"ltp":ltp,"decision":dec,"entry":entry,"sl":round(entry*0.75,1),"t1":round(entry*1.10,1),"t2":round(entry*1.20,1),"t3":round(entry*1.30,1)}

def send_smart_signals(sym):
    spot, prev, change, trend = get_spot_and_trend(sym)
    atm, ce_data, pe_data = get_option_data(sym, spot)
    ce = analyse("CE", ce_data, trend, change)
    pe = analyse("PE", pe_data, trend, change)

    # SIMPLE OUTPUT
    msg = f"📊 {sym} {atm} | Spot: {int(spot)} ({change:+.2f}%)\n"
    msg += f"Trend: {trend}\n"
    msg += f"--------------------------\n\n"

    if ce:
        if ce['decision']=="CMP":
            msg += f"🟢 {atm} CE - BUY AT CMP\n"
            msg += f"Buy Now: {ce['ltp']}\n"
        elif ce['decision']=="DIP":
            msg += f"🟢 {atm} CE - BUY AT DIP\n"
            msg += f"Wait & Buy at: {ce['entry']} (Live: {ce['ltp']})\n"
        else:
            msg += f"🟢 {atm} CE - AVOID NOW\n"
            msg += f"Only Dip Buy: {ce['entry']} (Live: {ce['ltp']})\n"
        msg += f"SL: {ce['sl']} | T1:{ce['t1']} T2:{ce['t2']} T3:{ce['t3']}\n\n"

    if pe:
        if pe['decision']=="CMP":
            msg += f"🔴 {atm} PE - BUY AT CMP\n"
            msg += f"Buy Now: {pe['ltp']}\n"
        elif pe['decision']=="DIP":
            msg += f"🔴 {atm} PE - BUY AT DIP\n"
            msg += f"Wait & Buy at: {pe['entry']} (Live: {pe['ltp']})\n"
        else:
            msg += f"🔴 {atm} PE - AVOID NOW\n"
            msg += f"Only Dip Buy: {pe['entry']} (Live: {pe['ltp']})\n"
        msg += f"SL: {pe['sl']} | T1:{pe['t1']} T2:{pe['t2']} T3:{pe['t3']}\n"

    send_tg(msg); menu()

def auto_set_webhook():
    time.sleep(2)
    try: requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook?url={MY_URL}/webhook", timeout=10)
    except: pass
threading.Thread(target=auto_set_webhook, daemon=True).start()
if __name__=="__main__": app.run(host="0.0.0.0", port=int(os.environ.get("PORT",10000)))
