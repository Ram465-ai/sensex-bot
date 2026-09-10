import os, time, threading, requests, datetime, json
from flask import Flask, request

app = Flask(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "8809989566:AAEWZZFly06YgQMYgbkM_PWyfANQRYIrBC0")
MY_URL = os.environ.get("MY_URL", "https://sensex-bot-b7b7.onrender.com")
CHAT_ID = os.environ.get("CHAT_ID", "YOUR_CHAT_ID_HERE") # Nee chat id ikkada pettu auto kosam

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": "https://www.nseindia.com/",
}

def get_ist_now():
    return datetime.datetime.utcnow() + datetime.timedelta(hours=5, minutes=30)

def send_tg(msg, chat_id=None):
    try:
        cid = chat_id or CHAT_ID or os.environ.get("CHAT_ID", "")
        if not cid:
            print("No CHAT_ID for auto signal")
            return
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": cid, "text": msg, "parse_mode": "Markdown"}, timeout=15)
    except Exception as e:
        print(f"TG Error: {e}")

def get_spot_and_trend(sym):
    spot, prev = 0, 0
    try:
        if sym == "SENSEX":
            r = requests.get("https://api.bseindia.com/BseIndiaAPI/api/Sensex/getSensexData", timeout=10).json()
            data = r[0] if isinstance(r, list) else r
            spot = float(str(data.get('CurrValue', '0')).replace(',',''))
            prev = float(str(data.get('PrevClose', spot)).replace(',',''))
        else:
            r = requests.get("https://www.nseindia.com/api/allIndices", headers=HEADERS, timeout=10).json()
            for d in r.get('data', []):
                if sym == "NIFTY" and d.get('index') == 'NIFTY 50':
                    spot = float(d.get('last', 0)); prev = float(d.get('previousClose', spot)); break
                if sym == "BANKNIFTY" and d.get('index') == 'NIFTY BANK':
                    spot = float(d.get('last', 0)); prev = float(d.get('previousClose', spot)); break
        if spot == 0: raise Exception("Spot 0")
    except Exception as e:
        print(f"Spot Error {sym}: {e}")
        spot = 74883 if sym == "SENSEX" else (23428 if sym == "NIFTY" else 51000)
        prev = spot - 150

    change = ((spot - prev) / prev * 100) if prev else 0
    trend = "BULLISH" if change > 0.6 else "BEARISH" if change < -0.6 else "SIDEWAYS"
    return spot, prev, change, trend

def get_option_data(sym, spot):
    now = get_ist_now()
    is_market = now.weekday() < 5 and ((now.hour==9 and now.minute>=15) or (9 < now.hour < 15) or (now.hour==15 and now.minute<=30))

    try:
        if sym == "SENSEX":
            url = "https://api.bseindia.com/BseIndiaAPI/api/OptionChain/w?scripcode=1&expiry=0"
            r = requests.get(url, headers=HEADERS, timeout=15).json()
            atm = int(round(spot / 100) * 100)
            for item in r.get('Data', []):
                if int(float(item.get('StrikePrice', 0))) == atm:
                    ce_ltp = float(item.get('CE_LTP', 0) or 0)
                    if ce_ltp > 5:
                        ce_data = {"lastPrice": ce_ltp, "dayHigh": float(item.get('CE_High', ce_ltp*1.2) or ce_ltp*1.2), "dayLow": float(item.get('CE_Low', ce_ltp*0.8) or ce_ltp*0.8)}
                        pe_ltp = float(item.get('PE_LTP', 0) or 0)
                        pe_data = {"lastPrice": pe_ltp, "dayHigh": float(item.get('PE_High', pe_ltp*1.2) or pe_ltp*1.2), "dayLow": float(item.get('PE_Low', pe_ltp*0.8) or pe_ltp*0.8)}
                        return atm, ce_data, pe_data, True
        else:
            symbol = "NIFTY" if sym == "NIFTY" else "BANKNIFTY"
            url = f"https://www.nseindia.com/api/option-chain-indices?symbol={symbol}"
            r = requests.get(url, headers=HEADERS, timeout=15).json()
            gap = 50 if sym == "NIFTY" else 100
            atm = int(round(spot / gap) * gap)
            for d in r.get('records', {}).get('data', []):
                if d.get('strikePrice') == atm:
                    ce = d.get('CE', {}); pe = d.get('PE', {})
                    if ce.get('lastPrice'):
                        ce_data = {"lastPrice": float(ce.get('lastPrice',0)), "dayHigh": float(ce.get('dayHigh', ce.get('lastPrice',0)*1.2)), "dayLow": float(ce.get('dayLow', ce.get('lastPrice',0)*0.8))}
                        pe_data = {"lastPrice": float(pe.get('lastPrice',0)), "dayHigh": float(pe.get('dayHigh', pe.get('lastPrice',0)*1.2)), "dayLow": float(pe.get('dayLow', pe.get('lastPrice',0)*0.8))}
                        return atm, ce_data, pe_data, True
    except Exception as e:
        print(f"Option Error {sym}: {e}")

    if is_market:
        return None, None, None, False
    else:
        mult = 0.0018 if sym=="SENSEX" else 0.0058
        atm = int(round(spot / 100) * 100) if sym=="SENSEX" else int(round(spot / 50) * 50)
        ce_data = {"lastPrice": round(spot*mult,1), "dayHigh": round(spot*(mult+0.0004),1), "dayLow": round(spot*(mult-0.0006),1)}
        pe_data = {"lastPrice": round(spot*(mult-0.0001),1), "dayHigh": round(spot*(mult+0.0003),1), "dayLow": round(spot*(mult-0.0007),1)}
        return atm, ce_data, pe_data, False

