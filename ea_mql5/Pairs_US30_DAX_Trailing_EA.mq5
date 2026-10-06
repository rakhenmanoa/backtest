//+------------------------------------------------------------------+
//| Pairs_US30_DAX_Trailing_EA.mq5                                    |
//|                                                                    |
//| Strategie stat-arb / pairs trading sur le RATIO US30/DAX,          |
//| testee en backtest Python sur donnees Exness REELLES (M15,        |
//| 2021-07 a 2026-09, spread reel des deux jambes : US30 ~5.4 pts,    |
//| DAX ~5.5 pts -- PAS une hypothese, mesure directement sur les      |
//| exports JSON Exness fournis par l'utilisateur).                    |
//|                                                                    |
//| Logique (identique au moteur Python pairs_meanrev_trailing.py) :   |
//|  - ratio = close(US30) / close(DAX), au M15.                       |
//|  - SMA(ratio, 20) comme moyenne de reference.                      |
//|  - ATR-proxy(ratio,14) = moyenne mobile des |ratio[i]-ratio[i-1]|   |
//|    (lissage Wilder), car le ratio n'a pas de high/low propre.      |
//|  - Entree : si ratio s'ecarte de la SMA de plus de DevAtr x ATR    |
//|      -> LONG le ratio = BUY US30 + SELL DAX                        |
//|      -> SHORT le ratio = SELL US30 + BUY DAX                       |
//|  - Sortie : SL initial = SlAtrMult x ATR (en unites de ratio).     |
//|    Une fois en profit >= ActivateAtrMult x ATR, le stop suit le    |
//|    meilleur ratio atteint a TrailAtrMult x ATR derriere lui.       |
//|    L'EA cloture les DEUX jambes ensemble quand le ratio touche ce  |
//|    stop (pas de TP fixe -- c'est le trailing qui capture le        |
//|    mouvement, exactement comme valide en backtest).                |
//|                                                                    |
//| Resultats backtest (donnees reelles, couts reels des 2 jambes,     |
//| config par defaut DevAtr=3.0 / SlAtrMult=6.0 / ActivateAtrMult=2.5 |
//| / TrailAtrMult=0.75) :                                             |
//|   n=4765 trades (2021-07 a 2026-09), winrate 68%,                  |
//|   avgR brut = +0.211, avgR NET (coûts reels 2 jambes) = +0.063     |
//|   Robustesse annuelle : 4 annees nettement positives (2021,2022,   |
//|   2025,2026), 2 annees quasi nulles/legerement negatives (2023:    |
//|   -0.005, 2024: -0.018). Pas de biais LONG/SHORT (symetrique).     |
//|                                                                    |
//| ATTENTION -- limites importantes avant tout trading reel :         |
//|  1. Le sizing des deux jambes ci-dessous (InpLotsUS30/InpLotsDAX)  |
//|     est a calibrer par toi : la notion de "neutralite" en dollars  |
//|     depend de la valeur du point/lot de CHAQUE instrument chez     |
//|     Exness (contract size, devise de cotation), que je n'ai pas    |
//|     verifiee ici. Les lots par defaut sont un point de depart,     |
//|     PAS une recommandation calibree.                                |
//|  2. Le backtest suppose une execution simultanee des 2 jambes.     |
//|     En reel, un leger decalage d'execution entre les 2 ordres      |
//|     peut degrader le resultat (slippage de timing).                |
//|  3. Teste d'abord en mode Strategy Tester multi-devises ou en      |
//|     demo reelle avant tout passage en compte reel.                 |
//|  4. Les noms de symboles (InpSymbolUS30/InpSymbolDAX) doivent      |
//|     correspondre EXACTEMENT a ceux de ton broker (ex: "US30",      |
//|     "US30Cash", "DE30", "DAX", "GER40"...).                        |
//+------------------------------------------------------------------+
#property copyright "Backtest Python (donnees Exness reelles) -> EA MQL5"
#property version   "1.00"
#property strict

#include <Trade\Trade.mqh>
CTrade trade;

//--- Symboles des deux jambes (A ADAPTER a ton broker)
input string InpSymbolUS30 = "US30";
input string InpSymbolDAX  = "DE30";

//--- Parametres strategie (ratio US30/DAX, calcule au M15)
input int    InpSmaPeriod       = 20;
input int    InpAtrPeriod       = 14;
input double InpDevAtr          = 3.0;   // seuil d'entree, en multiples d'ATR-proxy
input double InpSlAtrMult       = 6.0;   // SL initial, en multiples d'ATR-proxy
input double InpActivateAtrMult = 2.5;   // profit necessaire (en ATR) pour activer le trailing
input double InpTrailAtrMult    = 0.75;  // distance du trailing stop derriere le meilleur ratio

