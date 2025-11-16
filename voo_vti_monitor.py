"""
voo_vti_monitor.py
- Polls minute data for VOO and VTI (with fallback)
- Computes normalized spread (VOO - scaled VTI) and spread_pct
- Logs to CSV and keeps recent memory
- Reads Vanguard CSV holdings and appends datetime for archive
- Small Flask dashboard to view latest spread, last rows, shares
- Color-coded recommended action and table rows
- Countdown timer for last strong buy/sell
- Market closed / pre-market placeholder message
"""
import os
import time
from datetime import datetime
import threading

import yfinance as yf
import pandas as pd
from flask import Flask, render_template_string
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv

load_dotenv()

# ---------------- CONFIG ----------------
CONFIG = {
    "SYMBOL_A": "VOO",
    "SYMBOL_B": "VTI",
    "POLL_SECONDS": 30,
    "LOOKBACK_MINUTES": 480,
    "INTERVAL": "1m",
    "FALLBACK_INTERVALS": ["2m", "5m", "15m"],
    "THRESHOLD_PCT": 0.15,
    "PRE_WARNING_PCT": 0.10,
    "CSV_LOG": "voo_vti_spread_log.csv",
    "MAX_ROWS_IN_MEMORY": 5000,
    "FLASK_PORT": 8000,
    "AUTO_OPEN_BROWSER": False,
    "VANGUARD_CSV": "data/OfxDownload.csv"
}

# ---------------- APP STATE ----------------
app = Flask(__name__)
scheduler = BackgroundScheduler()
lock = threading.Lock()
state = {
    "last_row": None,
    "last_strong_time": None,
    "df_tail": pd.DataFrame(),
    "shares": {CONFIG["SYMBOL_A"]: 0, CONFIG["SYMBOL_B"]: 0},
    "market_msg": ""
}

# ---------------- DATA FETCH ----------------
def fetch_interval_safe(symbol, interval):
    period = "6d" if interval == "1m" else "60d"
    try:
        df = yf.download(symbol, period=period, interval=interval,
                         prepost=True, progress=False, auto_adjust=False)
        return df.sort_index() if not df.empty else pd.DataFrame()
    except Exception as e:
        print(f"Error fetching {symbol} interval {interval}: {e}")
        return pd.DataFrame()

def get_minute_data(symbol, primary_interval, fallback_intervals):
    for iv in [primary_interval] + fallback_intervals:
        df = fetch_interval_safe(symbol, iv)
        if not df.empty:
            return df
    return pd.DataFrame()

# ---------------- VANGUARD HOLDINGS ----------------
def read_vanguard_csv():
    csv_path = CONFIG["VANGUARD_CSV"]
    shares = {CONFIG["SYMBOL_A"]: 0, CONFIG["SYMBOL_B"]: 0}
    if not os.path.exists(csv_path):
        return shares
    try:
        df = pd.read_csv(csv_path)
        # Append Datetime for archive
        df["ArchiveDatetime"] = datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
        # Example: assume ETF symbol column is 'Symbol' and shares column is 'Shares'
        for sym in shares.keys():
            matched = df.loc[df['Symbol'].str.upper() == sym.upper(), 'Shares']
            if not matched.empty:
                shares[sym] = matched.iloc[0]
        return shares
    except Exception as e:
        print("Failed to read Vanguard CSV:", e)
        return shares

