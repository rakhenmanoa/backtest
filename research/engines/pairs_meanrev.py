"""
Mean reversion sur le RATIO US30/DAX (pairs trading / stat-arb).
Le ratio n'a pas de high/low bien definis (calcule a partir des closes des
deux jambes), donc on utilise une ATR "proxy" basee sur les variations de
close a close, et les sorties SL/TP sont verifiees uniquement sur le close
de chaque bougie (simplification -- pas de verification intra-bougie).
"""
import numpy as np


def ratio_atr_proxy(ratio, period=14):
    diffs = np.abs(np.diff(ratio, prepend=ratio[0]))
    atr = np.full(len(ratio), np.nan)
    if len(ratio) > period:
        atr[period] = diffs[1:period+1].mean()
        for i in range(period+1, len(ratio)):
            atr[i] = (atr[i-1]*(period-1) + diffs[i]) / period
    return atr


def sma(x, period):
    s = np.full(len(x), np.nan)
    c = np.cumsum(np.insert(x, 0, 0))
    s[period-1:] = (c[period:] - c[:-period]) / period
    return s


def run_pairs_meanrev(ratio, atr_period=14, sma_period=20, dev_atr=2.0,
                       sl_atr=2.0, tp_atr=3.0):
    n = len(ratio)
    atr = ratio_atr_proxy(ratio, atr_period)
    ma = sma(ratio, sma_period)

    trades = []
    position = None

    start = max(atr_period, sma_period) + 1
    for i in range(start, n):
        atr_val = atr[i]
        if np.isnan(atr_val) or atr_val <= 0 or np.isnan(ma[i]):
            continue

        if position is not None:
            side, sl, tp, entry = position['side'], position['sl'], position['tp'], position['entry']
            price = ratio[i]
            r = None
            if side == 'long':
                if price <= sl: r = -1.0
                elif price >= tp: r = (tp-entry)/(entry-sl)
            else:
                if price >= sl: r = -1.0
                elif price <= tp: r = (entry-tp)/(sl-entry)
            if r is not None:
                trades.append({**position, 'exit_i': i, 'r': r})
                position = None

        if position is None:
            dev = ratio[i] - ma[i]
            if dev < -dev_atr*atr_val:
                entry = ratio[i]
                sl = entry - sl_atr*atr_val
                tp = entry + tp_atr*atr_val
                position = {'side':'long','entry':entry,'sl':sl,'tp':tp,'entry_i':i}
            elif dev > dev_atr*atr_val:
                entry = ratio[i]
                sl = entry + sl_atr*atr_val
                tp = entry - tp_atr*atr_val
                position = {'side':'short','entry':entry,'sl':sl,'tp':tp,'entry_i':i}

    return trades


def summarize(trades):
    if not trades:
        return dict(n=0, winrate=float('nan'), avgR=float('nan'), sumR=0.0)
    rs = np.array([t['r'] for t in trades])
    n = len(rs)
    wr = (rs>0).mean()*100
    return dict(n=n, winrate=wr, avgR=rs.mean(), sumR=rs.sum())
