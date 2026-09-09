import os, requests, time
from datetime import datetime

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

HEADERS = {"User-Agent": "Mozilla/5.0"}

def send_tg(msg):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": CHAT_ID, "text": msg}, timeout=10)
    except:
        pass

def get_nse_data(symbol):
    try:
        url = f"https://www.nseindia.com/api/option-chain-indices?symbol={symbol}"
        s = requests.Session()
        s.get("https://www.nseindia.com", headers=HEADERS, timeout=10)
        r = s.get(url, headers=HEADERS, timeout=10).json()
        spot = r['records']['underlyingValue']
        # ATM
        atm = round(spot/100)*100
        for item in r['records']['data']:
            if item.get('strikePrice') == atm:
                ce = item.get('CE')
                pe = item.get('PE')
                signals = []
                if ce and ce['pChange'] > 2:
                    signals.append(("CE", atm, ce))
                if pe and pe['pChange'] > 2:
                    signals.append(("PE", atm, pe))
                return spot, signals
        return spot, []
    except Exception as e:
        print(e)
        return None, []

def main():
    send_tg("BOT STARTED - NIFTY/BANKNIFTY/SENSEX")
    while True:
        for sym in ["NIFTY", "BANKNIFTY"]:
            spot, sigs = get_nse_data(sym)
            if not spot: continue
            for typ, strike, d in sigs:
                e = d['lastPrice']
                msg = f"""{sym} {strike} {typ}
ENTRY {e}
SL {int(e*0.75)}
T1 {int(e*1.4)}
T2 {int(e*1.8)}
SPOT {spot}
TIME {datetime.now().strftime('%H:%M')}"""
                send_tg(msg)
                time.sleep(2)
        time.sleep(900)

if __name__ == "__main__":
    main()
