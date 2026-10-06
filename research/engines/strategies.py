"""
Trois moteurs additionnels + FVG, tous avec blocage sequentiel
(une seule position ouverte a la fois), aucun filtre de fenetre horaire.
"""
import numpy as np
from engine_ict_v2b import wilder_atr


def sma(x, period):
    s = np.full(len(x), np.nan)
    c = np.cumsum(np.insert(x, 0, 0))
    s[period-1:] = (c[period:] - c[:-period]) / period
    return s


def ema(x, period):
    e = np.full(len(x), np.nan)
    alpha = 2.0 / (period + 1)
    if len(x) < period:
        return e
    e[period-1] = np.mean(x[:period])
    for i in range(period, len(x)):
        e[i] = alpha * x[i] + (1 - alpha) * e[i-1]
    return e


def _close_trade(trades, position, exit_i, exit_price, r):
    trades.append({**position, 'exit_i': exit_i, 'exit_price': exit_price, 'r': r})


def _check_exit(position, h_i, l_i):
    """Retourne r si SL ou TP touche sur cette bougie, sinon None. Conservateur: SL en priorite si les deux touchent."""
    side, sl, tp, entry = position['side'], position['sl'], position['tp'], position['entry']
    if side == 'long':
        hit_sl = l_i <= sl
        hit_tp = h_i >= tp
        if hit_sl:
            return -1.0, sl
        if hit_tp:
            return (tp - entry) / (entry - sl), tp
    else:
        hit_sl = h_i >= sl
        hit_tp = l_i <= tp
        if hit_sl:
            return -1.0, sl
        if hit_tp:
            return (entry - tp) / (sl - entry), tp
    return None, None


def run_mean_reversion(df, atr_period=14, sma_period=20, dev_atr=2.0,
                        sl_atr=1.5, tp_atr=2.0):
    """
    Mean reversion: entree quand le close s'ecarte de plus de dev_atr x ATR
    de la SMA(sma_period), on parie sur le retour a la moyenne.
    Long si close < sma - dev_atr*ATR (survendu), short si close > sma + dev_atr*ATR.
    """
    o = df['open'].values; h = df['high'].values; l = df['low'].values; c = df['close'].values
    times = df['datetime'].values
    n = len(df)
    atr = wilder_atr(h, l, c, atr_period)
    ma = sma(c, sma_period)

    trades = []
    position = None

    for i in range(max(atr_period, sma_period) + 1, n):
        atr_val = atr[i]
        if np.isnan(atr_val) or atr_val <= 0 or np.isnan(ma[i]):
            continue

        if position is not None:
            r, exit_price = _check_exit(position, h[i], l[i])
            if r is not None:
                _close_trade(trades, position, i, exit_price, r)
                position = None

        if position is None:
            dev = c[i] - ma[i]
            if dev < -dev_atr * atr_val:
                entry = c[i]
                sl = entry - sl_atr * atr_val
                tp = entry + tp_atr * atr_val
                position = {'side': 'long', 'entry': entry, 'sl': sl, 'tp': tp,
                            'entry_i': i, 'entry_time': times[i]}
            elif dev > dev_atr * atr_val:
                entry = c[i]
                sl = entry + sl_atr * atr_val
                tp = entry - tp_atr * atr_val
                position = {'side': 'short', 'entry': entry, 'sl': sl, 'tp': tp,
                            'entry_i': i, 'entry_time': times[i]}

    return trades


def run_trend_following(df, atr_period=14, ema_fast=20, ema_slow=50,
                         sl_atr=2.0, tp_atr=4.0):
    """
    Trend following: croisement EMA rapide / EMA lente.
    Long a la hausse du croisement, short a la baisse. Une position a la
    fois; sortie sur SL/TP ou sur signal de croisement oppose (ce qui vient
    en premier).
    """
    o = df['open'].values; h = df['high'].values; l = df['low'].values; c = df['close'].values
    times = df['datetime'].values
    n = len(df)
    atr = wilder_atr(h, l, c, atr_period)
    ef = ema(c, ema_fast)
    es = ema(c, ema_slow)

    trades = []
    position = None

    start = max(atr_period, ema_slow) + 1
    for i in range(start, n):
        atr_val = atr[i]
        if np.isnan(atr_val) or atr_val <= 0 or np.isnan(ef[i]) or np.isnan(es[i]) or np.isnan(ef[i-1]) or np.isnan(es[i-1]):
            continue

        cross_up = ef[i-1] <= es[i-1] and ef[i] > es[i]
        cross_down = ef[i-1] >= es[i-1] and ef[i] < es[i]

        if position is not None:
            r, exit_price = _check_exit(position, h[i], l[i])
            if r is not None:
                _close_trade(trades, position, i, exit_price, r)
                position = None
            elif (position['side'] == 'long' and cross_down) or (position['side'] == 'short' and cross_up):
                # sortie sur signal oppose, au close de la bougie
                entry = position['entry']; sl = position['sl']
                if position['side'] == 'long':
                    r = (c[i] - entry) / (entry - sl)
                else:
                    r = (entry - c[i]) / (sl - entry)
                _close_trade(trades, position, i, c[i], r)
                position = None

        if position is None:
            if cross_up:
                entry = c[i]
                sl = entry - sl_atr * atr_val
                tp = entry + tp_atr * atr_val
                position = {'side': 'long', 'entry': entry, 'sl': sl, 'tp': tp,
                            'entry_i': i, 'entry_time': times[i]}
            elif cross_down:
                entry = c[i]
                sl = entry + sl_atr * atr_val
                tp = entry - tp_atr * atr_val
                position = {'side': 'short', 'entry': entry, 'sl': sl, 'tp': tp,
                            'entry_i': i, 'entry_time': times[i]}

    return trades


