"""
Mean reversion avec entree basee sur deviation ATR (comme avant), mais
SL et TP calcules en multiples du SPREAD REEL (au moment de l'entree)
plutot qu'en multiples d'ATR.

SL = sl_spread_mult x spread_reel_a_l_entree
TP = tp_spread_mult x spread_reel_a_l_entree

Avantage: le cout du spread en R devient CONSTANT = 1/sl_spread_mult
(puisque risque = sl_spread_mult x spread, et cout = spread), au lieu de
varier enormement avec l'ATR comme avant.
"""
import numpy as np
from engine_ict_v2b import wilder_atr, in_window
from strategies import sma


def run_mean_reversion_spread_sltp(df, atr_period=14, sma_period=20, dev_atr=1.5,
                                    sl_spread_mult=4.0, tp_spread_mult=8.0,
                                    exclude_hour0=False, windows=None):
    o = df['open'].values; h = df['high'].values; l = df['low'].values; c = df['close'].values
    spread_price = df['spread_price'].values
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
                if l[i] <= sl: r_gross=-1.0; outcome='SL'
                elif h[i] >= tp: r_gross=(tp-entry)/(entry-sl); outcome='TP'
            else:
                if h[i] >= sl: r_gross=-1.0; outcome='SL'
                elif l[i] <= tp: r_gross=(entry-tp)/(sl-entry); outcome='TP'
            if r_gross is not None:
                # cout reel = spread au moment de l'entree (deja fige dans 'entry_spread')
                r_net = r_gross - position['entry_spread'] / risk
                trades.append({**position, 'exit_i': i, 'r_gross': r_gross, 'r_net': r_net, 'outcome': outcome})
                position = None

        if position is None:
            spr = spread_price[i]
            if spr <= 0:
                continue
            hour_ok = (not exclude_hour0) or (hours[i] != 0)
            window_ok = True if windows is None else in_window(hours[i], windows)
            if hour_ok and window_ok:
                dev = c[i] - ma[i]
                risk = sl_spread_mult * spr
                if dev < -dev_atr * atr_val:
                    entry = c[i]
                    sl = entry - risk
                    tp = entry + tp_spread_mult * spr
                    position = {'side':'long','entry':entry,'sl':sl,'tp':tp,'risk':risk,
                                'entry_spread': spr, 'entry_i':i,'entry_time':times[i]}
                elif dev > dev_atr * atr_val:
                    entry = c[i]
                    sl = entry + risk
                    tp = entry - tp_spread_mult * spr
                    position = {'side':'short','entry':entry,'sl':sl,'tp':tp,'risk':risk,
                                'entry_spread': spr, 'entry_i':i,'entry_time':times[i]}

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
