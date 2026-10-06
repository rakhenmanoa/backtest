//+------------------------------------------------------------------+
//| MeanReversion_EA_M1.mq5                                           |
//| Strategie Mean Reversion testee en backtest Python sur donnees    |
//| Exness reelles (M1, 2021-2026).                                    |
//|                                                                    |
//| Logique :                                                          |
//|  - SMA(SmaPeriod) comme moyenne de reference.                     |
//|  - Ecart = Close - SMA. Si ecart < -DevAtr x ATR -> LONG (prix     |
//|    trop bas par rapport a la moyenne, on parie sur le retour).    |
//|    Si ecart > +DevAtr x ATR -> SHORT.                              |
//|  - SL = SlAtrMult x ATR, TP = TpAtrMult x ATR.                     |
//|  - Une seule position ouverte a la fois. Aucune fenetre horaire   |
//|    par defaut (le filtre horaire a degrade les resultats en       |
//|    backtest -- il concentre les trades sur les heures a faible    |
//|    ATR ou le spread pese proportionnellement plus).                |
//|                                                                    |
//|  Config par defaut = meilleure trouvee en backtest (la plus proche |
//|  de la rentabilite, mais toujours legerement negative net du      |
//|  spread reel Exness ~7 points) :                                   |
//|    DevAtr=1.5, SlAtrMult=5.0, TpAtrMult=8.0                        |
//|  avgR net backtest ~ -0.09 (spread reel). Seuil de rentabilite    |
//|  estime ~2.85 points de spread (soit ~2.4x plus serre que le      |
//|  spread moyen Exness observe). A ne pas trader en reel sans        |
//|  verifier le spread effectif de ton compte sur US30.               |
//+------------------------------------------------------------------+
#property copyright "Backtest Python -> EA MQL5"
#property version   "1.00"
#property strict

#include <Trade\Trade.mqh>
CTrade trade;

//--- Parametres Mean Reversion
input int    InpSmaPeriod   = 20;
input double InpDevAtr      = 1.5;    // ecart declencheur, en multiples d'ATR

//--- Parametres ATR / SL / TP
input int    InpAtrPeriod   = 14;
input double InpSlAtrMult   = 5.0;
input double InpTpAtrMult   = 8.0;

//--- Fenetre horaire optionnelle (desactivee par defaut = trade toute la journee)
input bool   InpUseSession    = false;
input int    InpSessionStartH = 7;
input int    InpSessionEndH   = 21;

//--- Exclusion optionnelle de l'heure d'ouverture de journee (artefact identifie en backtest,
//    impact plus faible ici que sur RSI mais laisse en option)
input bool   InpExcludeHour0  = false;
input int    InpExcludedHour  = 0;

input double InpLots  = 0.10;
input ulong  InpMagic = 20260927;

//--- Handles indicateurs
int smaHandle;
int atrHandle;

double smaBuf[];
double atrBuf[];

datetime lastBarTime = 0;

//+------------------------------------------------------------------+
int OnInit()
  {
   smaHandle = iMA(_Symbol, PERIOD_M1, InpSmaPeriod, 0, MODE_SMA, PRICE_CLOSE);
   atrHandle = iATR(_Symbol, PERIOD_M1, InpAtrPeriod);

   if(smaHandle == INVALID_HANDLE || atrHandle == INVALID_HANDLE)
     {
      Print("Erreur creation des handles indicateurs");
      return(INIT_FAILED);
     }

   ArraySetAsSeries(smaBuf, true);
   ArraySetAsSeries(atrBuf, true);

   trade.SetExpertMagicNumber(InpMagic);
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   IndicatorRelease(smaHandle);
   IndicatorRelease(atrHandle);
  }

//+------------------------------------------------------------------+
bool HasOpenPosition()
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) == _Symbol &&
         PositionGetInteger(POSITION_MAGIC) == (long)InpMagic)
         return true;
     }
   return false;
  }

//+------------------------------------------------------------------+
bool OpenPosition(ENUM_ORDER_TYPE orderType, double atrVal, bool &alreadyOpenedFlag)
  {
   if(HasOpenPosition() || alreadyOpenedFlag)
      return false;

   double price = (orderType == ORDER_TYPE_BUY)
                  ? SymbolInfoDouble(_Symbol, SYMBOL_ASK)
                  : SymbolInfoDouble(_Symbol, SYMBOL_BID);

   double sl, tp;
   if(orderType == ORDER_TYPE_BUY)
     {
      sl = price - InpSlAtrMult * atrVal;
      tp = price + InpTpAtrMult * atrVal;
     }
   else
     {
      sl = price + InpSlAtrMult * atrVal;
      tp = price - InpTpAtrMult * atrVal;
     }

   int digits = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   sl = NormalizeDouble(sl, digits);
   tp = NormalizeDouble(tp, digits);

   bool ok;
   if(orderType == ORDER_TYPE_BUY)
      ok = trade.Buy(InpLots, _Symbol, price, sl, tp, "MeanReversion");
   else
      ok = trade.Sell(InpLots, _Symbol, price, sl, tp, "MeanReversion");

   if(ok)
      alreadyOpenedFlag = true;

   return ok;
  }

//+------------------------------------------------------------------+
bool InTradingWindow(datetime t)
  {
   if(!InpUseSession)
      return true;
   MqlDateTime dt;
   TimeToStruct(t, dt);
   int h = dt.hour;
   if(InpSessionStartH <= InpSessionEndH)
      return (h >= InpSessionStartH && h < InpSessionEndH);
   return (h >= InpSessionStartH || h < InpSessionEndH);
  }

//+------------------------------------------------------------------+
bool IsExcludedHour(datetime t)
  {
   if(!InpExcludeHour0)
      return false;
   MqlDateTime dt;
   TimeToStruct(t, dt);
   return (dt.hour == InpExcludedHour);
  }

//+------------------------------------------------------------------+
void OnTick()
  {
   datetime curBarTime = iTime(_Symbol, PERIOD_M1, 0);
   if(curBarTime == lastBarTime)
      return; // une seule fois par nouvelle bougie M1 fermee
   lastBarTime = curBarTime;

   if(Bars(_Symbol, PERIOD_M1) < InpSmaPeriod + InpAtrPeriod + 5)
      return;

   if(CopyBuffer(smaHandle, 0, 1, 1, smaBuf) < 1) return; // SMA de la derniere bougie fermee (shift 1)
   if(CopyBuffer(atrHandle, 0, 1, 1, atrBuf) < 1) return;

   double atrVal = atrBuf[0];
   double smaVal = smaBuf[0];
   if(atrVal <= 0)
      return;

   double close1 = iClose(_Symbol, PERIOD_M1, 1);
   datetime time1 = iTime(_Symbol, PERIOD_M1, 1);

   if(!InTradingWindow(time1) || IsExcludedHour(time1))
      return;

   if(HasOpenPosition())
      return; // une seule position a la fois, comme dans le backtest

   double dev = close1 - smaVal;
   bool positionOpenedThisTick = false;

   if(dev < -InpDevAtr * atrVal)
     {
      // prix trop bas par rapport a la moyenne -> LONG
      OpenPosition(ORDER_TYPE_BUY, atrVal, positionOpenedThisTick);
     }
   else if(dev > InpDevAtr * atrVal)
     {
      // prix trop haut par rapport a la moyenne -> SHORT
      OpenPosition(ORDER_TYPE_SELL, atrVal, positionOpenedThisTick);
     }
  }
//+------------------------------------------------------------------+
