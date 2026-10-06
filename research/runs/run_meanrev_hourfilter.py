import pandas as pd, numpy as np, time
from mean_reversion_deep import run_mean_reversion_deep, summarize

df = pd.read_pickle('exness_us30_all.pkl')
print(f"M1: {len(df)} bougies", flush=True)

devs = [1.5, 2.0, 2.5, 3.0]
# sl/tp originaux +1 ATR chacun
sl_tp_combos = [(2.0, 2.5), (2.0, 3.0), (2.5, 3.0), (2.5, 4.0)]

window_options = {
    'toute_journee': None,
    'heures_fortes_4-7_11-12': [(4,7),(11,12)],
    'heures_fortes_larges_3-8_11-13': [(3,8),(11,13)],
}

results = []
t0 = time.time()
for wname, w in window_options.items():
    for dev in devs:
        for sl, tp in sl_tp_combos:
            trades = run_mean_reversion_deep(df, dev_atr=dev, sl_atr=sl, tp_atr=tp, windows=w)
            s = summarize(trades)
            results.append(dict(window=wname, dev=dev, sl=sl, tp=tp, **s))
            print(f"{wname} dev={dev} sl={sl} tp={tp}: n={s['n']} pct_tp={s['pct_tp']:.1f}% "
                  f"avgR_brut={s['avgR_brut']:+.3f} avgR_net={s['avgR_net']:+.3f}  ({time.time()-t0:.0f}s)", flush=True)

pd.DataFrame(results).to_csv('meanrev_hourfilter_results.csv', index=False)
print("TOTAL", time.time()-t0)
