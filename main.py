import os, time, threading, requests, datetime, json
from flask import Flask, request

app = Flask(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "8809989566:AAEWZZFly06YgQMYgbkM_PWyfANQRYIrBC0")
MY_URL = os.environ.get("MY_URL", "https://sensex-bot-b7b7.onrender.com")
CHAT_ID = os.environ.get("CHAT_ID", "")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/option-chain",
}

session = requests.Session()
session.headers.update(HEADERS)

def get_ist_now():
    return datetime.datetime.utcnow() + datetime.timedelta(hours=5, minutes=30)

def send_tg(msg, chat_id=None):
    try:
        cid = chat_id or CHAT_ID
        if not cid: return
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": cid, "text": msg, "parse_mode": "Markdown"}, timeout=15)
    except: pass

def get_spot_live(sym):
    # 100% LIVE SPOT
    try:
        if sym == "SENSEX":
            r = requests.get("https://api.bseindia.com/BseIndiaAPI/api/Sensex/getSensexData", timeout=10).json()
            data = r[0] if isinstance(r, list) else r
            spot = float(str(data.get('CurrValue', '0')).replace(',',''))
            prev = float(str(data.get('PrevClose', spot)).replace(',',''))
            return spot, prev
    except: pass

    try:
        # NSE spot with cookies
        session.get("https://www.nseindia.com", timeout=10)
        session.get("https://www.nseindia.com/option-chain", timeout=10)
        r = session.get("https://www.nseindia.com/api/allIndices", timeout=15).json()
        for d in r.get('data', []):
            if sym == "NIFTY" and d.get('index') == 'NIFTY 50':
                return float(d.get('last',0)), float(d.get('previousClose',0))
            if sym == "BANKNIFTY" and d.get('index') == 'NIFTY BANK':
                return float(d.get('last',0)), float(d.get('previousClose',0))
    except Exception as e:
        print(f"Spot error {sym}: {e}")
    return 0, 0

def get_option_live(sym, spot):
    atm = int(round(spot / 50) * 50) if sym!= "SENSEX" else int(round(spot / 100) * 100)

    # SOURCE 1: NSE OFFICIAL - 100% LIVE
    try:
        session.get("https://www.nseindia.com", timeout=10)
        time.sleep(1)
        url = f"https://www.nseindia.com/api/option-chain-indices?symbol={'NIFTY' if sym=='NIFTY' else 'BANKNIFTY'}"
        r = session.get(url, timeout=20).json()
        for d in r.get('records', {}).get('data', []):
            if d.get('strikePrice') == atm:
                ce = d.get('CE', {}); pe = d.get('PE', {})
                if ce.get('lastPrice') and pe.get('lastPrice'):
                    print(f"SOURCE 1 LIVE {sym} {atm} CE:{ce['lastPrice']} PE:{pe['lastPrice']}")
                    ce_data = {"lastPrice": float(ce['lastPrice']), "dayHigh": float(ce.get('dayHigh', ce['lastPrice']*1.3)), "dayLow": float(ce.get('dayLow', ce['lastPrice']*0.7))}
                    pe_data = {"lastPrice": float(pe['lastPrice']), "dayHigh": float(pe.get('dayHigh', pe['lastPrice']*1.3)), "dayLow": float(pe.get('dayLow', pe['lastPrice']*0.7))}
                    return atm, ce_data, pe_data, "NSE LIVE"
    except Exception as e:
        print(f"Source 1 fail: {e}")

    # SOURCE 2: NIFTYTRADER API - No Block
    try:
        # Backup API - no cookie needed
        url = f"https://webapi.niftytrader.in/webapi/option/fatch-option-chain?symbol={sym}"
        # Alternative public api
        r = requests.get("https://api.niftytrader.in/api/option-chain?symbol=NIFTY", headers=HEADERS, timeout=15).json()
        # parse according to response
        for item in r.get('data', []) or r.get('records', {}).get('data', []):
            if int(item.get('strikePrice',0)) == atm:
                ce = item.get('CE', {}); pe = item.get('PE', {})
                if ce.get('lastPrice'):
                    ce_data = {"lastPrice": float(ce['lastPrice']), "dayHigh": float(ce.get('dayHigh', ce['lastPrice']*1.3)), "dayLow": float(ce.get('dayLow', ce['lastPrice']*0.7))}
                    pe_data = {"lastPrice": float(pe['lastPrice']), "dayHigh": float(pe.get('dayHigh', pe['lastPrice']*1.3)), "dayLow": float(pe.get('dayLow', pe['lastPrice']*0.7))}
                    return atm, ce_data, pe_data, "NIFTYTRADER LIVE"
    except Exception as e:
        print(f"Source 2 fail: {e}")

    # SOURCE 3: SENSEX BSE
    if sym == "SENSEX":
        try:
            url = "https://api.bseindia.com/BseIndiaAPI/api/OptionChain/w?scripcode=1&expiry=0"
            r = requests.get(url, headers=HEADERS, timeout=15).json()
            for item in r.get('Data', []):
                if int(float(item.get('StrikePrice',0))) == atm:
                    ce_ltp = float(item.get('CE_LTP',0) or 0)
                    pe_ltp = float(item.get('PE_LTP',0) or 0)
                    if ce_ltp > 0:
                        ce_data = {"lastPrice": ce_ltp, "dayHigh": float(item.get('CE_High', ce_ltp*1.25)), "dayLow": float(item.get('CE_Low', ce_ltp*0.75))}
                        pe_data = {"lastPrice": pe_ltp, "dayHigh": float(item.get('PE_High', pe_ltp*1.25)), "dayLow": float(item.get('PE_Low', pe_ltp*0.75))}
                        return atm, ce_data, pe_data, "BSE LIVE"
        except: pass

    return None, None, None, None

