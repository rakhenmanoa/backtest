# Backtest JP225 : retour à la moyenne sur le VWAP

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