# ---------------- COMPUTE / LOG ----------------
def compute_and_log():
    try:
        a_sym = CONFIG["SYMBOL_A"]
        b_sym = CONFIG["SYMBOL_B"]

        df_a = get_minute_data(a_sym, CONFIG["INTERVAL"], CONFIG["FALLBACK_INTERVALS"])
        df_b = get_minute_data(b_sym, CONFIG["INTERVAL"], CONFIG["FALLBACK_INTERVALS"])
        if df_a.empty or df_b.empty:
            print(f"[{datetime.now().strftime('%I:%M:%S %p')}] Warning: missing data for {a_sym} or {b_sym}")
            return

        s_a = df_a["Close"].copy()
        s_b = df_b["Close"].copy()
        combined = pd.concat([s_a, s_b], axis=1).dropna()
        combined.columns = [a_sym, b_sym]

        if combined.empty:
            print(f"[{datetime.now().strftime('%I:%M:%S %p')}] No aligned data for {a_sym}/{b_sym}")
            return

        scale_factor = float(combined.iloc[0][a_sym]) / float(combined.iloc[0][b_sym])
        combined["B_scaled"] = combined[b_sym] * scale_factor
        combined["spread"] = combined[a_sym] - combined["B_scaled"]
        combined["spread_pct"] = (combined["spread"] / combined[a_sym]) * 100.0
        df_tail = combined.tail(200).copy()

        latest = df_tail.iloc[-1]
        latest_time = df_tail.index[-1]

        # Determine Action
        pct = latest["spread_pct"]
        if pct >= CONFIG["THRESHOLD_PCT"]:
            action = f"Strong Sell {a_sym} / Buy {b_sym}"
            color = "darkred"
            state["last_strong_time"] = datetime.now()
        elif pct >= CONFIG["PRE_WARNING_PCT"]:
            action = f"Approaching Sell {a_sym} / Buy {b_sym}"
            color = "orange"
        elif pct <= -CONFIG["THRESHOLD_PCT"]:
            action = f"Strong Buy {a_sym} / Sell {b_sym}"
            color = "darkgreen"
            state["last_strong_time"] = datetime.now()
        elif pct <= -CONFIG["PRE_WARNING_PCT"]:
            action = f"Approaching Buy {a_sym} / Sell {b_sym}"
            color = "lightgreen"
        else:
            action = "Neutral"
            color = "yellow"

        log_row = {
            "Datetime": latest_time.strftime("%Y-%m-%d %I:%M:%S %p"),
            a_sym: float(latest[a_sym]),
            b_sym: float(latest[b_sym]),
            "B_scaled": float(latest["B_scaled"]),
            "spread": float(latest["spread"]),
            "spread_pct": float(latest["spread_pct"]),
            "action": action,
            "color": color
        }

        # Append to CSV
        write_header = not os.path.exists(CONFIG["CSV_LOG"])
        pd.DataFrame([log_row]).to_csv(CONFIG["CSV_LOG"], mode="a", header=write_header, index=False)

        # Reset index for table
        df_tail_reset = df_tail.copy().reset_index()
        df_tail_reset.rename(columns={"index": "Datetime"}, inplace=True)
        df_tail_reset["Datetime"] = df_tail_reset["Datetime"].dt.strftime("%Y-%m-%d %I:%M:%S %p")

        # Compute row colors for table
        rows_with_colors = []
        for _, r in df_tail_reset.iterrows():
            pct_r = r["spread_pct"]
            if pct_r >= CONFIG["THRESHOLD_PCT"]:
                color_r = "darkred"
                action_r = f"Strong Sell {a_sym} / Buy {b_sym}"
            elif pct_r >= CONFIG["PRE_WARNING_PCT"]:
                color_r = "orange"
                action_r = f"Approaching Sell {a_sym} / Buy {b_sym}"
            elif pct_r <= -CONFIG["THRESHOLD_PCT"]:
                color_r = "darkgreen"
                action_r = f"Strong Buy {a_sym} / Sell {b_sym}"
            elif pct_r <= -CONFIG["PRE_WARNING_PCT"]:
                color_r = "lightgreen"
                action_r = f"Approaching Buy {a_sym} / Sell {b_sym}"
            else:
                color_r = "yellow"
                action_r = "Neutral"
            row_dict = r.to_dict()
            row_dict["action"] = action_r
            rows_with_colors.append((row_dict, color_r))

        # Update state
        with lock:
            state["last_row"] = log_row
            state["df_tail"] = rows_with_colors
            state["shares"] = read_vanguard_csv()

        print(f"[{datetime.now().strftime('%I:%M:%S %p')}] spread_pct={pct:.4f}% | Action={action}")

    except Exception as e:
        print("Error in compute_and_log():", e)

