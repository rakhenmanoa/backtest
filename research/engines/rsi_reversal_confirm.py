"""
RSI(14) reversal AVEC confirmation de retournement (pas d'entree immediate
au simple croisement de 70/30).

Logique (causale, sans lookahead):
1. On detecte un "swing high" (pic local: high[j] > high[j-1] et high[j] > high[j+1])
   pendant que RSI[j] > rsi_high -> zone de surachat avec extension du mouvement,
   PUIS retournement attendu. Le pic n'est confirme qu'a la bougie j+1 (donc on
   ne "sait" qu'il y a un pic qu'une fois j+1 formee, ce qui est normal/causal).
2. On attend ensuite (jusqu'a max_wait_bars) que le prix confirme le
   retournement: close[i] < low[j] (le bas de la bougie du pic) -> on entre
   SHORT au close[i].
3. Si RSI repasse sous rsi_cancel (ex: 50) avant confirmation, ou si
   max_wait_bars est depasse, on annule l'attente (pas de trade).
Symetrique pour les creux (survente, RSI < rsi_low) -> LONG.

SL/TP en multiples d'ATR comme les autres moteurs, une position a la fois,
aucune fenetre horaire.
"""
import numpy as np
from engine_ict_v2b import wilder_atr
from rsi_strategy import wilder_rsi


def run_rsi_reversal_confirm(df, rsi_period=14, atr_period=14,
                              rsi_high=70, rsi_low=30, rsi_cancel_high=50, rsi_cancel_low=50,
                              max_wait_bars=10, sl_atr=1.5, tp_atr=3.0):
    o = df['open'].values; h = df['high'].values; l = df['low'].values; c = df['close'].values
    times = df['datetime'].values
    n = len(df)
    atr = wilder_atr(h, l, c, atr_period)
    rsi = wilder_rsi(c, rsi_period)

    trades = []
    position = None

    # etat d'attente de confirmation
    watch_short = False
    watch_short_low = None
    watch_short_formed_i = -1

    watch_long = False
    watch_long_high = None
    watch_long_formed_i = -1

    start = max(atr_period, rsi_period) + 2
    for i in range(start, n):
        atr_val = atr[i]
        if np.isnan(atr_val) or atr_val <= 0 or np.isnan(rsi[i]):
            continue

        # ---- gestion position ouverte ----
        if position is not None:
            side, sl, tp, entry = position['side'], position['sl'], position['tp'], position['entry']
            if side == 'long':
                hit_sl = l[i] <= sl
                hit_tp = h[i] >= tp
                if hit_sl:
                    trades.append({**position, 'exit_i': i, 'exit_price': sl, 'r': -1.0, 'outcome': 'SL'})
                    position = None
                elif hit_tp:
                    trades.append({**position, 'exit_i': i, 'exit_price': tp,
                                   'r': (tp - entry) / (entry - sl), 'outcome': 'TP'})
                    position = None
            else:
                hit_sl = h[i] >= sl
                hit_tp = l[i] <= tp
                if hit_sl:
                    trades.append({**position, 'exit_i': i, 'exit_price': sl, 'r': -1.0, 'outcome': 'SL'})
                    position = None
                elif hit_tp:
                    trades.append({**position, 'exit_i': i, 'exit_price': tp,
                                   'r': (entry - tp) / (sl - entry), 'outcome': 'TP'})
                    position = None

        # ---- detection d'un nouveau pic de surachat (bougie i-1 est le pic, confirme par i) ----
        j = i - 1
        if not watch_short and rsi[j] > rsi_high and h[j] > h[j-1] and h[j] > h[i]:
            watch_short = True
            watch_short_low = l[j]
            watch_short_formed_i = i

        if not watch_long and rsi[j] < rsi_low and l[j] < l[j-1] and l[j] < l[i]:
            watch_long = True
            watch_long_high = h[j]
            watch_long_formed_i = i

        # ---- suivi de l'attente de confirmation SHORT ----
        if watch_short:
            bars_since = i - watch_short_formed_i
            if rsi[i] < rsi_cancel_high or bars_since > max_wait_bars:
                watch_short = False
            elif c[i] < watch_short_low:
                if position is None:
                    entry = c[i]
                    sl = entry + sl_atr * atr_val
                    tp = entry - tp_atr * atr_val
                    position = {'side': 'short', 'entry': entry, 'sl': sl, 'tp': tp,
                                'entry_i': i, 'entry_time': times[i]}
                watch_short = False

        # ---- suivi de l'attente de confirmation LONG ----
        if watch_long:
            bars_since = i - watch_long_formed_i
            if rsi[i] > rsi_cancel_low or bars_since > max_wait_bars:
                watch_long = False
            elif c[i] > watch_long_high:
                if position is None:
                    entry = c[i]
                    sl = entry - sl_atr * atr_val
                    tp = entry + tp_atr * atr_val
                    position = {'side': 'long', 'entry': entry, 'sl': sl, 'tp': tp,
                                'entry_i': i, 'entry_time': times[i]}
                watch_long = False

    return trades


def summarize(trades):
    if not trades:
        return dict(n=0, winrate=float('nan'), avgR=float('nan'), sumR=0.0, pct_tp=float('nan'))
    rs = np.array([t['r'] for t in trades])
    outcomes = np.array([t['outcome'] for t in trades])
    n = len(rs)
    n_tp = (outcomes == 'TP').sum()
    return dict(n=n, winrate=n_tp/n*100, avgR=rs.mean(), sumR=rs.sum(), pct_tp=n_tp/n*100)
