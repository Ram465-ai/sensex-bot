import os, requests, time, threading
from datetime import datetime
from flask import Flask

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

app = Flask(__name__)

@app.route('/')
def home():
    return "BOT LIVE - NIFTY BANKNIFTY - " + datetime.now().strftime('%H:%M:%S')

def send_tg(msg):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=15)
        print(f"SENT: {msg[:50]}")
    except Exception as e:
        print(f"TG Error: {e}")

def get_data(symbol):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.9"
        }
        s = requests.Session()
        s.headers.update(headers)
        s.get("https://www.nseindia.com", timeout=15)
        time.sleep(1)
        url = f"https://www.nseindia.com/api/option-chain-indices?symbol={symbol}"
        data = s.get(url, headers=headers, timeout=15).json()
        
        spot = data['records']['underlyingValue']
        print(f"{symbol} SPOT: {spot}")
        
        # Check ATM + 1 ITM + 1 OTM = 3 strikes
        atm = round(spot / 100) * 100 if symbol == "NIFTY" else round(spot / 100) * 100
        strikes_to_check = [atm-100, atm, atm+100] if symbol == "NIFTY" else [atm-200, atm, atm+200]
        
        sigs = []
        for row in data['records']['data']:
            strike = row.get('strikePrice')
            if strike in strikes_to_check:
                ce = row.get('CE')
                pe = row.get('PE')
                # Logic relaxed: pChange > 1.5 and OI buildup
                if ce and ce.get('pChange', 0) > 1.5 and ce.get('change',0) > 0:
                    sigs.append(("CE", strike, ce))
                if pe and pe.get('pChange', 0) > 1.5 and pe.get('change',0) > 0:
                    sigs.append(("PE", strike, pe))
        
        return spot, sigs
    except Exception as e:
        print(f"Data Error {symbol}: {e}")
        return None, []

def bot_loop():
    time.sleep(10)
    send_tg("✅ *BOT STARTED & FIXED* - Signals will come now")
    print("BOT LOOP STARTED")
    
    while True:
        try:
            print(f"Checking at {datetime.now()}...")
            for sym in ["NIFTY", "BANKNIFTY"]:
                spot, signals = get_data(sym)
                if not spot:
                    continue
                
                if not signals:
                    print(f"{sym}: No setup found")
                
                for typ, strike, d in signals:
                    entry = d['lastPrice']
                    if entry < 5: # 5 rupees kanna takkuva unte vaddu
                        continue
                    sl = int(entry * 0.70) # 30% SL
                    t1 = int(entry * 1.30)
                    t2 = int(entry * 1.70)
                    
                    msg = f"""🔥 *{sym} {strike} {typ}*

💰 ENTRY: {entry}
🛑 SL: {sl}
🎯 T1: {t1}
🎯 T2: {t2}

📍 SPOT: {spot}
⏰ TIME: {datetime.now().strftime('%H:%M')}"""
                    
                    send_tg(msg)
                    time.sleep(3)
            
            print("Sleeping 5 mins...")
            time.sleep(300) # 5 mins ki okasari check
            
        except Exception as e:
            print(f"Loop Error: {e}")
            time.sleep(60)

# Thread start once only
threading.Thread(target=bot_loop, daemon=True).start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
