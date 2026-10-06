# Backtest JP225 : retour à la moyenne sur le VWAP

> **Avertissement : résultats non concluants.**
> Malheureusement, aucune stratégie testée dans ce dépôt n'a démontré d'avantage fiable et rentable. De plus, **des bogues et des biais de backtest ont faussé une partie des résultats** : artefacts de la bougie d'ouverture de 00h GMT (écarts de prix non exploitables), simulations dont le moteur a été reconstruit après une perte de code et dont les chiffres ne coïncident pas avec les versions antérieures, coûts de spread parfois estimés avec des valeurs différentes selon les tests (7,0 puis 5,35 points sur l'US30), exécution des stops vérifiée sur la clôture seule pour le ratio US30/DAX, et nombreux balayages de paramètres sur les mêmes données (risque de surajustement). Les chiffres affichés ci-dessous, y compris le R net positif du pairs trading, sont à considérer comme des pistes de recherche et **non comme une preuve de rentabilité**. Ne pas trader en réel sur cette base.


Tests rétrospectifs d'une stratégie intraday de retour à la moyenne sur l'indice **Nikkei 225 coté en yen (JPXJPY)**, à partir de données minute Dukascopy de 2021 à 2023.

## La stratégie

Les bougies d'une minute sont regroupées en bougies de 5 minutes. Les indicateurs utilisés sont :

- **VWAP** journalier, approximé par la moyenne cumulée du prix typique (les données n'ont pas de volume exploitable)
- **ATR(14)** sur 5 minutes
- **RSI(2)** sur 5 minutes
- **ADX(14)** sur 15 minutes, comme filtre de tendance

**Conditions d'entrée** (uniquement quand l'ADX 15 min est sous 25, donc sans tendance marquée) :

| Sens | RSI(2) | Écart au VWAP |
|------|--------|---------------|
| Achat | < 10 | clôture ≤ VWAP − 1,5 × ATR |
| Vente | > 95 | clôture ≥ VWAP + 2 × ATR |

**Sorties** :

- **Objectif** : retour au VWAP
- **Stop** : 1,2 × ATR depuis le prix d'entrée
- **Délai maximum** : 12 bougies (1 heure), sortie à la clôture

Les résultats sont exprimés en **R** (multiples du risque initial). Une perte au stop vaut donc −1 R.

## Contenu du dépôt

| Fichier | Rôle |
|---------|------|
| `backtest_2023.py` | Backtest 2023, toutes heures, avec le détail des trades et des bougies 5 min |
| `backtest_2023_europe.py` | Backtest 2023, session Europe uniquement (7h–16h) |
| `backtest_2021_2022_europe.py` | Backtest 2021 et 2022, session Europe, par année et cumulé |
| `backtest_2021_2023_europe_monthly.py` | Résultats mensuels 2021–2023, session Europe |
| `backtest_2021_2023_sessions_monthly.py` | Résultats mensuels 2021–2023 par session : Asie (0h–8h), Europe (7h–16h), Amérique (13h–21h) et journée entière |
| `dukascopy/` | Données minute JPXJPY de Dukascopy, un fichier par année |
| `.github/workflows/` | Un workflow GitHub Actions par script |

Les heures des sessions sont celles des horodatages des fichiers Dukascopy.

## Lancer un backtest

En local, depuis la racine du dépôt :

```bash
pip install pandas numpy
python backtest_2021_2023_sessions_monthly.py
```

Chaque script affiche les statistiques principales (nombre de trades, taux de réussite, R net, profit factor, drawdown maximum) et écrit les trades dans des fichiers CSV à la racine.

Sur GitHub, chaque workflow se lance automatiquement quand son script ou les données changent. On peut aussi le lancer à la main depuis l'onglet **Actions**. Les fichiers CSV de résultats sont alors disponibles en téléchargement (artefacts) dans le détail de l'exécution.

## Format des données

Format ASCII Dukascopy, une bougie d'une minute par ligne :

```
AAAAMMJJ HHMMSS;ouverture;plus haut;plus bas;clôture;volume
```

Les scripts acceptent aussi les virgules, points-virgules ou espaces comme séparateurs.

---

# Étude multi-instruments : US30 / DE30 (DAX), Exness vs Dukascopy

> Résultats non concluants, et biais de backtest connus : voir l'avertissement en haut de ce fichier.

Cette seconde partie regroupe les données et le code de l'étude de stratégies sur l'indice US30 et le DAX (DE30), menée sur les données réelles du courtier Exness puis comparée à Dukascopy.

## Données

Toutes les données sont des bougies d'une minute, compressées (`.csv.gz`), un fichier par année. Aucune n'a été modifiée : seuls le format (JSON ou CSV géant vers CSV compressé) et le découpage par année changent.

