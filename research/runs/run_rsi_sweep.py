import pandas as pd, numpy as np, time
from rsi_strategy import run_rsi_reversal, summarize_rsi

timeframes = {
    'M1': 'exness_us30_all.pkl',
    'M5': 'exness_us30_M5.pkl',
    'M15': 'exness_us30_M15.pkl',
}

sls = [1.0, 1.5, 2.0]
tps = [2, 3, 4, 6]

results = []
t0 = time.time()
for tf, path in timeframes.items():
    df = pd.read_pickle(path)
    print(f"=== {tf}: {len(df)} bougies ===", flush=True)
    for sl in sls:
        for tp in tps:
            trades = run_rsi_reversal(df, sl_atr=sl, tp_atr=tp)
            s = summarize_rsi(trades)
            results.append(dict(tf=tf, sl=sl, tp=tp, **s))
            print(f"  sl={sl} tp={tp} n={s['n']} wr(TP%)={s['pct_tp']:.1f} avgR={s['avgR']:+.3f} mfe_perdants={s['avg_mfe_losers']:.2f}R  ({time.time()-t0:.0f}s)", flush=True)

pd.DataFrame(results).to_csv('rsi_sweep_results.csv', index=False)
print("TOTAL", time.time()-t0)
