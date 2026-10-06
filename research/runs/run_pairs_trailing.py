"""
Pairs trading US30/DAX (ratio) avec trailing stop, donnees Exness reelles des
deux jambes, cout reel des deux spreads. Reproduit le resultat final de l'etude.
Lancer depuis research/work/ apres build_datasets.py :
    PYTHONPATH=../engines python ../runs/run_pairs_trailing.py
"""
import pandas as pd
from pairs_meanrev_trailing import run_pairs_meanrev_trailing

m = pd.read_pickle('dax_us30_ratio_m15_REAL.pkl')
ratio, times = m['ratio'].values, m['datetime'].values
rel_cost = (m['spread_price_us'].mean() / m['close_us'].mean()
            + m['spread_price_dax'].mean() / m['close_dax'].mean())
print(f"spread US30 moyen {m['spread_price_us'].mean():.2f} | DAX {m['spread_price_dax'].mean():.2f} | cout relatif combine {rel_cost:.6f}")


def stats(trades):
    t = pd.DataFrame(trades)
    t['risk'] = (t['entry'] - t['init_sl']).abs()
    t['r_net'] = t['r'] - t['entry'] * rel_cost / t['risk']
    t['year'] = pd.to_datetime(times[t['entry_i'].values]).year
    return t


CFG = dict(sma_period=20, dev_atr=3.0, sl_atr=6.0, activate_atr=2.5, trail_atr=0.75)
t = stats(run_pairs_meanrev_trailing(ratio, **CFG))
print(f"\nConfig {CFG}\nn={len(t)} winrate={100*(t['r']>0).mean():.1f}% avgR_brut={t['r'].mean():+.3f} avgR_net={t['r_net'].mean():+.3f}")
print(t.groupby('year').agg(n=('r', 'size'), avgR_brut=('r', 'mean'), avgR_net=('r_net', 'mean'), sumR_net=('r_net', 'sum')).round(3))
print(t.groupby('side').agg(n=('r', 'size'), avgR_net=('r_net', 'mean')).round(3))
