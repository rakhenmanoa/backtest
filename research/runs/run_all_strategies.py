import pandas as pd, numpy as np, time
from engine_ict_v2b import run_fvg_full_simulate
from strategies import run_mean_reversion, run_trend_following, run_order_block, summarize

timeframes = ['M5', 'M15', 'M30']

results = []
t0 = time.time()

for tf in timeframes:
    df = pd.read_pickle(f'exness_us30_{tf}.pkl')
    print(f"=== {tf}: {len(df)} bougies ===", flush=True)

    # --- FVG (pas de fenetre) ---
    for margin in [0.25, 0.5]:
        for sl in [1.5, 2.0]:
            for tp in [4, 6, 8]:
                trades = run_fvg_full_simulate(df, exit_margin_atr=margin, sl_atr=sl, tp_atr=tp, windows=None)
                s = summarize(trades)
                results.append(dict(strategy='FVG', tf=tf, params=f"margin={margin},sl={sl},tp={tp}", **s))
    print(f"  FVG done, {time.time()-t0:.0f}s", flush=True)

    # --- Mean reversion ---
    for dev in [1.5, 2.0, 2.5]:
        for sl in [1.0, 1.5]:
            for tp in [1.5, 2.0, 3.0]:
                trades = run_mean_reversion(df, dev_atr=dev, sl_atr=sl, tp_atr=tp)
                s = summarize(trades)
                results.append(dict(strategy='MeanReversion', tf=tf, params=f"dev={dev},sl={sl},tp={tp}", **s))
    print(f"  MeanReversion done, {time.time()-t0:.0f}s", flush=True)

    # --- Trend following ---
    for fast, slow in [(10, 30), (20, 50), (20, 100)]:
        for sl in [1.5, 2.0]:
            for tp in [3, 4, 6]:
                trades = run_trend_following(df, ema_fast=fast, ema_slow=slow, sl_atr=sl, tp_atr=tp)
                s = summarize(trades)
                results.append(dict(strategy='TrendFollowing', tf=tf, params=f"fast={fast},slow={slow},sl={sl},tp={tp}", **s))
    print(f"  TrendFollowing done, {time.time()-t0:.0f}s", flush=True)

    # --- Order Block ---
    for sl in [1.5, 2.0]:
        for tp in [3, 4, 6]:
            trades = run_order_block(df, sl_atr=sl, tp_atr=tp)
            s = summarize(trades)
            results.append(dict(strategy='OrderBlock', tf=tf, params=f"sl={sl},tp={tp}", **s))
    print(f"  OrderBlock done, {time.time()-t0:.0f}s", flush=True)

pd.DataFrame(results).to_csv('all_strategies_results.csv', index=False)
print("TOTAL TIME", time.time()-t0)
