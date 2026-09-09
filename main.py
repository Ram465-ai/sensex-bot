import os
import time
import threading
import logging
from datetime import datetime
from typing import Tuple, List, Optional, Dict

import requests
from flask import Flask

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

app = Flask(__name__)


@app.route("/")
def home():
    return "BOT LIVE - NIFTY BANKNIFTY"


def send_tg(msg: str) -> bool:
    """Send message to Telegram. Returns True on success."""
    if not BOT_TOKEN or not CHAT_ID:
        logger.error("BOT_TOKEN or CHAT_ID not set; skipping Telegram send.")
        return False

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        resp = requests.post(
            url,
            data={"chat_id": CHAT_ID, "text": msg},
            timeout=15,
        )
        if resp.status_code != 200:
            logger.error("Telegram send failed: %s %s", resp.status_code, resp.text)
            return False
        return True
    except requests.RequestException as e:
        logger.error("Failed to send Telegram message: %s", e)
        return False


def _safe_get_lastprice(option: Dict) -> Optional[float]:
    if not option:
        return None
    return option.get("lastPrice")


def get_data(symbol: str) -> Tuple[Optional[float], List[Tuple[str, int, Dict]]]:
    """
    Fetch NSE option chain data for symbol.
    Returns (spot, signals) where signals is a list of tuples (typ, strike, data_dict).
    On errors returns (None, []).
    """
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.nseindia.com",
        "Connection": "keep-alive",
    }

    try:
        s = requests.Session()
        # Warm up session to get cookies
        s.get("https://www.nseindia.com", headers=headers, timeout=10)

        url = f"https://www.nseindia.com/api/option-chain-indices?symbol={symbol}"
        resp = s.get(url, headers=headers, timeout=10)
        if resp.status_code != 200:
            logger.error("NSE response status %s for %s", resp.status_code, symbol)
            return None, []

        data = resp.json()
        records = data.get("records")
        if not records:
            logger.error("No records in NSE response for %s", symbol)
            return None, []

        spot = records.get("underlyingValue")
        if spot is None:
            logger.error("No underlyingValue in NSE response for %s", symbol)
            return None, []

        # compute ATM to nearest 100 (explicit cast to int)
        try:
            atm = int(round(float(spot) / 100.0)) * 100
        except Exception:
            logger.exception("Failed to compute ATM for spot=%s", spot)
            return None, []

        signals = []
        rows = records.get("data", [])
        # find the row with strikePrice == atm
        atm_row = None
        for row in rows:
            if row.get("strikePrice") == atm:
                atm_row = row
                break

        if atm_row is None:
            # ATM row not found; return spot so caller can decide
            return spot, []

        ce = atm_row.get("CE") or {}
        pe = atm_row.get("PE") or {}

        if ce and ce.get("pChange", 0) > 2:
            signals.append(("CE", atm, ce))
        if pe and pe.get("pChange", 0) > 2:
            signals.append(("PE", atm, pe))

        return spot, signals

    except requests.RequestException as e:
        logger.error("Network error fetching NSE data for %s: %s", symbol, e)
        return None, []
    except ValueError as e:
        logger.error("JSON decode error for %s: %s", symbol, e)
        return None, []
    except Exception as e:
        logger.exception("Unexpected error fetching data for %s: %s", symbol, e)
        return None, []


def bot_loop():
    """Main bot loop running in background"""
    time.sleep(5)
    logger.info("Bot loop starting")
    if not BOT_TOKEN or not CHAT_ID:
        logger.error("BOT_TOKEN or CHAT_ID not set; bot loop will not send messages.")
    else:
        send_tg("BOT STARTED")

    while True:
        try:
            for sym in ["NIFTY", "BANKNIFTY"]:
                spot, signals = get_data(sym)
                # treat None as an error; 0 is a valid numeric but unlikely here
                if spot is None:
                    continue

                for typ, strike, d in signals:
                    entry = _safe_get_lastprice(d)
                    if entry is None:
                        logger.warning("Missing lastPrice for %s %s", sym, typ)
                        continue

                    sl = int(entry * 0.75)
                    t1 = int(entry * 1.4)
                    t2 = int(entry * 1.8)

                    msg = (
                        f"{sym} {strike} {typ}\n"
                        f"ENTRY {entry}\n"
                        f"SL {sl}\n"
                        f"T1 {t1}\n"
                        f"T2 {t2}\n"
                        f"SPOT {spot}\n"
                        f"TIME {datetime.now().strftime('%H:%M')}"
                    )
                    send_tg(msg)
                    time.sleep(2)

            # sleep between cycles
            time.sleep(900)  # 15 minutes
        except Exception:
            logger.exception("Error in bot_loop; sleeping 10s before retry")
            time.sleep(10)


if __name__ == "__main__":
    # Start bot thread only when running directly to avoid multiple threads under WSGI/reloader
    if BOT_TOKEN and CHAT_ID:
        t = threading.Thread(target=bot_loop, daemon=True)
        t.start()
    else:
        logger.warning("BOT_TOKEN or CHAT_ID missing: background bot will not start.")

    port = int(os.environ.get("PORT", 10000))
    # In production, run with a WSGI server (gunicorn/uwsgi) rather than app.run
    app.run(host="0.0.0.0", port=port)