| Dossier | Contenu | Période | Colonnes |
|---------|---------|---------|----------|
| `exness/us30/` | US30, export MT5 Exness | 2021-01 à 2026-09 | `datetime, open, high, low, close, tick_volume, spread, real_volume` |
| `exness/de30/` | DE30 (DAX), export MT5 Exness | 2021 à 2026-10 | idem |
| `dukascopy/us30/` | US30, prix bid Dukascopy | 2016 à 2026-08 | `timestamp (ms UTC), open, high, low, close` |
| `dukascopy/de30/` | DE30, prix bid Dukascopy | 2016 à 2026-08 | idem |
| `dukascopy/jp225/` | JP225 (Nikkei), Dukascopy | 2016 à 2020 | idem |
| `dukascopy/xauusd/` | Or (XAUUSD), Dukascopy | 2021 à 2026-08 | idem |

À savoir avant d'utiliser les données :

- **Spread Exness** : la colonne `spread` est en « points » MT5 bruts. La précision de prix est de 0,1, donc `spread en unités de prix = spread × 0,1` (spread moyen mesuré : US30 ≈ 5,4, DE30 ≈ 5,5). Dukascopy ne fournit pas de spread.
- **Début de 2021 chez Exness** : les premières lignes de `exness/us30/us30_M1_2021.csv.gz` et `exness/de30/de30_M1_2021.csv.gz` sont des bougies journalières avec `spread = 0` (historique M1 indisponible à cette date). Pour le DE30, les vraies bougies M1 démarrent le 2021-07-16. `build_datasets.py` écarte les lignes à spread nul pour le DE30.
- **Exness et Dukascopy ne sont pas interchangeables** : seuls ~16 % des signaux coïncident entre les deux flux, avec un décalage de prix moyen de +19 à +29 points sur l'US30. Les résultats sur Dukascopy ne se transposent pas tels quels au courtier.
- Les fichiers `dukascopy/DAT_ASCII_JPXJPY_M1_*.csv` de la première partie sont laissés à leur place, car les scripts et workflows existants les référencent.

## Code de l'étude (`research/`)

| Dossier | Contenu |
|---------|---------|
| `research/build_datasets.py` | Reconstruit les DataFrames pickle (M1, M5, M15, M30, spreads, ratio US30/DAX) depuis les `.csv.gz`, dans `research/work/` (ignoré par git). Vérifié identique aux jeux utilisés pendant l'étude. |
| `research/engines/` | Moteurs de backtest : FVG (comblement de gap), RSI (avec ou sans confirmation, filtre de tendance), retour à la moyenne, suivi de tendance, Order Block, pairs trading US30/DAX (sortie fixe, retour à la moyenne, trailing stop). |
| `research/runs/` | Scripts de balayage de paramètres. `run_pairs_trailing.py` reproduit le résultat final. |
| `research/results/`, `research/logs/` | Sorties CSV et journaux des balayages. |
| `ea_mql5/` | Les Expert Advisors MetaTrader 5 produits pendant l'étude (dont `Pairs_US30_DAX_Trailing_EA.mq5`). |
| `results/pdf/` | Synthèses PDF des stratégies étudiées (FVG, JP225, retour à la moyenne). |
| `results/indicateurs/` | Versions successives de l'indicateur FVG (fichiers texte). |
| `autres/` | Données hors périmètre principal : `jp225_m4`, `jp225_m5`, `usdjpy_m4`, `usdjpy_m5` (bougies de 4 et 5 minutes, format `AAAAMMJJ HHMMSS;o;h;l;c;volume`, compressées en `.csv.gz`). Origine non précisée. |

```bash
pip install pandas numpy
python research/build_datasets.py
cd research/work
PYTHONPATH=../engines python ../runs/run_pairs_trailing.py
```

## Principaux résultats

R net = résultat par trade en multiples du risque, après coût réel du spread, calculé trade par trade.

- **FVG, RSI, retour à la moyenne et suivi de tendance sur l'US30 seul** : aucune configuration rentable une fois le spread réel appliqué. Plusieurs résultats flatteurs venaient d'un artefact : les écarts de prix à la bougie d'ouverture de 00h GMT, non exploitables en pratique. Le filtrage doit se faire dans la simulation, pas après coup.
- **Pairs trading sur le ratio US30/DAX avec trailing stop** (SMA 20, entrée à 3,0 ATR d'écart, stop initial 6 ATR, trailing activé à 2,5 ATR et placé à 0,75 ATR du meilleur ratio) : 4 765 trades, 68 % de réussite, **R net moyen +0,063** avec les spreads réels des deux jambes (+0,211 avant coûts). Long et short sont symétriques (+0,062 et +0,064).
- **Robustesse limitée** : 4 années sur 6 nettement positives (2021, 2022, 2025, 2026), 2023 et 2024 proches de zéro ou légèrement négatives. Un trailing stop remplace avantageusement le take-profit fixe, qui ne rapportait rien net de coûts.
- Un raccourcissement de la SMA à 3 périodes améliorait le R brut mais détériorait le R net : artefact de coût, la distance de stop en unités de ratio devenant plus courte pour un coût fixe.
