import os
import requests
import json
import re
from datetime import datetime, timedelta

APPS_SCRIPT_URL = os.environ.get(
    "APPS_SCRIPT_URL",
    "https://script.google.com/macros/s/AKfycbyytAGmVfuxun3WJ5QYw_EP728V6KHLTivj20Kb8h9ArMqWV365XbgA2yItM7WOnZ18/exec"
)

NIFTY_50 = {"RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", "HCLTECH", "SBIN", "BHARTIARTL", "ITC", "LT", "KOTAKBANK", "AXISBANK"}
NIFTY_100 = NIFTY_50 | {"TATAMOTORS", "ZOMATO", "BEL", "HAL", "VEDL", "DIVISLAB", "ADANIENT", "BAJFINANCE", "NTPC", "ONGC"}

def get_index_tag(symbol):
    sym = str(symbol).strip().upper()
    if sym in NIFTY_50:
        return "Nifty 50"
    elif sym in NIFTY_100:
        return "Nifty 100"
    return "All Companies"

def extract_time(text):
    match = re.search(r'(\d{1,2}[:.]\d{2}\s*(?:AM|PM|am|pm|hrs|hours)?)', str(text))
    return match.group(1).upper() if match else "TBA"

def clean_date_str(raw_dt):
    if not raw_dt:
        return datetime.now().strftime("%d-%b-%Y")
    raw = str(raw_dt).strip()
    m = re.search(r'(\d{1,2}-[A-Za-z]{3}-\d{4})', raw)
    if m:
        return m.group(1)
    m2 = re.search(r'(\d{1,2}[-/.]\d{1,2}[-/.]\d{4})', raw)
    if m2:
        return m2.group(1)
    if len(raw) >= 11 and raw[2] == '-' and raw[6] == '-':
        return raw[:11]
    return raw[:10]

def get_session():
    session = requests.Session()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.nseindia.com/"
    }
    try:
        session.get("https://www.nseindia.com", headers=headers, timeout=10)
    except Exception:
        pass
    return session, headers

def fetch_results(session, headers):
    print("1. Fetching Board Meetings (Results)...")
    url = "https://www.nseindia.com/api/corporate-board-meetings?index=equities"
    try:
        res = session.get(url, headers=headers, timeout=15)
        data = res.json() if res.status_code == 200 else []
    except Exception:
        data = []

    rows = []
    for item in data:
        purpose = str(item.get("bm_desc", item.get("purpose", "")))
        p_lower = purpose.lower()
        if any(t in p_lower for t in ["result", "financial", "quarter", "audited", "unaudited", "accounts"]):
            symbol = item.get("bm_symbol", item.get("symbol", ""))
            company = item.get("sm_name", item.get("companyName", symbol))
            date_str = clean_date_str(item.get("bm_date", ""))
            link = f"https://www.nseindia.com/get-quotes/equity?symbol={symbol}"
            index_tag = get_index_tag(symbol)
            rows.append([symbol, company, date_str, index_tag, "Equity", purpose, link])
    return rows

def fetch_concalls(session, headers):
    print("2. Fetching Analyst & Investor Calls (Concalls)...")
    from_date = (datetime.now() - timedelta(days=7)).strftime("%d-%m-%Y")
    to_date = datetime.now().strftime("%d-%m-%Y")
    
    url = f"https://www.nseindia.com/api/corporate-announcements?index=equities&from_date={from_date}&to_date={to_date}"
    headers["Referer"] = "https://www.nseindia.com/companies-listing/corporate-filings-announcements"
    
    try:
        res = session.get(url, headers=headers, timeout=20)
        data = res.json() if res.status_code == 200 else []
    except Exception:
        data = []

    print(f"Total announcements inspected: {len(data)}")
    rows = []
    keywords = ["concall", "earnings call", "conference call", "analyst meet", "investor meet", "analyst / investor", "schedule of analyst"]
    seen_symbols = set()
    
    for item in data:
        desc = str(item.get("desc", ""))
        subject = str(item.get("attchmntText", item.get("sm_name", "")))
        full_text = f"{desc} {subject}".lower()
        
        if any(k in full_text for k in keywords):
            symbol = item.get("symbol", "")
            if symbol in seen_symbols:
                continue
            seen_symbols.add(symbol)
            
            company = item.get("sm_name", symbol)
            date_str = clean_date_str(item.get("an_dt", ""))
            
            call_time = extract_time(desc)
            if call_time == "TBA":
                call_time = extract_time(subject)
                
            att_url = item.get("attchmntFile", "")
            link = att_url if att_url else f"https://www.nseindia.com/get-quotes/equity?symbol={symbol}"
            index_tag = get_index_tag(symbol)
            
            rows.append([symbol, company, date_str, call_time, index_tag, "Equity", link])
            
    return rows

def push_to_sheets(tab_name, rows):
    if not rows:
        print(f"No records found for {tab_name}.")
        return
    print(f"Pushing {len(rows)} rows to '{tab_name}' tab...")
    payload = json.dumps({"tab": tab_name, "rows": rows})
    res = requests.post(
        APPS_SCRIPT_URL,
        data=payload,
        headers={"Content-Type": "text/plain;charset=utf-8"},
        allow_redirects=True,
        timeout=30
    )
    print(f"{tab_name} Response:", res.text)

def main():
    session, headers = get_session()
    
    results_rows = fetch_results(session, headers)
    push_to_sheets("Results", results_rows)
    
    concall_rows = fetch_concalls(session, headers)
    push_to_sheets("Concalls", concall_rows)
    
    print("\nSync completed successfully for both tabs.")

if __name__ == "__main__":
    main()