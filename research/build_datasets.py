"""
Reconstruit, a partir des fichiers .csv.gz du depot (exness/ et dukascopy/),
les DataFrames pickle utilises par les moteurs de backtest (research/engines).

Usage (depuis la racine du depot) :
    python research/build_datasets.py
Les fichiers sont ecrits dans research/work/ (ignore par git). Les scripts de
research/runs/ se lancent ensuite depuis ce dossier :
    cd research/work && PYTHONPATH=../engines python ../runs/run_meanrev_deep.py
"""
import glob, os
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
WORK = os.path.join(ROOT, 'research', 'work')
os.makedirs(WORK, exist_ok=True)
OHLC = ['datetime', 'open', 'high', 'low', 'close']


def load_exness(sym):
    files = sorted(glob.glob(f'{ROOT}/exness/{sym}/{sym}_M1_*.csv.gz'))
    df = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
    df['datetime'] = pd.to_datetime(df['datetime'], utc=True)
    df = df.sort_values('datetime').drop_duplicates('datetime').reset_index(drop=True)
    # spread brut MT5 en "points" ; precision de prix 0.1 -> 1 point = 0.1 unite de prix
    df['spread_price'] = df['spread'] * 0.1
    return df


def load_duka(sym, first_year=2016):
    files = sorted(glob.glob(f'{ROOT}/dukascopy/{sym}/{sym}_M1_*.csv.gz'))
    df = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
    return df[OHLC].sort_values('datetime').reset_index(drop=True)


def resample(df, rule):
    r = df.set_index('datetime')[OHLC[1:]].resample(rule, label='left', closed='left').agg(
        {'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'}).dropna()
    return r.reset_index()


# --- Exness US30 (M1 + spread) ---
us = load_exness('us30')
us_ohlc = us[OHLC]
us_ohlc.to_pickle(f'{WORK}/exness_us30_all.pkl')
us.drop(columns=['tick_volume', 'real_volume']).to_pickle(f'{WORK}/exness_us30_all_with_spread.pkl')
for name, rule in [('M5', '5min'), ('M15', '15min'), ('M30', '30min')]:
    resample(us_ohlc, rule).to_pickle(f'{WORK}/exness_us30_{name}.pkl')

# --- Exness DE30 / DAX : on ne garde que les barres M1 avec spread > 0 ---
dax = load_exness('de30')
dax = dax[dax['spread'] > 0].reset_index(drop=True)
dax.to_pickle(f'{WORK}/exness_dax_all_with_spread.pkl')

# --- Dukascopy US30 2021+ (reference de comparaison avec Exness) ---
duka = load_duka('us30')
duka[duka['datetime'] >= '2021-01-01'].reset_index(drop=True).to_pickle(f'{WORK}/duka_us30_all.pkl')

# --- Ratio US30/DAX en M15, donnees Exness reelles des deux jambes ---
def m15(df, suffix):
    return df.set_index('datetime').resample('15min', label='left', closed='left').agg(
        **{f'close_{suffix}': ('close', 'last'),
           f'spread_price_{suffix}': ('spread_price', 'mean')}).dropna().reset_index()

ratio = pd.merge(m15(us, 'us'), m15(dax, 'dax'), on='datetime', how='inner').sort_values('datetime').reset_index(drop=True)
ratio['ratio'] = ratio['close_us'] / ratio['close_dax']
ratio = ratio[['datetime', 'close_us', 'spread_price_us', 'close_dax', 'spread_price_dax', 'ratio']]
ratio.to_pickle(f'{WORK}/dax_us30_ratio_m15_REAL.pkl')

print('OK ->', WORK)
for f in sorted(os.listdir(WORK)):
    print(' ', f)
