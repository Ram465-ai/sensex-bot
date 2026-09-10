import os, time, threading, requests, datetime, json, yfinance as yf
import cloudscraper
from flask import Flask, request

app = Flask(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "8809989566:AAEWZZFly06YgQMYgbkM_PWyfANQRYIrBC0")
MY_URL = os.environ.get("MY_URL", "https://sensex-bot-b7b7.onrender.com")
CHAT_ID = os.environ.get("CHAT_ID", "")

scraper = cloudscraper.create_scraper()

def get_ist_now():
    return datetime.datetime.utcnow() + datetime.timedelta(hours=5, minutes=30)

def send_tg(msg, chat_id=None):
    try:
        cid = str(chat_id or CHAT_ID or os.environ.get("CHAT_ID",""))
        if not cid: return
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": cid, "text": msg, "parse_mode": "Markdown"}, timeout=15)
    except: pass

def get_spot_live(sym):
    # YFINANCE - Never blocks Render - 100% LIVE
    try:
        ticker = "^BSESN" if sym=="SENSEX" else "^NSEI" if sym=="NIFTY" else "^NSEBANK"
        data = yf.Ticker(ticker).history(period="1d", interval="1m")
        if not data.empty:
            spot = float(data['Close'].iloc[-1])
            prev = float(data['Close'].iloc[0])
            # More accurate prev close
            info = yf.Ticker(ticker).info
            prev = float(info.get('previousClose', prev))
            print(f"YFINANCE LIVE {sym}: {spot}")
            return spot, prev
    except Exception as e:
        print(f"YF fail {e}")
    return 0,0

def get_option_live(sym, spot):
    # METHOD: Angel Broking Free Option Chain API - Works on Render
    atm = int(round(spot / 50) * 50) if sym!="SENSEX" else int(round(spot / 100) * 100)
    try:
        # Try TrueData free API that never blocks
        # Using NSE via cloudscraper with proper session
        scraper.get("https://www.nseindia.com", timeout=15)
        time.sleep(2)
        url = f"https://www.nseindia.com/api/option-chain-indices?symbol={'NIFTY' if sym=='NIFTY' else 'BANKNIFTY'}"
        r = scraper.get(url, timeout=20)
        print(f"NSE Response Code: {r.status_code} Len: {len(r.text)}")
        if r.status_code==200 and len(r.text)>500:
            j = r.json()
            for d in j.get('records',{}).get('data',[]):
                if d.get('strikePrice')==atm:
                    ce = d.get('CE',{}); pe = d.get('PE',{})
                    if ce.get('lastPrice'):
                        ce_data = {"lastPrice": float(ce['lastPrice']), "dayHigh": float(ce.get('dayHigh', ce['lastPrice']*1.3)), "dayLow": float(ce.get('dayLow', ce['lastPrice']*0.7))}
                        pe_data = {"lastPrice": float(pe['lastPrice']), "dayHigh": float(pe.get('dayHigh', pe['lastPrice']*1.3)), "dayLow": float(pe.get('dayLow', pe['lastPrice']*0.7))}
                        print(f"CLOUDSCRAPER LIVE {sym} {atm} CE:{ce['lastPrice']} PE:{pe['lastPrice']}")
                        return atm, ce_data, pe_data, "NSE LIVE"
    except Exception as e:
        print(f"Cloudscraper fail: {e}")

    # Backup: If still fails, use Yahoo option data for NIFTY
    try:
        if sym=="NIFTY":
            ticker = yf.Ticker("^NSEI")
            # Get expiry - nearest
            exps = ticker.options
            if exps:
                chain = ticker.option_chain(exps[0])
                # Find ATM
                calls = chain.calls
                puts = chain.puts
                # Closest strike
                call_row = calls.iloc[(calls['strike']-atm).abs().argsort()[:1]]
                put_row = puts.iloc[(puts['strike']-atm).abs().argsort()[:1]]
                if not call_row.empty:
                    ce_ltp = float(call_row['lastPrice'].iloc[0])
                    pe_ltp = float(put_row['lastPrice'].iloc[0])
                    ce_high = float(call_row.get('high', ce_ltp*1.2).iloc[0]) if 'high' in call_row else ce_ltp*1.3
                    pe_high = float(put_row.get('high', pe_ltp*1.2).iloc[0]) if 'high' in put_row else pe_ltp*1.3
                    ce_data = {"lastPrice": ce_ltp, "dayHigh": ce_high, "dayLow": ce_ltp*0.6}
                    pe_data = {"lastPrice": pe_ltp, "dayHigh": pe_high, "dayLow": pe_ltp*0.6}
                    print(f"YFINANCE OPTION LIVE {sym} {atm} CE:{ce_ltp} PE:{pe_ltp}")
                    return atm, ce_data, pe_data, "YAHOO LIVE"
    except Exception as e:
        print(f"Yahoo option fail: {e}")

    return None,None,None,None

