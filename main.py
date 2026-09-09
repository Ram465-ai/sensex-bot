import os, requests, threading, time, json
from datetime import datetime, timezone, timedelta
from flask import Flask, request

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
MY_URL = "https://sensex-bot-b7b7.onrender.com"
IST = timezone(timedelta(hours=5, minutes=30))
app = Flask(__name__)

@app.route('/')
def home(): return "BOT LIVE - SMART CE PE ANALYSER"
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
            if msg in ["NIFTY","BANKNIFTY"]:
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
    kb = {"inline_keyboard": [[{"text":"📈 NIFTY ANALYSIS","callback_data":"NIFTY"},{"text":"🏦 BANKNIFTY ANALYSIS","callback_data":"BANKNIFTY"}]]}
    send_tg("👇 Select for Smart Analysis:", kb)

def get_spot_and_trend(sym):
    try:
        m = {"NIFTY":"^NSEI","BANKNIFTY":"^NSEBANK"}
        r = requests.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{m[sym]}?interval=5m&range=1d", headers={"User-Agent":"Mozilla/5.0"}, timeout=5).json()
        meta = r['chart']['result'][0]['meta']
        spot = float(meta['regularMarketPrice']); prev = float(meta['previousClose'])
        change = ((spot-prev)/prev)*100
        if change > 0.4: trend="BULLISH"
        elif change < -0.4: trend="BEARISH"
        else: trend="SIDEWAYS"
        return spot, prev, change, trend
    except: return (23431.5 if sym=="NIFTY" else 56295.55), 23300, 0.2, "SIDEWAYS"

def get_option_data(sym, spot):
    atm = round(spot / (100 if sym=="BANKNIFTY" else 50)) * (100 if sym=="BANKNIFTY" else 50)
    ce_data, pe_data = None, None
    try:
        s = requests.Session()
        s.headers.update({"User-Agent":"Mozilla/5.0","Accept":"application/json","Referer":"https://www.nseindia.com/option-chain"})
        s.get("https://www.nseindia.com/option-chain", timeout=5); time.sleep(1)
        r = s.get(f"https://www.nseindia.com/api/option-chain-indices?symbol={sym}", timeout=5).json()
        for row in r.get('records',{}).get('data',[]):
            if row.get('strikePrice')==atm:
                ce_data=row.get('CE',{}); pe_data=row.get('PE',{}); break
    except: pass
    return atm, ce_data, pe_data

def analyse(opt_type, opt_data, trend, change):
    if not opt_data or not opt_data.get('lastPrice'): return None
    ltp=float(opt_data.get('lastPrice')); high=float(opt_data.get('dayHigh',ltp*1.2)); low=float(opt_data.get('dayLow',ltp*0.8))
    pos = (ltp-low)/(high-low) if high!=low else 0.5
    if opt_type=="CE":
        if trend=="BULLISH" and pos < 0.7: dec="BUY AT CMP"; reason=f"Spot Bullish ({change:+.2f}%) & CE at good level"; entry=ltp
        elif trend=="BULLISH": dec="BUY AT DIP"; reason=f"Bullish but CE near High ({pos*100:.0f}%), wait for dip"; entry=round(ltp*0.90)
        elif trend=="BEARISH": dec="AVOID / DIP ONLY"; reason=f"Spot Bearish ({change:+.2f}%), Avoid CE"; entry=round(ltp*0.85)
        else: dec="BUY AT DIP"; reason="Sideways, buy dip is better"; entry=round(ltp*0.88)
    else:
        if trend=="BEARISH" and pos < 0.7: dec="BUY AT CMP"; reason=f"Spot Bearish ({change:+.2f}%) & PE at good level"; entry=ltp
        elif trend=="BEARISH": dec="BUY AT DIP"; reason=f"Bearish but PE near High ({pos*100:.0f}%), wait for dip"; entry=round(ltp*0.90)
        elif trend=="BULLISH": dec="AVOID / DIP ONLY"; reason=f"Spot Bullish ({change:+.2f}%), Avoid PE"; entry=round(ltp*0.85)
        else: dec="BUY AT DIP"; reason="Sideways, buy dip is better"; entry=round(ltp*0.88)
    return {"ltp":ltp,"high":high,"low":low,"decision":dec,"reason":reason,"entry":entry,"sl":int(entry*0.75),"t1":int(entry*1.10),"t2":int(entry*1.20),"t3":int(entry*1.30)}

def send_smart_signals(sym):
    spot, prev, change, trend = get_spot_and_trend(sym)
    atm, ce_data, pe_data = get_option_data(sym, spot)
    now = datetime.now(IST).strftime('%H:%M:%S')
    if not ce_data and not pe_data:
        send_tg(f"⚠️ {sym} {atm} - Market closed\nSpot: {spot} ({change:+.2f}%)\n{now} IST"); menu(); return
    ce = analyse("CE", ce_data, trend, change); pe = analyse("PE", pe_data, trend, change)
    msg = f"📊 {sym} SMART ANALYSIS\nSpot: {spot} ({change:+.2f}%) Prev: {prev}\nTrend: {trend} | Strike: {atm} | {now} IST\n--------------------------\n\n"
    if ce: msg+=f"🟢 {atm} CE - {ce['decision']}\nLive: {ce['ltp']} H:{ce['high']} L:{ce['low']}\nEntry: {ce['entry']} SL:{ce['sl']} T1:{ce['t1']} T2:{ce['t2']} T3:{ce['t3']}\nReason: {ce['reason']}\n\n"
    if pe: msg+=f"🔴 {atm} PE - {pe['decision']}\nLive: {pe['ltp']} H:{pe['high']} L:{pe['low']}\nEntry: {pe['entry']} SL:{pe['sl']} T1:{pe['t1']} T2:{pe['t2']} T3:{pe['t3']}\nReason: {pe['reason']}\n"
    send_tg(msg); menu()

def auto_set_webhook():
    time.sleep(2)
    try: requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook?url={MY_URL}/webhook", timeout=10)
    except: pass
threading.Thread(target=auto_set_webhook, daemon=True).start()
if __name__=="__main__": app.run(host="0.0.0.0", port=int(os.environ.get("PORT",10000)))