def analyse(opt_type, opt_data, trend):
    if not opt_data or not opt_data.get('lastPrice'): return None
    ltp=float(opt_data.get('lastPrice')); high=float(opt_data.get('dayHigh',ltp*1.2)); low=float(opt_data.get('dayLow',ltp*0.8))
    if ltp == 0: return None
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

def send_smart_signals(sym, chat_id=None):
    spot, prev, change, trend = get_spot_and_trend(sym)
    atm, ce_data, pe_data, is_real = get_option_data(sym, spot)

    if ce_data is None:
        send_tg(f"⏳ *{sym} LIVE WAITING*\nSpot: {int(spot)} ({change:+.2f}%)\nBSE data loading... 2 mins lo auto vastadi.\nTrend: {trend}", chat_id)
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
    send_tg(msg, chat_id)

def send_menu(chat_id=None):
    try:
        cid = chat_id or CHAT_ID
        if not cid: return
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        keyboard = {"inline_keyboard": [[{"text": "📈 NIFTY", "callback_data": "nifty"}, {"text": "🏦 BANKNIFTY", "callback_data": "banknifty"}], [{"text": "📊 SENSEX", "callback_data": "sensex"}]]}
        data = {"chat_id": cid, "text": "👇 Select Index:", "reply_markup": json.dumps(keyboard)}
        requests.post(url, data=data, timeout=10)
    except: pass

# ========= AUTOMATIC SIGNAL SENDER =========
def auto_signal_loop():
    sent_times = set()
    print("Auto signal loop started...")
    while True:
        try:
            now = get_ist_now()
            # Market hours only Mon-Fri 9:20 to 15:30
            if now.weekday() >= 5:
                time.sleep(3600); continue

            is_market = (now.hour==9 and now.minute>=20) or (9 < now.hour < 15) or (now.hour==15 and now.minute<=30)
            if not is_market:
                time.sleep(60); continue

            # Send at 9:20, 10:00, 11:00, 12:30, 14:00
            key = f"{now.hour}:{now.minute}"
            auto_slots = ["9:20", "10:0", "11:0", "12:30", "14:0"]

            if key in auto_slots and key not in sent_times:
                print(f"Auto sending signals at {key} IST")
                send_tg(f"🤖 *AUTO SIGNAL - {now.strftime('%I:%M %p')}*")
                time.sleep(2)
                send_smart_signals("SENSEX")
                time.sleep(3)
                send_smart_signals("NIFTY")
                sent_times.add(key)
                # clear old keys after 2 mins
                time.sleep(120)
                sent_times.clear()

            time.sleep(30)
        except Exception as e:
            print(f"Auto loop error: {e}")
            time.sleep(60)

@app.route('/')
def home(): return "Uday Bot LIVE + AUTO Running!"

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
        try:
            cb_id = data['callback_query']['id']
            requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/answerCallbackQuery", data={"callback_query_id": cb_id}, timeout=5)
        except: pass
    if not chat_id: return "ok"

    global CHAT_ID
    CHAT_ID = chat_id
    # save chat_id to env for auto
    os.environ["CHAT_ID"] = str(chat_id)

    if 'sensex' in text: threading.Thread(target=send_smart_signals, args=("SENSEX", chat_id)).start()
    elif 'nifty' in text: threading.Thread(target=send_smart_signals, args=("NIFTY", chat_id)).start()
    elif 'bank' in text: threading.Thread(target=send_smart_signals, args=("BANKNIFTY", chat_id)).start()
    else: threading.Thread(target=send_menu, args=(chat_id,)).start()
    return "ok"

def auto_set_webhook():
    time.sleep(2)
    try:
        requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook?url={MY_URL}/webhook", timeout=10)
    except: pass

threading.Thread(target=auto_set_webhook, daemon=True).start()
threading.Thread(target=auto_signal_loop, daemon=True).start()

if __name__=="__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",10000)))
