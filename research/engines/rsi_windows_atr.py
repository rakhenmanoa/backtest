"""
RSI(14) reversal (entree immediate au croisement 70/30, la version qui avait
le meilleur avgR brut), avec en plus:
- filtre de fenetre horaire (windows)
- filtre d'ATR eleve: on n'entre que si ATR(14) courant >= atr_filter_mult x
  ATR_long (moyenne mobile de l'ATR sur atr_long_period bougies), pour ne
  trader que les moments de volatilite elevee (le cout du spread en R baisse
  mecaniquement quand l'ATR est plus grand pour un meme multiple de SL).
Le R net (apres cout de spread reel) est calcule directement par trade,
avec spread_price_units = cout de spread estime en unites de prix.
"""
import numpy as np
from engine_ict_v2b import wilder_atr, in_window
from rsi_strategy import wilder_rsi


def sma(x, period):
    s = np.full(len(x), np.nan)
    c = np.cumsum(np.insert(np.nan_to_num(x, nan=0.0), 0, 0))
    valid = ~np.isnan(x)
    cnt = np.cumsum(np.insert(valid.astype(float), 0, 0))
    s[period-1:] = (c[period:] - c[:-period]) / period
    return s


def run_rsi_reversal_windows_atr(df, rsi_period=14, atr_period=14, atr_long_period=100,
                                  rsi_high=70, rsi_low=30,
                                  sl_atr=1.5, tp_atr=3.0,
                                  windows=None, atr_filter_mult=1.0,
                                  spread_price_units=7.0):
    o = df['open'].values; h = df['high'].values; l = df['low'].values; c = df['close'].values
    times = df['datetime'].values
    hours = df['datetime'].dt.hour.values
    n = len(df)
    atr = wilder_atr(h, l, c, atr_period)
    atr_long = sma(atr, atr_long_period)
    rsi = wilder_rsi(c, rsi_period)

    trades = []
    position = None

    start = max(atr_period, rsi_period, atr_long_period) + 1
    for i in range(start, n):
        atr_val = atr[i]
        if np.isnan(atr_val) or atr_val <= 0 or np.isnan(rsi[i]) or np.isnan(atr_long[i]):
            continue

        if position is not None:
            side, sl, tp, entry, risk = (position['side'], position['sl'], position['tp'],
                                          position['entry'], position['risk'])
            r_gross = None
            outcome = None
            if side == 'long':
                if l[i] <= sl:
                    r_gross = -1.0; outcome = 'SL'
                elif h[i] >= tp:
                    r_gross = (tp - entry) / (entry - sl); outcome = 'TP'
            else:
                if h[i] >= sl:
                    r_gross = -1.0; outcome = 'SL'
                elif l[i] <= tp:
                    r_gross = (entry - tp) / (sl - entry); outcome = 'TP'
            if r_gross is not None:
                r_net = r_gross - spread_price_units / risk
                trades.append({**position, 'exit_i': i, 'r_gross': r_gross, 'r_net': r_net, 'outcome': outcome})
                position = None

        if position is None:
            window_ok = True if windows is None else in_window(hours[i], windows)
            atr_ok = atr_val >= atr_filter_mult * atr_long[i]
            if window_ok and atr_ok:
                if rsi[i] > rsi_high:
                    entry = c[i]
                    sl = entry + sl_atr * atr_val
                    tp = entry - tp_atr * atr_val
                    position = {'side': 'short', 'entry': entry, 'sl': sl, 'tp': tp,
                                'risk': sl_atr * atr_val, 'entry_i': i, 'entry_time': times[i]}
                elif rsi[i] < rsi_low:
                    entry = c[i]
                    sl = entry - sl_atr * atr_val
                    tp = entry + tp_atr * atr_val
                    position = {'side': 'long', 'entry': entry, 'sl': sl, 'tp': tp,
                                'risk': sl_atr * atr_val, 'entry_i': i, 'entry_time': times[i]}

    return trades


def summarize(trades):
    if not trades:
        return dict(n=0, pct_tp=float('nan'), avgR_brut=float('nan'), avgR_net=float('nan'),
                    sumR_net=0.0)
    n = len(trades)
    n_tp = sum(1 for t in trades if t['outcome'] == 'TP')
    avgR_brut = np.mean([t['r_gross'] for t in trades])
    avgR_net = np.mean([t['r_net'] for t in trades])
    sumR_net = np.sum([t['r_net'] for t in trades])
    return dict(n=n, pct_tp=n_tp/n*100, avgR_brut=avgR_brut, avgR_net=avgR_net, sumR_net=sumR_net)