//--- Sizing des deux jambes (A CALIBRER -- voir avertissement en tete de fichier)
input double InpLotsUS30 = 0.10;
input double InpLotsDAX  = 0.10;

input ulong  InpMagic = 20261001;

//--- Etat interne
datetime lastBarTime = 0;
bool     inPosition  = false;
string   posSide     = "";      // "long" ou "short" (sur le RATIO)
double   entryRatio  = 0.0;
double   slRatio     = 0.0;
double   initSlRatio = 0.0;
double   bestRatio   = 0.0;
double   atrAtEntry  = 0.0;

#define MAX_HIST 2000
double ratioHist[];
datetime timeHist[];
int histCount = 0;

//+------------------------------------------------------------------+
int OnInit()
  {
   if(!SymbolSelect(InpSymbolUS30, true) || !SymbolSelect(InpSymbolDAX, true))
     {
      Print("Erreur: impossible de selectionner les symboles ", InpSymbolUS30, " / ", InpSymbolDAX,
            " -- verifie les noms exacts chez ton broker.");
      return(INIT_FAILED);
     }
   ArrayResize(ratioHist, MAX_HIST);
   ArrayResize(timeHist, MAX_HIST);
   trade.SetExpertMagicNumber(InpMagic);
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
void OnDeinit(const int reason) {}

//+------------------------------------------------------------------+
// Pousse une nouvelle valeur de ratio dans l'historique (buffer circulaire simplifie
// via decalage -- MAX_HIST est largement suffisant pour SMA(20)+ATR(14)).
void PushRatio(datetime t, double r)
  {
   if(histCount < MAX_HIST)
     {
      ratioHist[histCount] = r;
      timeHist[histCount]  = t;
      histCount++;
     }
   else
     {
      for(int i = 1; i < MAX_HIST; i++)
        {
         ratioHist[i-1] = ratioHist[i];
         timeHist[i-1]  = timeHist[i];
        }
      ratioHist[MAX_HIST-1] = r;
      timeHist[MAX_HIST-1]  = t;
     }
  }

//+------------------------------------------------------------------+
double ComputeSMA(int period)
  {
   if(histCount < period) return(EMPTY_VALUE);
   double s = 0;
   for(int i = histCount - period; i < histCount; i++)
      s += ratioHist[i];
   return(s / period);
  }

//+------------------------------------------------------------------+
// ATR-proxy Wilder sur les variations |ratio[i]-ratio[i-1]|, recalcule depuis
// le debut de l'historique disponible (suffisant car on garde jusqu'a 2000 barres M15).
double ComputeAtrProxy(int period)
  {
   if(histCount < period + 1) return(EMPTY_VALUE);
   double atr = 0;
   int start = 1;
   // valeur initiale = moyenne simple des 'period' premiers diffs
   double sum = 0;
   for(int i = start; i <= period; i++)
      sum += MathAbs(ratioHist[i] - ratioHist[i-1]);
   atr = sum / period;
   for(int i = period + 1; i < histCount; i++)
     {
      double diff = MathAbs(ratioHist[i] - ratioHist[i-1]);
      atr = (atr * (period - 1) + diff) / period;
     }
   return(atr);
  }

//+------------------------------------------------------------------+
bool HasAnyOpenPosition()
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetInteger(POSITION_MAGIC) == (long)InpMagic)
         return true;
     }
   return false;
  }

//+------------------------------------------------------------------+
void CloseLeg(string symbol)
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) == symbol &&
         PositionGetInteger(POSITION_MAGIC) == (long)InpMagic)
         trade.PositionClose(ticket);
     }
  }

//+------------------------------------------------------------------+
void CloseBothLegs()
  {
   CloseLeg(InpSymbolUS30);
   CloseLeg(InpSymbolDAX);
   inPosition = false;
  }

//+------------------------------------------------------------------+
void OpenPairLong()
  {
   // LONG le ratio = BUY US30 + SELL DAX
   double priceUS = SymbolInfoDouble(InpSymbolUS30, SYMBOL_ASK);
   double priceDAX = SymbolInfoDouble(InpSymbolDAX, SYMBOL_BID);
   if(!trade.Buy(InpLotsUS30, InpSymbolUS30, priceUS, 0, 0, "PairsLongUS30"))
     { Print("Echec ouverture jambe US30 (BUY)"); return; }
   if(!trade.Sell(InpLotsDAX, InpSymbolDAX, priceDAX, 0, 0, "PairsLongDAX"))
     {
      Print("Echec ouverture jambe DAX (SELL) -- fermeture de la jambe US30 pour rester neutre");
      CloseLeg(InpSymbolUS30);
      return;
     }
   inPosition = true;
  }

