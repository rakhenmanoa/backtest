import pandas as pd, numpy as np, time
from mean_reversion_deep import run_mean_reversion_deep, summarize

timeframes = {
    'M1': 'exness_us30_all.pkl',
    'M5': 'exness_us30_M5.pkl',
    'M15': 'exness_us30_M15.pkl',
}

devs = [1.5, 2.0, 2.5, 3.0]
sl_tp_combos = [(1.0, 1.5), (1.0, 2.0), (1.5, 2.0), (1.5, 3.0)]

results = []
t0 = time.time()
for tf, path in timeframes.items():
    df = pd.read_pickle(path)
    print(f"=== {tf}: {len(df)} bougies ===", flush=True)
    for dev in devs:
        for sl, tp in sl_tp_combos:
            trades = run_mean_reversion_deep(df, dev_atr=dev, sl_atr=sl, tp_atr=tp, exclude_hour0=False)
            s = summarize(trades)
            results.append(dict(tf=tf, dev=dev, sl=sl, tp=tp, hour0_excluded=False, **s))
            print(f"  dev={dev} sl={sl} tp={tp}: n={s['n']} pct_tp={s['pct_tp']:.1f}% avgR_brut={s['avgR_brut']:+.3f} avgR_net={s['avgR_net']:+.3f}  ({time.time()-t0:.0f}s)", flush=True)

pd.DataFrame(results).to_csv('meanrev_deep_results.csv', index=False)
print("TOTAL", time.time()-t0)
