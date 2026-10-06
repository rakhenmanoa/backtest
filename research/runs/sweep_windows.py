import pandas as pd, numpy as np, time
from engine_ict_v2b import run_fvg_full_simulate

exness = pd.read_pickle('exness_us30_all.pkl')

window_options = {
    'toute_journee': None,
    '13h-20h': [(13,20)],
    '7h-14h': [(7,14)],
    '0h-24h_sauf_nuit(6-14)': [(6,14)],
    '14h-21h(ref)': [(14,21)],
    '20h-24h+0h-6h(session_asie)': [(20,24),(0,6)],
}

margin=0.5
sls = [1.5, 2.0, 2.5]
tps = [4, 6, 8]

results = []
t0=time.time()
count=0
total = len(window_options)*len(sls)*len(tps)
for wname, w in window_options.items():
    for sl in sls:
        for tp in tps:
            trades = run_fvg_full_simulate(exness, exit_margin_atr=margin, sl_atr=sl, tp_atr=tp, windows=w)
            count+=1
            if trades:
                rs = np.array([t['r'] for t in trades])
                n=len(rs); wr=(rs>0).mean()*100; avgR=rs.mean(); sumR=rs.sum()
            else:
                n,wr,avgR,sumR=0,np.nan,np.nan,0.0
            results.append(dict(window=wname, sl=sl, tp=tp, n=n, winrate=wr, avgR=avgR, sumR=sumR))
            print(f"{count}/{total} {wname} sl={sl} tp={tp} n={n} wr={wr:.1f} avgR={avgR:+.3f}", flush=True)

pd.DataFrame(results).to_csv('sweep_windows_results.csv', index=False)
print("TOTAL TIME", time.time()-t0)
