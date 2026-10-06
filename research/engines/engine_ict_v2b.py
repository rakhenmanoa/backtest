"""
Reconstructed validated reference engine (bias-free version).
FVG-fill strategy: 3-candle FVG detection, full-fill requirement,
exit confirmation with ATR margin, sequential position blocking
(one position open at a time, resolved via TP/SL/timeout before next).

No speed filter (max_fill_bars / max_confirm_bars set very high = disabled)
to avoid the lookahead bias discovered earlier (using future knowledge of
whether a signal would pass the speed filter to decide whether to block
the sequential engine on it).
"""
import numpy as np


def wilder_atr(high, low, close, period=14):
    n = len(high)
    tr = np.zeros(n)
    tr[0] = high[0] - low[0]
    for i in range(1, n):
        tr[i] = max(high[i] - low[i], abs(high[i] - close[i-1]), abs(low[i] - close[i-1]))
    atr = np.full(n, np.nan)
    if n > period:
        atr[period] = tr[1:period+1].mean()
        for i in range(period+1, n):
            atr[i] = (atr[i-1] * (period - 1) + tr[i]) / period
    return atr


def in_window(hour, windows):
    for (s, e) in windows:
        if s <= hour < e:
            return True
    return False


def run_fvg_full_simulate(df, atr_period=14, exit_margin_atr=0.5,
                           sl_atr=1.5, tp_atr=8.0,
                           max_fill_bars=100000, max_confirm_bars=100000,
                           windows=None, trend_filter=False):
    """
    df: DataFrame with columns open, high, low, close, datetime (sorted ascending)
    windows: list of (start_hour, end_hour) GMT tuples defining trading windows; None = all day
    Sequential engine: only one position open at a time. FVG detection/tracking
    continues regardless, but a new trade can only be OPENED once the previous
    is resolved (TP/SL hit).
    """
    o = df['open'].values
    h = df['high'].values
    l = df['low'].values
    c = df['close'].values
    hours = df['datetime'].dt.hour.values
    n = len(df)

    atr = wilder_atr(h, l, c, atr_period)

    trades = []

    bull_active = False
    bull_top = bull_bot = None
    bull_formed_i = -1
    bull_filled = False
    bull_filled_i = -1

    bear_active = False
    bear_top = bear_bot = None
    bear_formed_i = -1
    bear_filled = False
    bear_filled_i = -1

    position = None  # dict: side, entry, sl, tp, entry_i

    for i in range(3, n):
        atr_val = atr[i]
        if np.isnan(atr_val) or atr_val <= 0:
            continue

        window_ok = True if windows is None else in_window(hours[i], windows)

        # ---- manage open position first (check SL/TP against this bar) ----
        if position is not None:
            side = position['side']
            sl = position['sl']
            tp = position['tp']
            if side == 'long':
                hit_sl = l[i] <= sl
                hit_tp = h[i] >= tp
                if hit_sl and hit_tp:
                    # conservative: assume SL hit first (worst case)
                    r = -1.0
                    trades.append({**position, 'exit_i': i, 'exit_price': sl, 'r': r})
                    position = None
                elif hit_sl:
                    r = -1.0
                    trades.append({**position, 'exit_i': i, 'exit_price': sl, 'r': r})
                    position = None
                elif hit_tp:
                    r = (tp - position['entry']) / (position['entry'] - sl)
                    trades.append({**position, 'exit_i': i, 'exit_price': tp, 'r': r})
                    position = None
            else:
                hit_sl = h[i] >= sl
                hit_tp = l[i] <= tp
                if hit_sl and hit_tp:
                    r = -1.0
                    trades.append({**position, 'exit_i': i, 'exit_price': sl, 'r': r})
                    position = None
                elif hit_sl:
                    r = -1.0
                    trades.append({**position, 'exit_i': i, 'exit_price': sl, 'r': r})
                    position = None
                elif hit_tp:
                    r = (position['entry'] - tp) / (sl - position['entry'])
                    trades.append({**position, 'exit_i': i, 'exit_price': tp, 'r': r})
                    position = None

        # ---- FVG detection (only if window ok and slot free) ----
        if window_ok and not bull_active:
            if l[i] > h[i-2]:
                bull_active = True
                bull_bot = h[i-2]
                bull_top = l[i]
                bull_formed_i = i
                bull_filled = False

        if window_ok and not bear_active:
            if h[i] < l[i-2]:
                bear_active = True
                bear_top = l[i-2]
                bear_bot = h[i]
                bear_formed_i = i
                bear_filled = False

        # ---- bullish FVG state machine ----
        if bull_active:
            bars_since_formed = i - bull_formed_i
            if not bull_filled:
                if bars_since_formed > max_fill_bars:
                    bull_active = False
                elif bars_since_formed >= 1 and l[i] <= bull_bot:
                    bull_filled = True
                    bull_filled_i = i
            else:
                bars_since_filled = i - bull_filled_i
                trigger = bull_top + exit_margin_atr * atr_val
                if bars_since_filled > max_confirm_bars:
                    bull_active = False
                elif bars_since_filled >= 1 and c[i] > trigger:
                    if position is None:
                        entry = c[i]
                        sl = entry - sl_atr * atr_val
                        tp = entry + tp_atr * atr_val
                        position = {'side': 'long', 'entry': entry, 'sl': sl, 'tp': tp,
                                    'entry_i': i, 'entry_time': df['datetime'].iloc[i]}
                    bull_active = False

        # ---- bearish FVG state machine ----
        if bear_active:
            bars_since_formed_b = i - bear_formed_i
            if not bear_filled:
                if bars_since_formed_b > max_fill_bars:
                    bear_active = False
                elif bars_since_formed_b >= 1 and h[i] >= bear_top:
                    bear_filled = True
                    bear_filled_i = i
            else:
                bars_since_filled_b = i - bear_filled_i
                trigger = bear_bot - exit_margin_atr * atr_val
                if bars_since_filled_b > max_confirm_bars:
                    bear_active = False
                elif bars_since_filled_b >= 1 and c[i] < trigger:
                    if position is None:
                        entry = c[i]
                        sl = entry + sl_atr * atr_val
                        tp = entry - tp_atr * atr_val
                        position = {'side': 'short', 'entry': entry, 'sl': sl, 'tp': tp,
                                    'entry_i': i, 'entry_time': df['datetime'].iloc[i]}
                    bear_active = False

    return trades
