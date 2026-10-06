import pandas as pd, numpy as np, time, itertools
from engine_ict_v2b import run_fvg_full_simulate

exness = pd.read_pickle('exness_us30_all.pkl')
windows = [(14, 21)]

margins = [0.0, 0.25, 0.5, 1.0]
sls = [1.0, 1.5, 2.0, 2.5, 3.0]
tps = [3, 4, 6, 8, 10, 12]

results = []
t0 = time.time()
count = 0
total = len(margins)*len(sls)*len(tps)
for margin in margins:
    for sl in sls:
        for tp in tps:
            trades = run_fvg_full_simulate(exness, exit_margin_atr=margin, sl_atr=sl, tp_atr=tp, windows=windows)
            count += 1
            if trades:
                rs = np.array([t['r'] for t in trades])
                n = len(rs)
                wr = (rs > 0).mean() * 100
                avgR = rs.mean()
                sumR = rs.sum()
            else:
                n, wr, avgR, sumR = 0, np.nan, np.nan, 0.0
            results.append(dict(margin=margin, sl=sl, tp=tp, n=n, winrate=wr, avgR=avgR, sumR=sumR))
            if count % 20 == 0:
                print(f"{count}/{total} done, elapsed {time.time()-t0:.0f}s")

res_df = pd.DataFrame(results)
res_df.to_csv('sweep_results.csv', index=False)
print("TOTAL TIME", time.time()-t0)
