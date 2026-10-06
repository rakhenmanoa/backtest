//+------------------------------------------------------------------+
//| RSI_Reversal_Confirm_EA_M1.mq5                                    |
//| Strategie RSI(14) reversal AVEC confirmation de retournement,     |
//| testee en backtest Python sur donnees Exness reelles (M1).        |
//|                                                                    |
//| Logique (identique au moteur Python valide) :                     |
//|  1. Pic local de surachat: RSI(bougie j) > RsiHigh ET              |
//|     High(j) > High(j-1) ET High(j) > High(j+1)  -> on arme une    |
//|     attente de confirmation SHORT, seuil = Low(j).                |
//|  2. On attend (jusqu'a MaxWaitBars bougies) que le prix cloture   |
//|     sous ce seuil -> entree SHORT au marche.                      |
//|  3. Annulation si RSI repasse sous RsiCancelHigh avant confirmation|
//|     ou si MaxWaitBars est depasse.                                 |
//|  Symetrique pour un creux de survente -> LONG.                     |
//|                                                                    |
//|  SL = 1.5 x ATR(14), TP = 3.0 x ATR(14) (parametrable).            |
//|  Une seule position ouverte a la fois (blocage sequentiel, comme  |
//|  dans le backtest). Aucune fenetre horaire par defaut (trade toute |
//|  la journee) -- activable via les parametres de session.          |
//|                                                                    |
//|  ATTENTION (resultats du backtest sur donnees Exness reelles) :   |
//|  cette config brute n'a PAS montre d'edge net des couts reels de  |
//|  spread sur M1 (avgR net negatif dans toutes les variantes         |
//|  testees). Ce script est fourni tel que demande, a des fins de    |
//|  test/demo -- pas comme strategie validee rentable.                |
//+------------------------------------------------------------------+
#property copyright "Backtest Python -> EA MQL5"
#property version   "1.00"
#property strict

#include <Trade\Trade.mqh>
CTrade trade;

//--- Parametres RSI
input int    InpRsiPeriod      = 14;
input double InpRsiHigh        = 70.0;
input double InpRsiLow         = 30.0;
input double InpRsiCancelHigh  = 50.0;   // annule l'attente SHORT si RSI repasse sous ce niveau
input double InpRsiCancelLow   = 50.0;   // annule l'attente LONG si RSI repasse au-dessus de ce niveau
input int    InpMaxWaitBars    = 10;     // nb max de bougies pour la confirmation de retournement

//--- Parametres ATR / SL / TP
input int    InpAtrPeriod      = 14;
input double InpSlAtrMult      = 1.5;
input double InpTpAtrMult      = 3.0;

//--- Filtre de tendance optionnel (desactive par defaut, non valide comme utile en backtest)
input bool   InpUseTrendFilter = false;
input int    InpEmaFast        = 50;
input int    InpEmaSlow        = 200;

//--- Fenetre horaire optionnelle (desactivee par defaut = trade toute la journee, heure serveur/GMT selon le broker)
input bool   InpUseSession     = false;
input int    InpSessionStartH  = 7;
input int    InpSessionEndH    = 21;

//--- Exclusion optionnelle de l'heure d'ouverture de journee (artefact de gap identifie en backtest)
input bool   InpExcludeHour0   = true;
input int    InpExcludedHour   = 0;

input double InpLots           = 0.10;
input ulong  InpMagic          = 20260926;

//--- Handles indicateurs
int rsiHandle;
int atrHandle;
int emaFastHandle;
int emaSlowHandle;

double rsiBuf[];
double atrBuf[];
double emaFastBuf[];
double emaSlowBuf[];

datetime lastBarTime = 0;

//--- Etat d'attente de confirmation (equivalent des variables Python watch_short / watch_long)
bool    watchShort        = false;
double  watchShortLow     = 0.0;
datetime watchShortFormedTime = 0;
int     watchShortFormedBar   = -1;

bool    watchLong         = false;
double  watchLongHigh     = 0.0;
datetime watchLongFormedTime  = 0;
int     watchLongFormedBar    = -1;

