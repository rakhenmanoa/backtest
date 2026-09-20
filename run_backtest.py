import os
import pandas as pd
import numpy as np

FILES = [
    "DAT_ASCII_JPXJPY_M1_2021.csv",
    "DAT_ASCII_JPXJPY_M1_2022.csv",
    "DAT_ASCII_JPXJPY_M1_2023.csv"
]

def load_and_preprocess(file_paths):
    raw_list = []
    for fp in file_paths:
        if not os.path.exists(fp):
            print(f"Warning: File {fp} not found.")
            continue
        raw = pd.read_csv(fp, header=None, sep=r"[,;\s]+", engine="python")
        if raw.shape[1] < 6:
            continue
        raw = raw.iloc[:, :7]
        cols = ["date", "time", "open", "high", "low", "close", "volume"][:raw.shape[1]]
        raw.columns = cols
        raw["date"] = raw["date"].astype(str)
        raw["time"] = raw["time"].astype(str).str.zfill(6)
        raw["dt"] = pd.to_datetime(raw["date"] + raw["time"], format="%Y%m%d%H%M%S", errors="coerce")
        for c in ["open", "high", "low", "close"]:
            raw[c] = pd.to_numeric(raw[c], errors="coerce")
        raw = raw.dropna(subset=["dt", "open", "high", "low", "close"])
        raw_list.append(raw)

    if not raw_list:
        raise ValueError("No valid data loaded!")

    df = pd.concat(raw_list, ignore_index=True)
    df = df.set_index("dt").sort_index()
    # Deduplicate index if any
    df = df[~df.index.duplicated(keep="first")]
    return df

