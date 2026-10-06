"""
Meme moteur que rsi_reversal_confirm.py (RSI + confirmation de retournement),
avec en plus:
- filtre de tendance: EMA(ema_fast) vs EMA(ema_slow). Tendance haussiere si
  EMA_fast > EMA_slow, baissiere sinon. On ne prend le LONG (retournement
  depuis la survente) QUE si tendance haussiere, et le SHORT (retournement
  depuis le surachat) QUE si tendance baissiere -> "trade dans le sens de
  la tendance" (on achete les creux d'un uptrend, on vend les pics d'un
  downtrend, on ignore les signaux a contre-tendance).
- exclusion optionnelle de l'heure 00h00 GMT (artefact de gap d'ouverture
  identifie precedemment).
Spread reel deduit du R (spread_price_units), comme dans rsi_windows_atr.py.
"""
import numpy as np
from engine_ict_v2b import wilder_atr
from rsi_strategy import wilder_rsi
from strategies import ema


def run_rsi_confirm_trend(df, rsi_period=14, atr_period=14,
                           rsi_high=70, rsi_low=30, rsi_cancel_high=50, rsi_cancel_low=50,
                           max_wait_bars=10, sl_atr=1.5, tp_atr=3.0,
                           ema_fast=50, ema_slow=200, trend_filter=True,
                           exclude_hour0=True, spread_price_units=7.0):
    o = df['open'].values; h = df['high'].values; l = df['low'].values; c = df['close'].values
    times = df['datetime'].values
    hours = df['datetime'].dt.hour.values
    n = len(df)
    atr = wilder_atr(h, l, c, atr_period)
    rsi = wilder_rsi(c, rsi_period)
    ef = ema(c, ema_fast)
    es = ema(c, ema_slow)

    trades = []
    position = None

    watch_short = False
    watch_short_low = None
    watch_short_formed_i = -1

    watch_long = False
    watch_long_high = None
    watch_long_formed_i = -1

    start = max(atr_period, rsi_period, ema_slow) + 2
    for i in range(start, n):
        atr_val = atr[i]
        if np.isnan(atr_val) or atr_val <= 0 or np.isnan(rsi[i]) or np.isnan(ef[i]) or np.isnan(es[i]):
            continue

        if position is not None:
            side, sl, tp, entry, risk = (position['side'], position['sl'], position['tp'],
                                          position['entry'], position['risk'])
            r_gross = None; outcome = None
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

        trend_up = ef[i] > es[i]
        trend_down = ef[i] < es[i]

        j = i - 1
        if not watch_short and rsi[j] > rsi_high and h[j] > h[j-1] and h[j] > h[i]:
            watch_short = True
            watch_short_low = l[j]
            watch_short_formed_i = i

        if not watch_long and rsi[j] < rsi_low and l[j] < l[j-1] and l[j] < l[i]:
            watch_long = True
            watch_long_high = h[j]
            watch_long_formed_i = i

        if watch_short:
            bars_since = i - watch_short_formed_i
            if rsi[i] < rsi_cancel_high or bars_since > max_wait_bars:
                watch_short = False
            elif c[i] < watch_short_low:
                allow = (not trend_filter) or trend_down
                hour_ok = (not exclude_hour0) or (hours[i] != 0)
                if position is None and allow and hour_ok:
                    entry = c[i]
                    sl = entry + sl_atr * atr_val
                    tp = entry - tp_atr * atr_val
                    position = {'side': 'short', 'entry': entry, 'sl': sl, 'tp': tp,
                                'risk': sl_atr * atr_val, 'entry_i': i, 'entry_time': times[i]}
                watch_short = False

        if watch_long:
            bars_since = i - watch_long_formed_i
            if rsi[i] > rsi_cancel_low or bars_since > max_wait_bars:
                watch_long = False
            elif c[i] > watch_long_high:
                allow = (not trend_filter) or trend_up
                hour_ok = (not exclude_hour0) or (hours[i] != 0)
                if position is None and allow and hour_ok:
                    entry = c[i]
                    sl = entry - sl_atr * atr_val
                    tp = entry + tp_atr * atr_val
                    position = {'side': 'long', 'entry': entry, 'sl': sl, 'tp': tp,
                                'risk': sl_atr * atr_val, 'entry_i': i, 'entry_time': times[i]}
                watch_long = False

    return trades


def summarize(trades):
    if not trades:
        return dict(n=0, pct_tp=float('nan'), avgR_brut=float('nan'), avgR_net=float('nan'), sumR_net=0.0)
    n = len(trades)
    n_tp = sum(1 for t in trades if t['outcome'] == 'TP')
    avgR_brut = np.mean([t['r_gross'] for t in trades])
    avgR_net = np.mean([t['r_net'] for t in trades])
    sumR_net = np.sum([t['r_net'] for t in trades])
    return dict(n=n, pct_tp=n_tp/n*100, avgR_brut=avgR_brut, avgR_net=avgR_net, sumR_net=sumR_net)