//+------------------------------------------------------------------+
int OnInit()
  {
   rsiHandle = iRSI(_Symbol, PERIOD_M1, InpRsiPeriod, PRICE_CLOSE);
   atrHandle = iATR(_Symbol, PERIOD_M1, InpAtrPeriod);
   emaFastHandle = iMA(_Symbol, PERIOD_M1, InpEmaFast, 0, MODE_EMA, PRICE_CLOSE);
   emaSlowHandle = iMA(_Symbol, PERIOD_M1, InpEmaSlow, 0, MODE_EMA, PRICE_CLOSE);

   if(rsiHandle == INVALID_HANDLE || atrHandle == INVALID_HANDLE ||
      emaFastHandle == INVALID_HANDLE || emaSlowHandle == INVALID_HANDLE)
     {
      Print("Erreur creation des handles indicateurs");
      return(INIT_FAILED);
     }

   ArraySetAsSeries(rsiBuf, true);
   ArraySetAsSeries(atrBuf, true);
   ArraySetAsSeries(emaFastBuf, true);
   ArraySetAsSeries(emaSlowBuf, true);

   trade.SetExpertMagicNumber(InpMagic);
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   IndicatorRelease(rsiHandle);
   IndicatorRelease(atrHandle);
   IndicatorRelease(emaFastHandle);
   IndicatorRelease(emaSlowHandle);
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
      ok = trade.Buy(InpLots, _Symbol, price, sl, tp, "RSI_Reversal_Confirm");
   else
      ok = trade.Sell(InpLots, _Symbol, price, sl, tp, "RSI_Reversal_Confirm");

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
   return (h >= InpSessionStartH || h < InpSessionEndH); // fenetre a cheval sur minuit
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
      return; // on ne traite qu'une fois par nouvelle bougie M1 fermee
   lastBarTime = curBarTime;

   // besoin d'au moins 4 bougies fermees + historique indicateurs
   if(Bars(_Symbol, PERIOD_M1) < InpEmaSlow + 5)
      return;

   if(CopyBuffer(rsiHandle, 0, 0, 5, rsiBuf) < 5) return;
   if(CopyBuffer(atrHandle, 0, 0, 5, atrBuf) < 5) return;
   if(InpUseTrendFilter)
     {
      if(CopyBuffer(emaFastHandle, 0, 0, 2, emaFastBuf) < 2) return;
      if(CopyBuffer(emaSlowHandle, 0, 0, 2, emaSlowBuf) < 2) return;
     }

   double high1 = iHigh(_Symbol, PERIOD_M1, 1); // derniere bougie fermee
   double high2 = iHigh(_Symbol, PERIOD_M1, 2);
   double high3 = iHigh(_Symbol, PERIOD_M1, 3);
   double low1  = iLow(_Symbol, PERIOD_M1, 1);
   double low2  = iLow(_Symbol, PERIOD_M1, 2);
   double low3  = iLow(_Symbol, PERIOD_M1, 3);
   double close1 = iClose(_Symbol, PERIOD_M1, 1);
   datetime time1 = iTime(_Symbol, PERIOD_M1, 1);
   datetime time2 = iTime(_Symbol, PERIOD_M1, 2);

   double rsiShift1 = rsiBuf[1]; // RSI de la bougie fermee la plus recente
   double rsiShift2 = rsiBuf[2]; // RSI de la bougie candidate au pic (j)
   double atrVal    = atrBuf[1];

   if(atrVal <= 0)
      return;

   bool trendUp   = true;
   bool trendDown = true;
   if(InpUseTrendFilter)
     {
      trendUp   = (emaFastBuf[1] > emaSlowBuf[1]);
      trendDown = (emaFastBuf[1] < emaSlowBuf[1]);
     }

   bool positionOpenedThisTick = false;

   //--- 1) Detection d'un nouveau pic de surachat (bougie j = shift 2, confirmee par shift 1)
   //    equivalent Python: rsi[j] > rsi_high and h[j] > h[j-1] and h[j] > h[i]
   if(!watchShort && rsiShift2 > InpRsiHigh && high2 > high3 && high2 > high1)
     {
      watchShort = true;
      watchShortLow = low2;
      watchShortFormedTime = time1; // "i" au moment ou le pic est confirme
     }

   if(!watchLong && rsiShift2 < InpRsiLow && low2 < low3 && low2 < low1)
     {
      watchLong = true;
      watchLongHigh = high2;
      watchLongFormedTime = time1;
     }

   //--- 2) Suivi de l'attente de confirmation SHORT
   if(watchShort)
     {
      // nombre de bougies fermees depuis l'armement (>=0 des la bougie d'armement elle-meme)
      int barsSince = (int)((time1 - watchShortFormedTime) / PeriodSeconds(PERIOD_M1));

      if(rsiShift1 < InpRsiCancelHigh || barsSince > InpMaxWaitBars)
        {
         watchShort = false;
        }
      else if(close1 < watchShortLow)
        {
         bool sessionOk = InTradingWindow(time1);
         bool hourOk    = !IsExcludedHour(time1);
         bool trendOk   = (!InpUseTrendFilter) || trendDown;
         if(sessionOk && hourOk && trendOk)
            OpenPosition(ORDER_TYPE_SELL, atrVal, positionOpenedThisTick);
         watchShort = false;
        }
     }

   //--- 3) Suivi de l'attente de confirmation LONG
   if(watchLong)
     {
      int barsSince = (int)((time1 - watchLongFormedTime) / PeriodSeconds(PERIOD_M1));

      if(rsiShift1 > InpRsiCancelLow || barsSince > InpMaxWaitBars)
        {
         watchLong = false;
        }
      else if(close1 > watchLongHigh)
        {
         bool sessionOk = InTradingWindow(time1);
         bool hourOk    = !IsExcludedHour(time1);
         bool trendOk   = (!InpUseTrendFilter) || trendUp;
         if(sessionOk && hourOk && trendOk)
            OpenPosition(ORDER_TYPE_BUY, atrVal, positionOpenedThisTick);
         watchLong = false;
        }
     }
  }
//+------------------------------------------------------------------+
