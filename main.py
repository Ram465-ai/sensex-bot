mport os, requests, threading, time
from flask import Flask, request
from datetime import datetime

app = Flask(__name__)
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# Free proxy API that works from USA server - bypasses NSE block
def get_nse_data_proxy(symbol):
    # Try 3 methods
    urls = [
        f"https://nseindia.vercel.app/api/option-chain-indices?symbol={symbol}",
        f"https://nse-api-new.vercel.app/api/optionChain?symbol={symbol}",
        f"https://api.niftytrader.in/api/option-chain?symbol={symbol}&expiry="
    ]
    for url in urls:
        try:
            r = requests.get(url, timeout=12, headers={"User-Agent":"Mozilla/5.0"})
            print(f"Trying {url} -> {r.status_code}")
            if r.status_code == 200:
                j = r.json()
                # Normalize different formats
                if 'records' in j: # NSE format
                    return j
                if 'data' in j and 'records' in j['data']:
                    return j['data']
                if 'body' in j: # vercel proxy
                    return j['body'] if 'records' in j['body'] else j
                return j
        except Exception as e:
            print(f"Proxy fail {url}: {e}")
            continue
    return None

def get_spot_yahoo(symbol):
    # Fallback - Yahoo Finance always works from USA
    try:
        ymap = {"NIFTY":"^NSEI", "BANKNIFTY":"^NSEBANK", "SENSEX":"^BSESN"}
        ysym = ymap.get(symbol, "^NSEI")
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ysym}?interval=1m&range=1d"
        r = requests.get(url, headers={"User-Agent":"Mozilla/5.0"}, timeout=10).json()
        price = r['chart']['result'][0]['meta']['regularMarketPrice']
        return float(price)
    except Exception as e:
        print(f"Yahoo fail {e}")
        return None

def build_msg(index_name):
    try:
        symbol = "NIFTY" if index_name=="NIFTY" else "BANKNIFTY" if index_name=="BANKNIFTY" else "NIFTY"

        data = get_nse_data_proxy(symbol)
        spot = None

        if data and 'records' in data:
            spot = data['records']['underlyingValue']
            expiry = data['records']['expiryDates'][0]
            atm = round(spot/50)*50
            if symbol=="BANKNIFTY": atm = round(spot/100)*100

            ce_ltp = pe_ltp = ce_oi = pe_oi = 0
            for item in data['records']['data']:
                if item.get('strikePrice')==atm and item.get('expiryDate')==expiry:
                    if 'CE' in item:
                        ce_ltp = item['CE']['lastPrice']
                        ce_oi = item['CE']['openInterest']
                        ce_high = item['CE'].get('dayHigh', ce_ltp)
                    if 'PE' in item:
                        pe_ltp = item['PE']['lastPrice']
                        pe_oi = item['PE']['openInterest']
                        pe_high = item['PE'].get('dayHigh', pe_ltp)
                    break

            if ce_ltp==0:
                raise Exception("CE 0")

            pcr = round(pe_oi/ce_oi,2) if ce_oi>0 else 1.0

            if pcr>1.1:
                entry = round(ce_high+2,1) if 'ce_high' in locals() else round(ce_ltp*1.03,1)
                sl = round(entry*0.65,1)
                t1 = round(entry*1.4,1)
                t2 = round(entry*1.9,1)
                signal = f"🟢 *BUY {atm} CE*\nEntry: > {entry}\nSL: {sl}\nT1: {t1} T2: {t2}\nReason: PCR {pcr} Bullish"
            elif pcr<0.9:
                entry = round(pe_high+2,1) if 'pe_high' in locals() else round(pe_ltp*1.03,1)
                sl = round(entry*0.65,1)
                t1 = round(entry*1.4,1)
                t2 = round(entry*1.9,1)
                signal = f"🔴 *BUY {atm} PE*\nEntry: > {entry}\nSL: {sl}\nT1: {t1} T2: {t2}\nReason: PCR {pcr} Bearish"
            else:
                signal = f"⚪ *WAIT*\nCE Buy > {round(ce_ltp*1.04,1)} | PE Buy > {round(pe_ltp*1.04,1)}\nPCR {pcr} Neutral"

            msg = f"📊 *{index_name} {expiry}*\nSpot: {spot:.2f} ATM: {atm} PCR:{pcr}\nCE:{ce_ltp} OI:{ce_oi/1000:.0f}k | PE:{pe_ltp} OI:{pe_oi/1000:.0f}k\n\n{signal}\n\n✅ LIVE via Proxy"
            return msg
        else:
            # If proxy also fails, use Yahoo spot + entry logic without option chain
            spot = get_spot_yahoo(symbol)
            if spot:
                atm = round(spot/50)*50
                if symbol=="BANKNIFTY": atm = round(spot/100)*100
                # Estimate entry - 1% breakout
                return (
                    f"📊 *{index_name}*\n"
                    f"Spot: {spot:.2f} ATM: {atm}\n\n"
                    f"⚠️ NSE Option chain blocked, using Spot\n"
                    f"🟢 BUY {atm} CE if Spot > {round(spot+30,2)}\n"
                    f"🔴 BUY {atm} PE if Spot < {round(spot-30,2)}\n"
                    f"SL 35% | Target 40-90%\n\n"
                    f"✅ Yahoo LIVE"
                )
            return f"⏳ {index_name} servers busy - try again in 30 sec /{index_name.lower()}"

    except Exception as e:
        print(f"Build error {index_name}: {e}")
        spot = get_spot_yahoo(symbol)
        if spot:
            return f"📊 *{index_name}* Spot: {spot:.2f}\nNSE retrying... /{index_name.lower()}"
        return f"⏳ {index_name} retrying..."

def send_telegram(text, chat_id=None):
    try:
        cid = chat_id or CHAT_ID
        if not cid: return
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id":cid,"text":text,"parse_mode":"Markdown"}, timeout=10)
    except: pass

@app.route("/")
def home(): return "Bot Live V4 Proxy Fixed"

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json()
        if not data: return "ok"
        msg = data.get("message",{})
        chat_id = msg.get("chat",{}).get("id")
        text = msg.get("text","").lower()
        if chat_id: os.environ["CHAT_ID"]=str(chat_id)

        if "/nifty" in text:
            send_telegram(build_msg("NIFTY"), chat_id)
        elif "/banknifty" in text or text=="/bn":
            send_telegram(build_msg("BANKNIFTY"), chat_id)
        elif "/sensex" in text:
            # Sensex spot via yahoo
            spot = get_spot_yahoo("SENSEX")
            send_telegram(f"📊 *SENSEX* Spot: {spot}\nUse /nifty /banknifty for entries", chat_id)
        elif "/start" in text:
            send_telegram("Welcome! /nifty /banknifty - with Buy Entry ✅", chat_id)
        return "ok"
    except Exception as e:
        print(f"Webhook {e}")
        return "ok"

# STOP spam auto messages when failing
def auto_loop():
    while True:
        try:
            time.sleep(900) # 15 min only, and only if working
            now = datetime.now()
            if now.weekday()<5 and 9 <= now.hour <= 15 and CHAT_ID:
                # Only send if data works
                test = get_nse_data_proxy("NIFTY")
                if test:
                    msg = build_msg("NIFTY")
                    if "⏳" not in msg:
                        send_telegram(f"🔔 Auto 15m\n{msg}")
        except:
            time.sleep(60)

threading.Thread(target=auto_loop, daemon=True).start()

if __name__=="__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",10000)))