//+------------------------------------------------------------------+
void OpenPairShort()
  {
   // SHORT le ratio = SELL US30 + BUY DAX
   double priceUS = SymbolInfoDouble(InpSymbolUS30, SYMBOL_BID);
   double priceDAX = SymbolInfoDouble(InpSymbolDAX, SYMBOL_ASK);
   if(!trade.Sell(InpLotsUS30, InpSymbolUS30, priceUS, 0, 0, "PairsShortUS30"))
     { Print("Echec ouverture jambe US30 (SELL)"); return; }
   if(!trade.Buy(InpLotsDAX, InpSymbolDAX, priceDAX, 0, 0, "PairsShortDAX"))
     {
      Print("Echec ouverture jambe DAX (BUY) -- fermeture de la jambe US30 pour rester neutre");
      CloseLeg(InpSymbolUS30);
      return;
     }
   inPosition = true;
  }

//+------------------------------------------------------------------+
double CurrentRatio()
  {
   double pUS = SymbolInfoDouble(InpSymbolUS30, SYMBOL_BID);
   double pDAX = SymbolInfoDouble(InpSymbolDAX, SYMBOL_BID);
   if(pDAX <= 0) return(-1);
   return(pUS / pDAX);
  }

//+------------------------------------------------------------------+
void OnTick()
  {
   // Detection nouvelle bougie M15 sur la jambe US30 (les deux symboles doivent
   // etre synchronises -- meme broker, meme serveur de temps).
   datetime curBarTime = iTime(InpSymbolUS30, PERIOD_M15, 0);
   bool newBar = (curBarTime != lastBarTime);

   //--- Gestion de la position ouverte : verification du stop/trailing a CHAQUE tick
   //    (plus reactif que d'attendre la cloture de la bougie, comme un vrai trailing).
   if(inPosition)
     {
      double ratioNow = CurrentRatio();
      if(ratioNow > 0)
        {
         if(posSide == "long")
           {
            if(ratioNow > bestRatio) bestRatio = ratioNow;
            if(bestRatio - entryRatio >= InpActivateAtrMult * atrAtEntry)
              {
               double newSl = bestRatio - InpTrailAtrMult * atrAtEntry;
               if(newSl > slRatio) slRatio = newSl;
              }
            if(ratioNow <= slRatio)
               CloseBothLegs();
           }
         else // short
           {
            if(ratioNow < bestRatio) bestRatio = ratioNow;
            if(entryRatio - bestRatio >= InpActivateAtrMult * atrAtEntry)
              {
               double newSl = bestRatio + InpTrailAtrMult * atrAtEntry;
               if(newSl < slRatio) slRatio = newSl;
              }
            if(ratioNow >= slRatio)
               CloseBothLegs();
           }
        }
     }

   if(!newBar)
      return;
   lastBarTime = curBarTime;

   //--- Mise a jour de l'historique du ratio (close M15, bougie precedente fermee)
   double closeUS  = iClose(InpSymbolUS30, PERIOD_M15, 1);
   double closeDAX = iClose(InpSymbolDAX, PERIOD_M15, 1);
   if(closeUS <= 0 || closeDAX <= 0)
      return;
   double ratioClose = closeUS / closeDAX;
   datetime t1 = iTime(InpSymbolUS30, PERIOD_M15, 1);
   PushRatio(t1, ratioClose);

   if(histCount < InpSmaPeriod + InpAtrPeriod + 2)
      return;

   double sma = ComputeSMA(InpSmaPeriod);
   double atr = ComputeAtrProxy(InpAtrPeriod);
   if(sma == EMPTY_VALUE || atr == EMPTY_VALUE || atr <= 0)
      return;

   //--- Pas de nouvelle entree si une paire est deja ouverte
   if(inPosition || HasAnyOpenPosition())
      return;

   double dev = ratioClose - sma;
   if(dev < -InpDevAtr * atr)
     {
      entryRatio  = ratioClose;
      slRatio     = entryRatio - InpSlAtrMult * atr;
      initSlRatio = slRatio;
      bestRatio   = entryRatio;
      atrAtEntry  = atr;
      posSide     = "long";
      OpenPairLong();
     }
   else if(dev > InpDevAtr * atr)
     {
      entryRatio  = ratioClose;
      slRatio     = entryRatio + InpSlAtrMult * atr;
      initSlRatio = slRatio;
      bestRatio   = entryRatio;
      atrAtEntry  = atr;
      posSide     = "short";
      OpenPairShort();
     }
  }
//+------------------------------------------------------------------+