def run_backtest(df, label="All"):
    # 1-minute -> 5-minute bars.
    bars = df.resample("5min", label="right", closed="right").agg(
        open=("open", "first"), high=("high", "max"), low=("low", "min"), close=("close", "last")
    ).dropna()

    # Session-reset equal-volume VWAP proxy: cumulative average of typical price within each calendar day.
    tp = (bars.high + bars.low + bars.close) / 3.0
    day = bars.index.date
    bars["vwap"] = tp.groupby(day).transform(lambda x: x.cumsum() / np.arange(1, len(x) + 1))

    # ATR(14), Wilder/RMA.
    prev_close = bars.close.shift(1)
    tr = pd.concat([
        bars.high - bars.low,
        (bars.high - prev_close).abs(),
        (bars.low - prev_close).abs()
    ], axis=1).max(axis=1)
    bars["atr"] = tr.ewm(alpha=1/14, adjust=False, min_periods=14).mean()

    # RSI(2), Wilder/RMA.
    delta = bars.close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    ag = gain.ewm(alpha=1/2, adjust=False, min_periods=2).mean()
    al = loss.ewm(alpha=1/2, adjust=False, min_periods=2).mean()
    rs = ag / al.replace(0, np.nan)
    bars["rsi2"] = 100 - (100 / (1 + rs))
    bars.loc[al.eq(0) & ag.gt(0), "rsi2"] = 100
    bars.loc[ag.eq(0) & al.gt(0), "rsi2"] = 0

    # ADX(14) computed on 15-minute bars.
    b15 = bars.resample("15min", label="right", closed="right").agg(
        open=("open", "first"), high=("high", "max"), low=("low", "min"), close=("close", "last")
    ).dropna()
    pc = b15.close.shift(1)
    tr15 = pd.concat([
        b15.high - b15.low, (b15.high - pc).abs(), (b15.low - pc).abs()
    ], axis=1).max(axis=1)
    up = b15.high.diff()
    dn = -b15.low.diff()
    plus_dm = up.where((up > dn) & (up > 0), 0.0)
    minus_dm = dn.where((dn > up) & (dn > 0), 0.0)
    atr15 = tr15.ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    pdi = 100 * plus_dm.ewm(alpha=1/14, adjust=False, min_periods=14).mean() / atr15
    mdi = 100 * minus_dm.ewm(alpha=1/14, adjust=False, min_periods=14).mean() / atr15
    dx = 100 * (pdi - mdi).abs() / (pdi + mdi).replace(0, np.nan)
    adx15 = dx.ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    bars["adx15"] = adx15.reindex(bars.index, method="ffill")

    trades = []
    pos = None

    for i in range(len(bars)):
        row = bars.iloc[i]
        ts = bars.index[i]

        if pos is not None:
            exit_price = None
            reason = None
            # Intrabar exits. If both SL and TP are touched in the same bar, assume SL first.
            if pos["side"] == "long":
                if row.low <= pos["sl"]:
                    exit_price, reason = pos["sl"], "SL"
                elif row.high >= pos["tp"]:
                    exit_price, reason = pos["tp"], "VWAP"
            else:
                if row.high >= pos["sl"]:
                    exit_price, reason = pos["sl"], "SL"
                elif row.low <= pos["tp"]:
                    exit_price, reason = pos["tp"], "VWAP"

            if exit_price is None and i - pos["entry_i"] >= 12:
                exit_price, reason = row.close, "TIMEOUT"

            if exit_price is not None:
                if pos["side"] == "long":
                    r = (exit_price - pos["entry"]) / pos["risk"]
                else:
                    r = (pos["entry"] - exit_price) / pos["risk"]
                trades.append({
                    "entry_time": pos["entry_time"], "exit_time": ts, "side": pos["side"],
                    "entry": pos["entry"], "exit": exit_price, "sl": pos["sl"], "tp_vwap": pos["tp"],
                    "atr": pos["atr"], "r": r, "reason": reason,
                    "bars_held": i - pos["entry_i"]
                })
                pos = None
                continue

        if pos is None and np.isfinite(row.rsi2) and np.isfinite(row.atr) and np.isfinite(row.vwap) and np.isfinite(row.adx15):
            if row.adx15 < 25:
                if row.rsi2 < 10 and row.close <= row.vwap - 1.5 * row.atr:
                    risk = 1.2 * row.atr
                    pos = {"side": "long", "entry_time": ts, "entry": row.close,
                           "sl": row.close - risk, "tp": row.vwap, "risk": risk, "atr": row.atr, "entry_i": i}
                elif row.rsi2 > 95 and row.close >= row.vwap + 2 * row.atr:
                    risk = 1.2 * row.atr
                    pos = {"side": "short", "entry_time": ts, "entry": row.close,
                           "sl": row.close + risk, "tp": row.vwap, "risk": risk, "atr": row.atr, "entry_i": i}

    if pos is not None:
        row = bars.iloc[-1]
        exit_price = row.close
        r = ((exit_price - pos["entry"]) / pos["risk"]) if pos["side"] == "long" else ((pos["entry"] - exit_price) / pos["risk"])
        trades.append({"entry_time": pos["entry_time"], "exit_time": bars.index[-1], "side": pos["side"],
                       "entry": pos["entry"], "exit": exit_price, "sl": pos["sl"], "tp_vwap": pos["tp"],
                       "atr": pos["atr"], "r": r, "reason": "END_OF_DATA", "bars_held": len(bars) - 1 - pos["entry_i"]})

    tr = pd.DataFrame(trades)
    print(f"\n=================== BACKTEST RESULTS: {label} ===================")
    if len(tr):
        tr["cum_r"] = tr["r"].cumsum()
        tr.to_csv(f"trades_{label.lower().replace(' ', '_')}.csv", index=False)
        wins = (tr.r > 0).sum()
        losses = (tr.r < 0).sum()
        pf = tr.loc[tr.r > 0, "r"].sum() / abs(tr.loc[tr.r < 0, "r"].sum()) if losses else float("inf")
        max_dd = (tr.cum_r.cummax() - tr.cum_r).max()

        print(f"TRADES        : {len(tr)}")
        print(f"WINS          : {wins} ({wins/len(tr)*100:.2f}%)")
        print(f"LOSSES        : {losses} ({losses/len(tr)*100:.2f}%)")
        print(f"NET R         : {tr.r.sum():.3f}")
        print(f"AVG R         : {tr.r.mean():.4f}")
        print(f"MEDIAN R      : {tr.r.median():.4f}")
        print(f"PROFIT FACTOR : {pf:.3f}")
        print(f"MAX DRAWDOWN  : {max_dd:.3f} R")
        print(f"LONGS         : {(tr.side == 'long').sum()}")
        print(f"SHORTS        : {(tr.side == 'short').sum()}")
        print("\nBreakdown by Exit Reason:")
        print(tr.groupby("reason").r.agg(["count", "sum", "mean"]).to_string())
    else:
        print("TRADES = 0")
    print("=================================================================\n")
    return tr

if __name__ == "__main__":
    for file_path in FILES:
        if os.path.exists(file_path):
            year_str = file_path.split("_")[-1].replace(".csv", "")
            print(f"Processing year {year_str}...")
            df_year = load_and_preprocess([file_path])
            run_backtest(df_year, label=f"Year_{year_str}")

    print("Processing Combined Multi-Year Backtest (2021-2023)...")
    df_all = load_and_preprocess(FILES)
    run_backtest(df_all, label="Combined_2021_2023")
