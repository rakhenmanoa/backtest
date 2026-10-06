import pandas as pd, numpy as np, time
from rsi_reversal_confirm_trend import run_rsi_confirm_trend, summarize

df = pd.read_pickle('exness_us30_all.pkl')
print(f"M1: {len(df)} bougies", flush=True)

sl_tp_combos = [(1.0, 3), (1.0, 4), (1.0, 6), (1.5, 3)]

results = []
t0 = time.time()
for sl, tp in sl_tp_combos:
    for trend_filter in [False, True]:
        trades = run_rsi_confirm_trend(df, sl_atr=sl, tp_atr=tp, trend_filter=trend_filter,
                                        exclude_hour0=True, ema_fast=50, ema_slow=200)
        s = summarize(trades)
        results.append(dict(sl=sl, tp=tp, trend_filter=trend_filter, **s))
        print(f"sl={sl} tp={tp} trend_filter={trend_filter}: n={s['n']} pct_tp={s['pct_tp']:.1f}% "
              f"avgR_brut={s['avgR_brut']:+.3f} avgR_net={s['avgR_net']:+.3f} sumR_net={s['sumR_net']:+.1f}  ({time.time()-t0:.0f}s)", flush=True)

pd.DataFrame(results).to_csv('trend_filter_results.csv', index=False)
print("TOTAL", time.time()-t0)