def send_smart_signals(sym, chat_id=None):
    spot, prev = get_spot_live(sym)
    if spot == 0:
        send_tg(f"⚠️ *{sym} LIVE BUSY*\nNSE server busy. 30 sec lo /{sym.lower()} malli kottu.", chat_id)
        return

    change = ((spot - prev)/prev*100) if prev else 0
    trend = "BULLISH" if change > 0.6 else "BEARISH" if change < -0.6 else "SIDEWAYS"

    atm, ce_data, pe_data, source = get_option_live(sym, spot)

    if not ce_data:
        send_tg(f"⚠️ *{sym} {int(spot)} ({change:+.2f}%) - LIVE FETCHING...*\nOption chain loading. 30 sec lo /{sym.lower()} malli kottu.\nSource busy, fake data ivvatledu.", chat_id)
        return

    # CORRECT LOGIC - SIDEWAYS lo AVOID
    def get_decision(opt_type, ltp_data):
        ltp = ltp_data['lastPrice']
        if trend == "SIDEWAYS":
            return "AVOID", round(ltp*0.80,1), round(ltp*0.70,1), round(ltp*1.15,1), round(ltp*1.30,1), round(ltp*1.50,1)
        if opt_type == "CE":
            if trend == "BULLISH": return "CMP" if ltp < ltp_data['dayHigh']*0.7 else "DIP", round(ltp*0.92,1) if ltp >= ltp_data['dayHigh']*0.7 else ltp, round(ltp*0.70,1), round(ltp*1.15,1), round(ltp*1.30,1), round(ltp*1.50,1)
            else: return "AVOID", round(ltp*0.80,1), round(ltp*0.70,1), round(ltp*1.15,1), round(ltp*1.30,1), round(ltp*1.50,1)
        else:
            if trend == "BEARISH": return "CMP" if ltp < ltp_data['dayHigh']*0.7 else "DIP", round(ltp*0.92,1) if ltp >= ltp_data['dayHigh']*0.7 else ltp, round(ltp*0.70,1), round(ltp*1.15,1), round(ltp*1.30,1), round(ltp*1.50,1)
            else: return "AVOID", round(ltp*0.80,1), round(ltp*0.70,1), round(ltp*1.15,1), round(ltp*1.30,1), round(ltp*1.50,1)

    ce_dec, ce_entry, ce_sl, ce_t1, ce_t2, ce_t3 = get_decision("CE", ce_data)
    pe_dec, pe_entry, pe_sl, pe_t1, pe_t2, pe_t3 = get_decision("PE", pe_data)

    msg = f"📊 *{sym} {atm} | Spot: {int(spot)} ({change:+.2f}%) ✅ {source}*\n"
    msg += f"Trend: {trend}\n--------------------------\n\n"

    if ce_dec == "CMP": msg += f"🟢 {atm} CE - BUY AT CMP\nBuy Now: {ce_data['lastPrice']}\n"
    elif ce_dec == "DIP": msg += f"🟢 {atm} CE - BUY AT DIP\nWait: {ce_entry} (Live: {ce_data['lastPrice']})\n"
    else: msg += f"🔴 {atm} CE - AVOID NOW\nOnly Dip: {ce_entry} (Live: {ce_data['lastPrice']})\n"
    msg += f"SL: {ce_sl} | T1:{ce_t1} T2:{ce_t2} T3:{ce_t3}\n\n"

    if pe_dec == "CMP": msg += f"🔴 {atm} PE - BUY AT CMP\nBuy Now: {pe_data['lastPrice']}\n"
    elif pe_dec == "DIP": msg += f"🔴 {atm} PE - BUY AT DIP\nWait: {pe_entry} (Live: {pe_data['lastPrice']})\n"
    else: msg += f"🟢 {atm} PE - AVOID NOW\nOnly Dip: {pe_entry} (Live: {pe_data['lastPrice']})\n"
    msg += f"SL: {pe_sl} | T1:{pe_t1} T2:{pe_t2} T3:{pe_t3}\n"

    send_tg(msg, chat_id)
    # Menu
    try:
        keyboard = {"inline_keyboard": [[{"text": "📈 NIFTY", "callback_data": "nifty"}, {"text": "🏦 BANKNIFTY", "callback_data": "banknifty"}], [{"text": "📊 SENSEX", "callback_data": "sensex"}]]}
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", data={"chat_id": chat_id or CHAT_ID, "text": "👇 Next:", "reply_markup": json.dumps(keyboard)}, timeout=10)
    except: pass

