import os, requests, time, threading
from datetime import datetime
from flask import Flask
BOT_TOKEN=os.getenv("BOT_TOKEN")
CHAT_ID=os.getenv("CHAT_ID")
app=Flask(__name__)
@app.route('/')
def home(): return "BOT LIVE - "+datetime.now().strftime('%H:%M:%S')
@app.route('/test')
def test():
    try:
        url=f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.post(url,data={"chat_id":CHAT_ID,"text":"🧪 TESTING OK ✅\nNIFTY 25000 CE\nENTRY 150\nBot Working!"},timeout=15)
        return "TEST SENT - Check Telegram"
    except Exception as e: return f"Error {e}"
def send_tg(msg):
    try: requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",data={"chat_id":CHAT_ID,"text":msg},timeout=15)
    except: pass
def get_data(symbol):
    try:
        s=requests.Session(); s.headers.update({"User-Agent":"Mozilla/5.0"})
        s.get("https://www.nseindia.com",timeout=15); time.sleep(1)
        data=s.get(f"https://www.nseindia.com/api/option-chain-indices?symbol={symbol}",timeout=15).json()
        spot=data['records']['underlyingValue']; atm=round(spot/100)*100
        sigs=[]
        for r in data['records']['data']:
            if r.get('strikePrice')==atm:
                ce=r.get('CE'); pe=r.get('PE')
                if ce and ce.get('pChange',0)>1.5: sigs.append(("CE",atm,ce))
                if pe and pe.get('pChange',0)>1.5: sigs.append(("PE",atm,pe))
        return spot,sigs
    except: return None,[]
def bot_loop():
    time.sleep(10); send_tg("✅ BOT STARTED & FIXED"); print("BOT LOOP STARTED")
    while True:
        try:
            for sym in ["NIFTY","BANKNIFTY"]:
                spot,sigs=get_data(sym)
                if not spot: continue
                for typ,strike,d in sigs:
                    e=d['lastPrice']; sl=int(e*0.7); t1=int(e*1.3); t2=int(e*1.7)
                    send_tg(f"🔥 {sym} {strike} {typ}\nENTRY {e}\nSL {sl}\nT1 {t1}\nT2 {t2}\nSPOT {spot}")
            time.sleep(300)
        except: time.sleep(60)
threading.Thread(target=bot_loop,daemon=True).start()
if __name__=="__main__": app.run(host="0.0.0.0",port=int(os.environ.get("PORT",10000)))
