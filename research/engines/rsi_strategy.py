"""
Strategie RSI(14) reversal: short si RSI>70, long si RSI<30.
SL/TP en multiples d'ATR. Blocage sequentiel (une position a la fois),
aucune fenetre horaire (toutes les seances).

Suit aussi, pour chaque trade, le MFE (Maximum Favorable Excursion, en R)
atteint avant la sortie -> permet de voir, parmi les trades qui n'ont PAS
atteint le TP (donc sortis en perte), jusqu'ou ils s'etaient rapproches
du TP avant de repartir contre nous.
"""
import numpy as np
from engine_ict_v2b import wilder_atr


def wilder_rsi(close, period=14):
    n = len(close)
    delta = np.diff(close, prepend=close[0])
    gain = np.where(delta > 0, delta, 0.0)
    loss = np.where(delta < 0, -delta, 0.0)
    rsi = np.full(n, np.nan)
    if n <= period:
        return rsi
    avg_gain = gain[1:period+1].mean()
    avg_loss = loss[1:period+1].mean()
    rs = avg_gain / avg_loss if avg_loss > 0 else np.inf
    rsi[period] = 100 - 100 / (1 + rs)
    for i in range(period+1, n):
        avg_gain = (avg_gain * (period - 1) + gain[i]) / period
        avg_loss = (avg_loss * (period - 1) + loss[i]) / period
        rs = avg_gain / avg_loss if avg_loss > 0 else np.inf
        rsi[i] = 100 - 100 / (1 + rs)
    return rsi


def run_rsi_reversal(df, rsi_period=14, atr_period=14, rsi_high=70, rsi_low=30,
                      sl_atr=1.5, tp_atr=3.0):
    o = df['open'].values; h = df['high'].values; l = df['low'].values; c = df['close'].values
    times = df['datetime'].values
    n = len(df)
    atr = wilder_atr(h, l, c, atr_period)
    rsi = wilder_rsi(c, rsi_period)

    trades = []
    position = None
    mfe_r = 0.0  # excursion favorable max courante (en R), suivie pendant la position ouverte

    start = max(atr_period, rsi_period) + 1
    for i in range(start, n):
        atr_val = atr[i]
        if np.isnan(atr_val) or atr_val <= 0 or np.isnan(rsi[i]):
            continue

        if position is not None:
            side, sl, tp, entry = position['side'], position['sl'], position['tp'], position['entry']
            risk = abs(entry - sl)
            # mise a jour du MFE avec les extremes de la bougie courante (avant de checker sortie)
            if side == 'long':
                fav_excursion = (h[i] - entry) / risk
            else:
                fav_excursion = (entry - l[i]) / risk
            if fav_excursion > mfe_r:
                mfe_r = fav_excursion

            if side == 'long':
                hit_sl = l[i] <= sl
                hit_tp = h[i] >= tp
                if hit_sl:
                    trades.append({**position, 'exit_i': i, 'exit_price': sl, 'r': -1.0,
                                   'outcome': 'SL', 'mfe_r': mfe_r})
                    position = None
                elif hit_tp:
                    trades.append({**position, 'exit_i': i, 'exit_price': tp,
                                   'r': (tp - entry) / (entry - sl), 'outcome': 'TP', 'mfe_r': mfe_r})
                    position = None
            else:
                hit_sl = h[i] >= sl
                hit_tp = l[i] <= tp
                if hit_sl:
                    trades.append({**position, 'exit_i': i, 'exit_price': sl, 'r': -1.0,
                                   'outcome': 'SL', 'mfe_r': mfe_r})
                    position = None
                elif hit_tp:
                    trades.append({**position, 'exit_i': i, 'exit_price': tp,
                                   'r': (entry - tp) / (sl - entry), 'outcome': 'TP', 'mfe_r': mfe_r})
                    position = None

        if position is None:
            mfe_r = 0.0
            if rsi[i] > rsi_high:
                entry = c[i]
                sl = entry + sl_atr * atr_val
                tp = entry - tp_atr * atr_val
                position = {'side': 'short', 'entry': entry, 'sl': sl, 'tp': tp,
                            'entry_i': i, 'entry_time': times[i]}
            elif rsi[i] < rsi_low:
                entry = c[i]
                sl = entry - sl_atr * atr_val
                tp = entry + tp_atr * atr_val
                position = {'side': 'long', 'entry': entry, 'sl': sl, 'tp': tp,
                            'entry_i': i, 'entry_time': times[i]}

    return trades


def summarize_rsi(trades):
    if not trades:
        return dict(n=0, winrate=float('nan'), avgR=float('nan'), sumR=0.0,
                    pct_tp=float('nan'), pct_sl=float('nan'), avg_mfe_losers=float('nan'))
    rs = np.array([t['r'] for t in trades])
    outcomes = np.array([t['outcome'] for t in trades])
    n = len(rs)
    n_tp = (outcomes == 'TP').sum()
    n_sl = (outcomes == 'SL').sum()
    losers_mfe = np.array([t['mfe_r'] for t in trades if t['outcome'] == 'SL'])
    return dict(
        n=n,
        winrate=n_tp / n * 100,
        avgR=rs.mean(),
        sumR=rs.sum(),
        pct_tp=n_tp / n * 100,
        pct_sl=n_sl / n * 100,
        avg_mfe_losers=losers_mfe.mean() if len(losers_mfe) else float('nan'),
    )