def auto_signal_loop():
    while True:
        try:
            now = get_ist_now()
            if now.weekday() >= 5: time.sleep(3600); continue
            is_market = (now.hour==9 and now.minute>=20) or (9 < now.hour < 15) or (now.hour==15 and now.minute<=30)
            if not is_market: time.sleep(60); continue

            key = f"{now.hour}:{now.minute}"
            if key in ["9:20", "10:0", "11:0", "12:30", "14:0"]:
                send_tg(f"🤖 *AUTO LIVE SIGNAL - {now.strftime('%I:%M %p')}*")
                time.sleep(2)
                send_smart_signals("NIFTY")
                time.sleep(5)
                send_smart_signals("SENSEX")
                time.sleep(120)
        except: time.sleep(60)
        time.sleep(30)

@app.route('/')
def home(): return "100% LIVE Bot Running!"

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
        try: requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/answerCallbackQuery", data={"callback_query_id": data['callback_query']['id']}, timeout=5)
        except: pass
    if not chat_id: return "ok"
    global CHAT_ID; CHAT_ID = chat_id
    if 'sensex' in text: threading.Thread(target=send_smart_signals, args=("SENSEX", chat_id)).start()
    elif 'nifty' in text: threading.Thread(target=send_smart_signals, args=("NIFTY", chat_id)).start()
    elif 'bank' in text: threading.Thread(target=send_smart_signals, args=("BANKNIFTY", chat_id)).start()
    else:
        try:
            keyboard = {"inline_keyboard": [[{"text": "📈 NIFTY", "callback_data": "nifty"}, {"text": "🏦 BANKNIFTY", "callback_data": "banknifty"}], [{"text": "📊 SENSEX", "callback_data": "sensex"}]]}
            requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", data={"chat_id": chat_id, "text": "👇 Select:", "reply_markup": json.dumps(keyboard)}, timeout=10)
        except: pass
    return "ok"

def set_hook():
    time.sleep(2)
    try: requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook?url={MY_URL}/webhook", timeout=10)
    except: pass

threading.Thread(target=set_hook, daemon=True).start()
threading.Thread(target=auto_signal_loop, daemon=True).start()

if __name__=="__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",10000)))
