export default {
  async fetch(request) {
    const url = new URL(request.url);
    const symbol = (url.searchParams.get("symbol") || "NIFTY").toUpperCase();

    const targets = [
      `https://webapi.niftytrader.in/webapi/option/option-chain-data?symbol=${symbol}`,
      `https://www.niftytrader.in/api/option-chain?symbol=${symbol}&type=indices`
    ];

    for (const target of targets) {
      try {
        const res = await fetch(target, {
          headers: {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://www.niftytrader.in/option-chain",
            "Origin": "https://www.niftytrader.in"
          }
        });
        const text = await res.text();
        if (text && text.length > 500 && (text.includes("strike") || text.includes("Strike"))) {
          return new Response(text, {
            headers: {
              "Content-Type": "application/json",
              "Access-Control-Allow-Origin": "*",
              "Cache-Control": "no-cache"
            }
          });
        }
      } catch(e) {}
    }

    return new Response(JSON.stringify({error: "fetch failed"}), {
      headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" }
    });
  }
}
