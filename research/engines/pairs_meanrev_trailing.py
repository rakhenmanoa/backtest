"""
Variante avec trailing stop : au lieu d'un TP fixe, on laisse courir la
position et on utilise un stop qui suit le prix (trailing), une fois que
le trade est en profit d'au moins `activate_atr` x ATR-proxy. Objectif :
capturer des mouvements plus larges que le TP fixe, tout en protegeant les
gains acquis.
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


def run_pairs_meanrev_trailing(ratio, atr_period=14, sma_period=20, dev_atr=2.0,
                                sl_atr=2.0, activate_atr=1.0, trail_atr=1.5,
                                hard_tp_atr=None):
    n = len(ratio)
    atr = ratio_atr_proxy(ratio, atr_period)
    ma = sma(ratio, sma_period)

    trades = []
    position = None

    start = max(atr_period, sma_period) + 1
    for i in range(start, n):
        atr_val = atr[i]

        if position is not None:
            side, entry, entry_i, risk_atr = (position['side'], position['entry'],
                                               position['entry_i'], position['risk_atr'])
            price = ratio[i]
            r = None; outcome = None
            sl = position['sl']

            if side == 'long':
                best = max(position['best'], price)
                position['best'] = best
                if best - entry >= activate_atr * risk_atr:
                    new_sl = best - trail_atr * risk_atr
                    if new_sl > sl:
                        sl = new_sl
                        position['sl'] = sl
                if hard_tp_atr is not None and price >= entry + hard_tp_atr*risk_atr:
                    r = (price - entry) / (entry - position['init_sl']); outcome='TP'
                elif price <= sl:
                    r = (sl - entry) / (entry - position['init_sl']); outcome = 'TRAIL' if sl > position['init_sl'] else 'SL'
            else:
                best = min(position['best'], price)
                position['best'] = best
                if entry - best >= activate_atr * risk_atr:
                    new_sl = best + trail_atr * risk_atr
                    if new_sl < sl:
                        sl = new_sl
                        position['sl'] = sl
                if hard_tp_atr is not None and price <= entry - hard_tp_atr*risk_atr:
                    r = (entry - price) / (position['init_sl'] - entry); outcome='TP'
                elif price >= sl:
                    r = (entry - sl) / (position['init_sl'] - entry); outcome = 'TRAIL' if sl < position['init_sl'] else 'SL'

            if r is not None:
                trades.append({**position, 'exit_i': i, 'r': r, 'outcome': outcome})
                position = None

        if position is None:
            if np.isnan(atr_val) or atr_val <= 0 or np.isnan(ma[i]):
                continue
            dev = ratio[i] - ma[i]
            if dev < -dev_atr*atr_val:
                entry = ratio[i]
                sl = entry - sl_atr*atr_val
                position = {'side':'long','entry':entry,'sl':sl,'init_sl':sl,
                            'risk_atr':atr_val,'entry_i':i,'best':entry}
            elif dev > dev_atr*atr_val:
                entry = ratio[i]
                sl = entry + sl_atr*atr_val
                position = {'side':'short','entry':entry,'sl':sl,'init_sl':sl,
                            'risk_atr':atr_val,'entry_i':i,'best':entry}

    return trades