# ---------------- FLASK DASHBOARD ----------------
DASH_TEMPLATE = """
<!doctype html>
<title>VOO/VTI Spread Monitor</title>
<meta http-equiv="refresh" content="5">
<h2>VOO / VTI Spread Monitor</h2>
<p>Symbols: {{ a_sym }} / {{ b_sym }}</p>
<p>Last update: {{ last_time }}</p>
<p>Top Action Recommendation:
    <b style="color: {{ top_color }}">{{ top_action }}</b>
    {% if top_action in ['Strong Buy','Strong Sell'] %}
        | Countdown: {{ countdown }}
    {% endif %}
    | Spread %={{ top_spread_pct }}
</p>
<p>Market Status: {{ market_msg }}</p>
<p>Current Shares: {{ shares[a_sym] }} {{ a_sym }} / {{ shares[b_sym] }} {{ b_sym }}</p>
<hr>
<h3>Recent spread rows</h3>
<table border=1 cellpadding=6>
<tr><th>Datetime</th><th>{{ a_sym }}</th><th>{{ b_sym }}</th><th>B_scaled</th><th>Spread</th><th>Spread %</th><th>Action</th></tr>
{% for row, color in rows %}
<tr style="background-color: {{ color }}; {% if color in ['darkred','darkgreen'] %}color:white;font-weight:bold{% endif %}">
  <td>{{ row['Datetime'] }}</td>
  <td>{{ "%.3f"|format(row[a_sym]) }}</td>
  <td>{{ "%.3f"|format(row[b_sym]) }}</td>
  <td>{{ "%.3f"|format(row['B_scaled']) }}</td>
  <td>{{ "%.4f"|format(row['spread']) }}</td>
  <td>{{ "%.4f"|format(row['spread_pct']) }}</td>
  <td>{{ row['action'] }}</td>
</tr>
{% endfor %}
</table>
"""

@app.route("/")
def index():
    with lock:
        lr = state.get("last_row")
        rows_with_colors = state.get("df_tail")
        shares = state.get("shares")
        last_strong = state.get("last_strong_time")
        market_msg = state.get("market_msg")

    if lr is None:
        return "No data yet - wait for first poll."

    # Countdown for last strong signal
    countdown = ""
    if last_strong:
        delta = datetime.now() - last_strong
        mins, secs = divmod(delta.seconds, 60)
        countdown = f"{mins}m {secs}s ago"

    return render_template_string(DASH_TEMPLATE,
                                  a_sym=CONFIG["SYMBOL_A"],
                                  b_sym=CONFIG["SYMBOL_B"],
                                  last_time=lr["Datetime"],
                                  top_action=lr["action"] if "Strong" in lr["action"] else "None",
                                  top_color=lr["color"] if "Strong" in lr["action"] else "yellow",
                                  top_spread_pct=f"{lr['spread_pct']:.4f}",
                                  countdown=countdown,
                                  shares=shares,
                                  rows=rows_with_colors[::-1][:50],
                                  market_msg=market_msg)

# ---------------- SCHEDULER ----------------
def start_scheduler():
    scheduler.add_job(compute_and_log, 'interval', seconds=CONFIG["POLL_SECONDS"], next_run_time=datetime.now())
    scheduler.start()
    print("Scheduler started. Poll interval:", CONFIG["POLL_SECONDS"], "sec")

# ---------------- MAIN ----------------
if __name__ == "__main__":
    print("Starting VOO/VTI spread monitor...")
    start_scheduler()
    try:
        app.run(host="0.0.0.0", port=CONFIG["FLASK_PORT"], debug=False, use_reloader=False)
    except (KeyboardInterrupt, SystemExit):
        print("Shutting down...")
        scheduler.shutdown()