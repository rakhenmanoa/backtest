"""
Mean reversion approfondi: close s'ecarte de dev_atr x ATR de la SMA(sma_period)
-> pari sur le retour a la moyenne. R net calcule par trade (spread reel /
risque reel de CE trade), heure d'entree trackee pour vérifier l'artefact
de gap d'ouverture (00h GMT), comme pour RSI.
"""
import numpy as np
from engine_ict_v2b import wilder_atr, in_window
from strategies import sma


def run_mean_reversion_deep(df, atr_period=14, sma_period=20, dev_atr=2.0,
                             sl_atr=1.5, tp_atr=2.0,
                             exclude_hour0=False, windows=None,
                             spread_price_units=7.0):
    o = df['open'].values; h = df['high'].values; l = df['low'].values; c = df['close'].values
    times = df['datetime'].values
    hours = df['datetime'].dt.hour.values
    n = len(df)
    atr = wilder_atr(h, l, c, atr_period)
    ma = sma(c, sma_period)

    trades = []
    position = None

    start = max(atr_period, sma_period) + 1
    for i in range(start, n):
        atr_val = atr[i]
        if np.isnan(atr_val) or atr_val <= 0 or np.isnan(ma[i]):
            continue

        if position is not None:
            side, sl, tp, entry, risk = (position['side'], position['sl'], position['tp'],
                                          position['entry'], position['risk'])
            r_gross = None; outcome = None
            if side == 'long':
                if l[i] <= sl: r_gross = -1.0; outcome='SL'
                elif h[i] >= tp: r_gross=(tp-entry)/(entry-sl); outcome='TP'
            else:
                if h[i] >= sl: r_gross = -1.0; outcome='SL'
                elif l[i] <= tp: r_gross=(entry-tp)/(sl-entry); outcome='TP'
            if r_gross is not None:
                r_net = r_gross - spread_price_units/risk
                trades.append({**position, 'exit_i': i, 'r_gross': r_gross, 'r_net': r_net, 'outcome': outcome})
                position = None

        if position is None:
            hour_ok = (not exclude_hour0) or (hours[i] != 0)
            window_ok = True if windows is None else in_window(hours[i], windows)
            if hour_ok and window_ok:
                dev = c[i] - ma[i]
                if dev < -dev_atr * atr_val:
                    entry = c[i]
                    sl = entry - sl_atr*atr_val
                    tp = entry + tp_atr*atr_val
                    position = {'side':'long','entry':entry,'sl':sl,'tp':tp,
                                'risk': sl_atr*atr_val, 'entry_i':i,'entry_time':times[i]}
                elif dev > dev_atr * atr_val:
                    entry = c[i]
                    sl = entry + sl_atr*atr_val
                    tp = entry - tp_atr*atr_val
                    position = {'side':'short','entry':entry,'sl':sl,'tp':tp,
                                'risk': sl_atr*atr_val, 'entry_i':i,'entry_time':times[i]}

    return trades


def summarize(trades):
    if not trades:
        return dict(n=0, pct_tp=float('nan'), avgR_brut=float('nan'), avgR_net=float('nan'), sumR_net=0.0)
    n = len(trades)
    n_tp = sum(1 for t in trades if t['outcome']=='TP')
    avgR_brut = np.mean([t['r_gross'] for t in trades])
    avgR_net = np.mean([t['r_net'] for t in trades])
    sumR_net = np.sum([t['r_net'] for t in trades])
    return dict(n=n, pct_tp=n_tp/n*100, avgR_brut=avgR_brut, avgR_net=avgR_net, sumR_net=sumR_net)
