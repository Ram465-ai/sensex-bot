import os, time, threading, requests, datetime, json
from flask import Flask, request

app = Flask(__name__)
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
MY_URL = os.environ.get("MY_URL", "")
CHAT_ID = os.environ.get("CHAT_ID", "")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.nseindia.com/",
}

def send_tg(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                      data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=10)
    except Exception as e:
        print(f"TG Error: {e}")

def get_spot_and_trend(sym):
    spot, prev = 0, 0
    try:
        if sym == "SENSEX":
            # BSE SENSEX LIVE SPOT
            r = requests.get("https://api.bseindia.com/BseIndiaAPI/api/Sensex/getSensexData", timeout=10).json()
            # BSE returns list
            data = r[0] if isinstance(r, list) else r
            spot = float(data.get('CurrValue', 0) or data.get('curvalue', 0))
            prev = float(data.get('PrevClose', spot) or data.get('prevclose', spot))
        else:
            # NSE NIFTY LIVE SPOT
            r = requests.get("https://www.nseindia.com/api/allIndices", headers=HEADERS, timeout=10).json()
            for d in r.get('data', []):
                if d.get('index') == 'NIFTY 50':
                    spot = float(d.get('last', 0))
                    prev = float(d.get('previousClose', spot))
                    break
        if spot == 0: raise Exception("Spot 0")
    except Exception as e:
        print(f"Spot Error {sym}: {e}")
        # Last fallback only for spot
        spot = 74764 if sym == "SENSEX" else 23428
        prev = spot

    change = ((spot - prev) / prev * 100) if prev else 0
    if change > 0.6: trend = "BULLISH"
    elif change < -0.6: trend = "BEARISH"
    else: trend = "SIDEWAYS"
    return spot, prev, change, trend

def get_option_data(sym, spot):
    try:
        if sym == "SENSEX":
            # BSE SENSEX Option Chain LIVE
            # BSE scripcode 1 is SENSEX
            url = "https://api.bseindia.com/BseIndiaAPI/api/OptionChain/w?scripcode=1&expiry=0"
            r = requests.get(url, headers=HEADERS, timeout=10).json()
            # Find ATM
            atm = int(round(spot / 100) * 100)
            ce_data, pe_data = None, None
            for item in r.get('Data', []):
                if int(float(item.get('StrikePrice', 0))) == atm:
                    ce_data = {"lastPrice": float(item.get('CE_LTP', 0) or item.get('CElastPrice', 0)),
                               "dayHigh": float(item.get('CE_High', 0) or 0)*1.1 or float(item.get('CE_LTP',0))*1.2,
                               "dayLow": float(item.get('CE_Low', 0) or 0)*0.9 or float(item.get('CE_LTP',0))*0.8}
                    pe_data = {"lastPrice": float(item.get('PE_LTP', 0) or item.get('PElastPrice', 0)),
                               "dayHigh": float(item.get('PE_High', 0) or 0)*1.1 or float(item.get('PE_LTP',0))*1.2,
                               "dayLow": float(item.get('PE_Low', 0) or 0)*0.9 or float(item.get('PE_LTP',0))*0.8}
                    break
            if ce_data and ce_data['lastPrice'] > 0:
                return atm, ce_data, pe_data, True

        else: # NIFTY
            url = "https://www.nseindia.com/api/option-chain-indices?symbol=NIFTY"
            r = requests.get(url, headers=HEADERS, timeout=10).json()
            atm = int(round(spot / 50) * 50)
            rec = r.get('records', {})
            for d in rec.get('data', []):
                if d.get('strikePrice') == atm:
                    ce = d.get('CE', {})
                    pe = d.get('PE', {})
                    ce_data = {"lastPrice": float(ce.get('lastPrice', 0)), "dayHigh": float(ce.get('dayHigh', ce.get('lastPrice',0)*1.2)), "dayLow": float(ce.get('dayLow', ce.get('lastPrice',0)*0.8))}
                    pe_data = {"lastPrice": float(pe.get('lastPrice', 0)), "dayHigh": float(pe.get('dayHigh', pe.get('lastPrice',0)*1.2)), "dayLow": float(pe.get('dayLow', pe.get('lastPrice',0)*0.8))}
                    break
            if ce_data and ce_data['lastPrice'] > 0:
                return atm, ce_data, pe_data, True

    except Exception as e:
        print(f"BSE/NSE Option Error {sym}: {e}")

    # === MARKET TIME CHECK - NO FAKE DATA DURING MARKET ===
    now = datetime.datetime.now()
    is_market_time = now.weekday() < 5 and ((now.hour == 9 and now.minute >= 15) or (9 < now.hour < 15) or (now.hour == 15 and now.minute <= 30))

    if is_market_time:
        return None, None, None, False # Live data raaledu -> No signal
    else:
        # Market closed ayithe ne estimated ivvu
        mult = 0.0018 if sym == "SENSEX" else 0.0058
        atm = int(round(spot / 100) * 100) if sym == "SENSEX" else int(round(spot / 50) * 50)
        ce_data = {"lastPrice": round(spot*mult,1), "dayHigh": round(spot*(mult+0.0004),1), "dayLow": round(spot*(mult-0.0006),1)}
        pe_data = {"lastPrice": round(spot*(mult-0.0001),1), "dayHigh": round(spot*(mult+0.0003),1), "dayLow": round(spot*(mult-0.0007),1)}
        return atm, ce_data, pe_data, False

