import os, requests, time
from datetime import datetime
from nsepython import nse_optionchain_scrapper

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

def send_tg(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": CHAT_ID, "text": msg}, timeout=15)
    except:
        pass

def scan(symbol):
    try:
        data = nse_optionchain_scrapper(symbol)
        spot = data['records']['underlyingValue']
        atm = round(spot / 100) * 100
        out = []
        for item in data['records']['data']:
            if item.get('strikePrice') == atm:
                ce = item.get('CE')
                pe = item.get('PE')
                if ce and ce['pChange'] > 2 and ce['pchangeinOpenInterest'] > 5:
                    out.append(("CE", atm, ce))
                if pe and pe['pChange'] > 2 and pe['pchangeinOpenInterest'] > 5:
                    out.append(("PE", atm, pe))
        return spot, out
    except:
        return None, []

def main():
    send_tg("BOT STARTED")
    while True:
        for sym in ["NIFTY", "BANKNIFTY"]:
            spot, signals = scan(sym)
            for typ, strike, d in signals:
                e = d['lastPrice']
                sl = int(e * 0.75)
                t1 = int(e * 1.4)
                t2 = int(e * 1.8)
                msg = f"""{sym} {strike} {typ}
ENTRY {e}
SL {sl}
T1 {t1}
T2 {t2}
SPOT {spot}
TIME {datetime.now().strftime('%H:%M')}"""
                send_tg(msg)
                time.sleep(2)
        time.sleep(900)

if __name__ == "__main__":
    main()
