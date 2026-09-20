import pandas as pd
import numpy as np

YEARS = [2021, 2022]

def run_year(year):
    FILE = f"DAT_ASCII_JPXJPY_M1_{year}.csv"
    raw = pd.read_csv(FILE, header=None, sep=r"[,;\s]+", engine="python")
    raw = raw.iloc[:, :7]
    raw.columns = ["date","time","open","high","low","close","volume"]
    raw["dt"] = pd.to_datetime(
        raw["date"].astype(str) + raw["time"].astype(str).str.zfill(6),
        format="%Y%m%d%H%M%S", errors="coerce"
    )
    for c in ["open","high","low","close"]:
        raw[c] = pd.to_numeric(raw[c], errors="coerce")
    raw = raw.dropna(subset=["dt","open","high","low","close"]).set_index("dt").sort_index()

    bars = raw.resample("5min", label="right", closed="right").agg(
        open=("open","first"), high=("high","max"), low=("low","min"), close=("close","last")
    ).dropna()

    tp = (bars.high + bars.low + bars.close) / 3
    day = bars.index.date
    bars["vwap"] = tp.groupby(day).transform(lambda x: x.cumsum()/np.arange(1,len(x)+1))

    pc = bars.close.shift(1)
    tr = pd.concat([bars.high-bars.low, (bars.high-pc).abs(), (bars.low-pc).abs()], axis=1).max(axis=1)
    bars["atr"] = tr.ewm(alpha=1/14, adjust=False, min_periods=14).mean()

    d = bars.close.diff()
    g, l = d.clip(lower=0), -d.clip(upper=0)
    ag = g.ewm(alpha=1/2, adjust=False, min_periods=2).mean()
    al = l.ewm(alpha=1/2, adjust=False, min_periods=2).mean()
    rs = ag/al.replace(0,np.nan)
    bars["rsi2"] = 100 - 100/(1+rs)
    bars.loc[al.eq(0)&ag.gt(0),"rsi2"] = 100
    bars.loc[ag.eq(0)&al.gt(0),"rsi2"] = 0

    b15 = bars.resample("15min", label="right", closed="right").agg(
        open=("open","first"), high=("high","max"), low=("low","min"), close=("close","last")
    ).dropna()
    pc = b15.close.shift(1)
    tr15 = pd.concat([b15.high-b15.low, (b15.high-pc).abs(), (b15.low-pc).abs()], axis=1).max(axis=1)
    up, dn = b15.high.diff(), -b15.low.diff()
    pdm = up.where((up>dn)&(up>0),0.0)
    mdm = dn.where((dn>up)&(dn>0),0.0)
    a15 = tr15.ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    pdi = 100*pdm.ewm(alpha=1/14, adjust=False, min_periods=14).mean()/a15
    mdi = 100*mdm.ewm(alpha=1/14, adjust=False, min_periods=14).mean()/a15
    dx = 100*(pdi-mdi).abs()/(pdi+mdi).replace(0,np.nan)
    bars["adx15"] = dx.ewm(alpha=1/14, adjust=False, min_periods=14).mean().reindex(bars.index, method="ffill")

    trades, pos = [], None
    for i, row in enumerate(bars.itertuples()):
        ts = bars.index[i]
        in_eu = 420 <= ts.hour*60+ts.minute < 960

        if pos is not None:
            ex = reason = None
            if pos["side"] == "long":
                if row.low <= pos["sl"]: ex, reason = pos["sl"], "SL"
                elif row.high >= pos["tp"]: ex, reason = pos["tp"], "VWAP"
            else:
                if row.high >= pos["sl"]: ex, reason = pos["sl"], "SL"
                elif row.low <= pos["tp"]: ex, reason = pos["tp"], "VWAP"
            if ex is None and i-pos["entry_i"] >= 12:
                ex, reason = row.close, "TIMEOUT"
            if ex is not None:
                r = ((ex-pos["entry"])/pos["risk"]) if pos["side"]=="long" else ((pos["entry"]-ex)/pos["risk"])
                trades.append({"entry_time":pos["entry_time"],"exit_time":ts,"side":pos["side"],"entry":pos["entry"],"exit":ex,"r":r,"reason":reason})
                pos = None
                continue

        if pos is None and in_eu and all(np.isfinite(x) for x in [row.rsi2,row.atr,row.vwap,row.adx15]) and row.adx15 < 25:
            if row.rsi2 < 10 and row.close <= row.vwap - 1.5*row.atr:
                risk = 1.2*row.atr
                pos = {"side":"long","entry_time":ts,"entry":row.close,"sl":row.close-risk,"tp":row.vwap,"risk":risk,"entry_i":i}
            elif row.rsi2 > 95 and row.close >= row.vwap + 2*row.atr:
                risk = 1.2*row.atr
                pos = {"side":"short","entry_time":ts,"entry":row.close,"sl":row.close+risk,"tp":row.vwap,"risk":risk,"entry_i":i}

    if pos is not None:
        row = bars.iloc[-1]
        ex = row.close
        r = ((ex-pos["entry"])/pos["risk"]) if pos["side"]=="long" else ((pos["entry"]-ex)/pos["risk"])
        trades.append({"entry_time":pos["entry_time"],"exit_time":bars.index[-1],"side":pos["side"],"entry":pos["entry"],"exit":ex,"r":r,"reason":"END_OF_DATA"})

    tr = pd.DataFrame(trades)
    tr.to_csv(f"trades_{year}_europe.csv", index=False)
    if len(tr):
        wins, losses = sum(tr.r>0), sum(tr.r<0)
        pf = tr.loc[tr.r>0,"r"].sum()/abs(tr.loc[tr.r<0,"r"].sum())
        cr = tr.r.cumsum()
        print(f"YEAR={year} TRADES={len(tr)} WINS={wins} LOSSES={losses} WIN_RATE={wins/len(tr)*100:.2f} NET_R={tr.r.sum():.3f} AVG_R={tr.r.mean():.4f} PROFIT_FACTOR={pf:.3f} MAX_DRAWDOWN_R={(cr.cummax()-cr).max():.3f}")
        print(tr.groupby("reason").r.agg(["count","sum","mean"]).to_string())
    else:
        print(f"YEAR={year} TRADES=0")
    return tr

all_trades = []
for y in YEARS:
    tr = run_year(y)
    if len(tr):
        all_trades.append(tr.assign(year=y))

if all_trades:
    alltr = pd.concat(all_trades, ignore_index=True)
    alltr.to_csv("trades_2021_2022_europe.csv", index=False)
    wins = (alltr.r>0).sum()
    pf = alltr.loc[alltr.r>0,"r"].sum()/abs(alltr.loc[alltr.r<0,"r"].sum())
    cr = alltr.r.cumsum()
    print(f"COMBINED TRADES={len(alltr)} WINS={wins} LOSSES={(alltr.r<0).sum()} WIN_RATE={wins/len(alltr)*100:.2f} NET_R={alltr.r.sum():.3f} AVG_R={alltr.r.mean():.4f} PROFIT_FACTOR={pf:.3f} MAX_DRAWDOWN_R={(cr.cummax()-cr).max():.3f}")
