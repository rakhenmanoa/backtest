import pandas as pd, numpy as np, time
from rsi_windows_atr import run_rsi_reversal_windows_atr, summarize

timeframes = {
    'M1': 'exness_us30_all.pkl',
    'M5': 'exness_us30_M5.pkl',
    'M15': 'exness_us30_M15.pkl',
}

sl_tp_combos = [(1.0, 4), (1.0, 6), (1.5, 3)]
window_options = {
    'toute_journee': None,
    '14h-21h': [(14,21)],
    '7h-14h': [(7,14)],
    '6h-14h': [(6,14)],
    '13h-20h': [(13,20)],
}
atr_filters = [1.0, 1.3, 1.6, 2.0]  # 1.0 = pas de filtre

results = []
t0 = time.time()
count = 0
total = len(timeframes)*len(sl_tp_combos)*len(window_options)*len(atr_filters)
for tf, path in timeframes.items():
    df = pd.read_pickle(path)
    for sl, tp in sl_tp_combos:
        for wname, w in window_options.items():
            for af in atr_filters:
                trades = run_rsi_reversal_windows_atr(df, sl_atr=sl, tp_atr=tp, windows=w, atr_filter_mult=af)
                s = summarize(trades)
                results.append(dict(tf=tf, sl=sl, tp=tp, window=wname, atr_filter=af, **s))
                count += 1
                if count % 20 == 0:
                    print(f"{count}/{total} ({time.time()-t0:.0f}s)", flush=True)

pd.DataFrame(results).to_csv('rsi_windows_atr_results.csv', index=False)
print("TOTAL", time.time()-t0)
