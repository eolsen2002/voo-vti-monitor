import yfinance as yf
import pandas as pd
import numpy as np

symbol1 = "VOO"
symbol2 = "VTI"

lookback = "7d"
primary_interval = "1m"

# % threshold for alert
threshold_pct = 0.10   # 0.10% difference

# -----------------------------
# SAFE DOWNLOAD WITH FALLBACKS
# -----------------------------
def download_close_series(symbol, period, interval):
    print(f"\nDownloading {interval} data for {symbol}...")
    data = yf.download(
        symbol, period=period, interval=interval,
        prepost=True, progress=False, auto_adjust=True
    )

    # If empty, fallback steps
    if data.empty:
        print(f"⚠️ No {interval} data for {symbol}. Falling back to 5m...")
        data = yf.download(
            symbol, period=period, interval="5m",
            prepost=True, progress=False, auto_adjust=True
        )

    if data.empty:
        print(f"⚠️ No 5m data for {symbol}. Falling back to 1d...")
        data = yf.download(
            symbol, period="30d", interval="1d",
            prepost=True, progress=False, auto_adjust=True
        )

    if data.empty:
        raise ValueError(f"❌ No usable data for {symbol} at any interval.")

    print(f"✔️ Data OK for {symbol}. Rows: {len(data)}")

    # Always return the Close column as a Series
    return data["Close"]


# -----------------------------
# DOWNLOAD BOTH SYMBOLS
# -----------------------------
voo_close = download_close_series(symbol1, lookback, primary_interval)
vti_close = download_close_series(symbol2, lookback, primary_interval)

# -----------------------------
# ALIGN & MERGE SAFELY
# -----------------------------
df = pd.concat([voo_close, vti_close], axis=1, keys=["VOO", "VTI"]).dropna()

# 🔥 FIX: Ensure flat column names
df.columns = ["VOO", "VTI"]


print("\nMerged dataframe tail:")
print(df.tail())


# -----------------------------
# SCALE VTI TO MATCH VOO PRICE
# -----------------------------
scale_factor = df["VOO"].iloc[-1] / df["VTI"].iloc[-1]
df["VTI_scaled"] = df["VTI"] * scale_factor

# -----------------------------
# SPREAD CALCULATION
# -----------------------------
df["spread"] = df["VOO"] - df["VTI_scaled"]
df["spread_pct"] = df["spread"] / df["VTI_scaled"] * 100

latest = df.iloc[-1]
latest_spread_pct = latest["spread_pct"]

print("\nLatest values:")
print(latest)

print(f"\n📊 Latest spread %: {latest_spread_pct:.4f}%")

# -----------------------------
# TRIGGER LOGIC
# -----------------------------
if abs(latest_spread_pct) > threshold_pct:
    print(f"🚨 ALERT: Spread has exceeded {threshold_pct:.2f}% threshold!")
else:
    print("No alert. Spread normal.")