def run_order_block(df, atr_period=14, structure_lookback=10, ob_search_window=5,
                     max_wait_bars=50, sl_buffer_atr=0.2, sl_atr=1.5, tp_atr=4.0):
    """
    Order Block (ICT) simplifie, sans lookahead:
    - Cassure de structure haussiere a la bougie i: close[i] > max(high[i-structure_lookback:i])
    - Order block haussier = derniere bougie baissiere (close<open) parmi les
      ob_search_window bougies precedant i (formee AVANT i, donc pas de lookahead).
    - On attend ensuite (jusqu'a max_wait_bars) que le prix revienne toucher
      la zone de l'order block [low, high] de cette bougie -> entree au retest,
      SL sous le bas de la zone (- marge), TP a tp_atr x ATR.
    Symetrique pour les OB baissiers.
    """
    o = df['open'].values; h = df['high'].values; l = df['low'].values; c = df['close'].values
    times = df['datetime'].values
    n = len(df)
    atr = wilder_atr(h, l, c, atr_period)

    trades = []
    position = None

    # zones actives en attente de retest
    bull_zone = None  # (top, bot, formed_i)
    bear_zone = None

    for i in range(structure_lookback + ob_search_window + 1, n):
        atr_val = atr[i]
        if np.isnan(atr_val) or atr_val <= 0:
            continue

        # ---- gestion position ouverte ----
        if position is not None:
            r, exit_price = _check_exit(position, h[i], l[i])
            if r is not None:
                _close_trade(trades, position, i, exit_price, r)
                position = None

        # ---- detection cassure de structure haussiere ----
        if bull_zone is None:
            prior_high = np.max(h[i-structure_lookback:i])
            if c[i] > prior_high:
                # chercher la derniere bougie baissiere avant i (dans la fenetre de recherche)
                ob_j = None
                for j in range(i-1, i-1-ob_search_window, -1):
                    if j < 0:
                        break
                    if c[j] < o[j]:
                        ob_j = j
                        break
                if ob_j is not None:
                    bull_zone = (h[ob_j], l[ob_j], i)  # top, bot, formed_i

        # ---- detection cassure de structure baissiere ----
        if bear_zone is None:
            prior_low = np.min(l[i-structure_lookback:i])
            if c[i] < prior_low:
                ob_j = None
                for j in range(i-1, i-1-ob_search_window, -1):
                    if j < 0:
                        break
                    if c[j] > o[j]:
                        ob_j = j
                        break
                if ob_j is not None:
                    bear_zone = (h[ob_j], l[ob_j], i)

        # ---- gestion zone haussiere active: attente du retest ----
        if bull_zone is not None:
            top, bot, formed_i = bull_zone
            bars_since = i - formed_i
            if bars_since > max_wait_bars:
                bull_zone = None
            elif bars_since >= 1 and l[i] <= top and h[i] >= bot:
                # retest de la zone -> entree si pas deja en position
                if position is None:
                    entry = c[i]
                    sl = bot - sl_buffer_atr * atr_val
                    tp = entry + tp_atr * atr_val
                    position = {'side': 'long', 'entry': entry, 'sl': sl, 'tp': tp,
                                'entry_i': i, 'entry_time': times[i]}
                bull_zone = None

        # ---- gestion zone baissiere active: attente du retest ----
        if bear_zone is not None:
            top, bot, formed_i = bear_zone
            bars_since = i - formed_i
            if bars_since > max_wait_bars:
                bear_zone = None
            elif bars_since >= 1 and h[i] >= bot and l[i] <= top:
                if position is None:
                    entry = c[i]
                    sl = top + sl_buffer_atr * atr_val
                    tp = entry - tp_atr * atr_val
                    position = {'side': 'short', 'entry': entry, 'sl': sl, 'tp': tp,
                                'entry_i': i, 'entry_time': times[i]}
                bear_zone = None

    return trades


def summarize(trades):
    if not trades:
        return dict(n=0, winrate=float('nan'), avgR=float('nan'), sumR=0.0)
    rs = np.array([t['r'] for t in trades])
    n = len(rs)
    wr = (rs > 0).mean() * 100
    return dict(n=n, winrate=wr, avgR=rs.mean(), sumR=rs.sum())
