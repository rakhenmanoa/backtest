import pandas as pd, numpy as np, time
from rsi_reversal_confirm import run_rsi_reversal_confirm, summarize
from engine_ict_v2b import wilder_atr

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
    # ATR moyen pour estimer le cout du spread en R
    h,l,c = df['high'].values, df['low'].values, df['close'].values
    atr_vals = wilder_atr(h,l,c,14)
    atr_mean = np.nanmean(atr_vals)
    for sl in sls:
        for tp in tps:
            trades = run_rsi_reversal_confirm(df, sl_atr=sl, tp_atr=tp)
            s = summarize(trades)
            spread_cost_R = 7.0 / (sl * atr_mean) if s['n'] else float('nan')
            avgR_net = s['avgR'] - spread_cost_R if s['n'] else float('nan')
            results.append(dict(tf=tf, sl=sl, tp=tp, atr_mean=atr_mean, spread_cost_R=spread_cost_R,
                                 avgR_net=avgR_net, **s))
            print(f"  sl={sl} tp={tp} n={s['n']} pct_tp={s['pct_tp']:.1f}% avgR_brut={s['avgR']:+.3f} "
                  f"cout_spread={spread_cost_R:.3f}R avgR_net={avgR_net:+.3f}  ({time.time()-t0:.0f}s)", flush=True)

pd.DataFrame(results).to_csv('rsi_confirm_sweep_results.csv', index=False)
print("TOTAL", time.time()-t0)