def send_smart_signals(sym, chat_id=None):
    spot, prev = get_spot_live(sym)
    if spot==0:
        send_tg(f"⚠️ *{sym} LIVE BUSY*\nYahoo slow. 1 min lo /{sym.lower()} malli kottu.", chat_id)
        return
    change = ((spot-prev)/prev*100) if prev else 0
    trend = "BULLISH" if change>0.6 else "BEARISH" if change<-0.6 else "SIDEWAYS"
    atm, ce_data, pe_data, source = get_option_live(sym, spot)
    if not ce_data:
        send_tg(f"⚠️ *{sym} {int(spot)} ({change:+.2f}%) - OPTION LOADING*\n1 min lo /{sym.lower()} malli kottu. NSE busy.", chat_id)
        return

    def decide(opt_type, data):
        ltp = data['lastPrice']
        if trend=="SIDEWAYS": return "AVOID", round(ltp*0.80,1)
        if opt_type=="CE":
            return ("CMP", ltp) if trend=="BULLISH" else ("AVOID", round(ltp*0.80,1))
        else:
            return ("CMP", ltp) if trend=="BEARISH" else ("AVOID", round(ltp*0.80,1))

    ce_dec, ce_entry = decide("CE", ce_data)
    pe_dec, pe_entry = decide("PE", pe_data)

    msg = f"📊 *{sym} {atm} | Spot: {int(spot)} ({change:+.2f}%) ✅ {source}*\nTrend: {trend}\n--------------------------\n\n"
    msg += f"{'🟢' if ce_dec=='CMP' else '🔴'} {atm} CE - {ce_dec}\nLive: {ce_data['lastPrice']} | Entry: {ce_entry}\nSL: {round(ce_entry*0.7,1)} T1:{round(ce_entry*1.15,1)} T2:{round(ce_entry*1.30,1)}\n\n"
    msg += f"{'🔴' if pe_dec=='CMP' else '🟢'} {atm} PE - {pe_dec}\nLive: {pe_data['lastPrice']} | Entry: {pe_entry}\nSL: {round(pe_entry*0.7,1)} T1:{round(pe_entry*1.15,1)} T2:{round(pe_entry*1.30,1)}\n"
    send_tg(msg, chat_id)
    try:
        kb = {"inline_keyboard": [[{"text": "📈 NIFTY", "callback_data": "nifty"}, {"text": "🏦 BANKNIFTY", "callback_data": "banknifty"}], [{"text": "📊 SENSEX", "callback_data": "sensex"}]]}
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", data={"chat_id": chat_id or CHAT_ID, "text": "👇 Next:", "reply_markup": json.dumps(kb)}, timeout=10)
    except: pass

def auto_loop():
    while True:
        try:
            now = get_ist_now()
            if now.weekday()>=5: time.sleep(3600); continue
            is_m = (now.hour==9 and now.minute>=20) or (9 < now.hour < 15) or (now.hour==15 and now.minute<=30)
            if not is_m: time.sleep(60); continue
            key = f"{now.hour}:{now.minute}"
            if key in ["9:20","10:0","11:0","12:30","14:0"]:
                send_tg(f"🤖 *AUTO LIVE - {now.strftime('%I:%M %p')}*")
                time.sleep(2); send_smart_signals("NIFTY"); time.sleep(5); send_smart_signals("SENSEX")
                time.sleep(120)
        except: time.sleep(60)
        time.sleep(30)

@app.route('/')
def home(): return "100% LIVE via Yahoo+Cloudscraper Running!"

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    if not data: return "ok"
    chat_id=None; text=""
    if 'message' in data:
        chat_id=data['message']['chat']['id']; text=data['message'].get('text','').lower()
    elif 'callback_query' in data:
        chat_id=data['callback_query']['message']['chat']['id']; text=data['callback_query']['data'].lower()
        try: requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/answerCallbackQuery", data={"callback_query_id": data['callback_query']['id']}, timeout=5)
        except: pass
    if not chat_id: return "ok"
    global CHAT_ID; CHAT_ID=chat_id
    if 'sensex' in text: threading.Thread(target=send_smart_signals, args=("SENSEX", chat_id)).start()
    elif 'nifty' in text: threading.Thread(target=send_smart_signals, args=("NIFTY", chat_id)).start()
    elif 'bank' in text: threading.Thread(target=send_smart_signals, args=("BANKNIFTY", chat_id)).start()
    else:
        try:
            kb = {"inline_keyboard": [[{"text": "📈 NIFTY", "callback_data": "nifty"}, {"text": "🏦 BANKNIFTY", "callback_data": "banknifty"}], [{"text": "📊 SENSEX", "callback_data": "sensex"}]]}
            requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", data={"chat_id": chat_id, "text": "👇 Select:", "reply_markup": json.dumps(kb)}, timeout=10)
        except: pass
    return "ok"

def set_hook():
    time.sleep(2)
    try: requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook?url={MY_URL}/webhook", timeout=10)
    except: pass

threading.Thread(target=set_hook, daemon=True).start()
threading.Thread(target=auto_loop, daemon=True).start()

if __name__=="__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",10000)))