def analyse(opt_type, opt_data, trend):
    if not opt_data or not opt_data.get('lastPrice'): return None
    ltp=float(opt_data.get('lastPrice')); high=float(opt_data.get('dayHigh',ltp*1.2)); low=float(opt_data.get('dayLow',ltp*0.8))
    if ltp == 0: return None
    pos = (ltp-low)/(high-low) if high!=low and high!=0 else 0.5
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
    atm, ce_data, pe_data, is_real = get_option_data(sym, spot)

    if ce_data is None:
        send_tg(f"⏳ *{sym} LIVE WAITING*\nSpot: {int(spot)} ({change:+.2f}%)\nBSE/NSE data inka raaledu mowa, 1 min aagi malli /{sym.lower()} kottu.\nTrend: {trend}")
        return

    tag = "✅ REAL LIVE" if is_real else "📊 ESTIMATED (Mkt Closed)"
    msg = f"📊 *{sym} {atm} | Spot: {int(spot)} ({change:+.2f}%) {tag}*\nTrend: {trend}\n--------------------------\n\n"
    if ce_data:
        ce = analyse("CE", ce_data, trend)
        if ce:
            if ce['decision']=="CMP": msg += f"🟢 {atm} CE - BUY AT CMP\nBuy Now: {ce['ltp']}\n"
            elif ce['decision']=="DIP": msg += f"🟢 {atm} CE - BUY AT DIP\nWait & Buy at: {ce['entry']} (Live: {ce['ltp']})\n"
            else: msg += f"🔴 {atm} CE - AVOID NOW\nOnly Dip Buy: {ce['entry']} (Live: {ce['ltp']})\n"
            msg += f"SL: {ce['sl']} | T1:{ce['t1']} T2:{ce['t2']} T3:{ce['t3']}\n\n"
    if pe_data:
        pe = analyse("PE", pe_data, trend)
        if pe:
            if pe['decision']=="CMP": msg += f"🔴 {atm} PE - BUY AT CMP\nBuy Now: {pe['ltp']}\n"
            elif pe['decision']=="DIP": msg += f"🔴 {atm} PE - BUY AT DIP\nWait & Buy at: {pe['entry']} (Live: {pe['ltp']})\n"
            else: msg += f"🟢 {atm} PE - AVOID NOW\nOnly Dip Buy: {pe['entry']} (Live: {pe['ltp']})\n"
            msg += f"SL: {pe['sl']} | T1:{pe['t1']} T2:{pe['t2']} T3:{pe['t3']}\n"
    send_tg(msg)

@app.route('/')
def home(): return "Uday Bot LIVE Running!"

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    if not data or 'message' not in data: return "ok"
    chat_id = data['message']['chat']['id']
    text = data['message'].get('text','').lower()
    global CHAT_ID
    CHAT_ID = chat_id
    if 'sensex' in text: send_smart_signals("SENSEX")
    elif 'nifty' in text: send_smart_signals("NIFTY")
    elif 'bank' in text: send_smart_signals("BANKNIFTY")
    else: send_tg("Commands: /sensex /nifty /banknifty")
    return "ok"

def auto_set_webhook():
    time.sleep(2)
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook?url={MY_URL}/webhook"
        requests.get(url, timeout=10)
    except: pass

threading.Thread(target=auto_set_webhook, daemon=True).start()
if __name__=="__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",10000)))
