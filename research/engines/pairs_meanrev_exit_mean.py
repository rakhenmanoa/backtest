"""
Variante : au lieu d'un TP fixe (tp_atr x ATR-proxy), on sort quand le ratio
retraverse sa moyenne mobile (retour complet a la moyenne) -- ce qui peut
capturer des mouvements plus grands que ceux limites par un TP fixe, mais
aussi en rater certains qui redescendent avant de toucher la moyenne.
On garde un SL fixe en multiple d'ATR pour limiter le risque, et on ajoute
un TP "plafond" optionnel tres large (safety net) pour eviter de rester
en position indefiniment si le ratio diverge longtemps.
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


def run_pairs_meanrev_exit_mean(ratio, atr_period=14, sma_period=20, dev_atr=2.0,
                                 sl_atr=2.0, max_hold=None, tp_cap_atr=None):
    """
    Entree identique (deviation ATR par rapport a SMA). Sortie :
      - SL fixe (sl_atr x ATR-proxy a l'entree)
      - TP = retour au niveau de la SMA courante (recalculee a chaque barre)
      - tp_cap_atr optionnel : TP plafond tres large en secours
      - max_hold optionnel : sortie au marche (close) apres N barres si rien d'autre
    """
    n = len(ratio)
    atr = ratio_atr_proxy(ratio, atr_period)
    ma = sma(ratio, sma_period)

    trades = []
    position = None

    start = max(atr_period, sma_period) + 1
    for i in range(start, n):
        atr_val = atr[i]
        if position is not None:
            side, sl, entry, entry_i = (position['side'], position['sl'],
                                         position['entry'], position['entry_i'])
            price = ratio[i]
            r = None; outcome = None

            if side == 'long':
                if price <= sl:
                    r = -1.0; outcome = 'SL'
                elif not np.isnan(ma[i]) and price >= ma[i]:
                    r = (price - entry) / (entry - sl); outcome = 'MEAN'
                elif tp_cap_atr is not None and price >= entry + tp_cap_atr * position['risk_atr']:
                    r = (price - entry) / (entry - sl); outcome = 'CAP'
            else:
                if price >= sl:
                    r = -1.0; outcome = 'SL'
                elif not np.isnan(ma[i]) and price <= ma[i]:
                    r = (entry - price) / (sl - entry); outcome = 'MEAN'
                elif tp_cap_atr is not None and price <= entry - tp_cap_atr * position['risk_atr']:
                    r = (entry - price) / (sl - entry); outcome = 'CAP'

            if r is None and max_hold is not None and (i - entry_i) >= max_hold:
                # sortie forcee au marche
                if side == 'long':
                    r = (price - entry) / (entry - sl)
                else:
                    r = (entry - price) / (sl - entry)
                outcome = 'TIME'

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
                position = {'side':'long','entry':entry,'sl':sl,'risk_atr':atr_val,'entry_i':i}
            elif dev > dev_atr*atr_val:
                entry = ratio[i]
                sl = entry + sl_atr*atr_val
                position = {'side':'short','entry':entry,'sl':sl,'risk_atr':atr_val,'entry_i':i}

    return trades


def summarize(trades):
    if not trades:
        return dict(n=0, winrate=float('nan'), avgR=float('nan'), sumR=0.0)
    rs = np.array([t['r'] for t in trades])
    n = len(rs)
    wr = (rs>0).mean()*100
    return dict(n=n, winrate=wr, avgR=rs.mean(), sumR=rs.sum())
