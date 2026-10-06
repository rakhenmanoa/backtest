//+------------------------------------------------------------------+
//| Trend_MA_Cross_EA.mq5                                            |
//| Strategie simple de suivi de tendance: croisement de deux        |
//| moyennes mobiles exponentielles (EMA rapide / EMA lente).        |
//| Sert de test de reference pour comparer le win rate obtenu sur   |
//| les donnees Exness a celui obtenu sur Python/Dukascopy, afin de  |
//| verifier si l'ecart observe avec la strategie FVG est general    |
//| (probleme de flux de donnees) ou specifique a cette logique.     |
//+------------------------------------------------------------------+
#property copyright "Test de reference - suivi de tendance"
#property version   "1.00"

#include <Trade\Trade.mqh>
CTrade trade;

input group "=== Moyennes mobiles ==="
input int    InpFastPeriod  = 20;      // Periode EMA rapide
input int    InpSlowPeriod  = 50;      // Periode EMA lente
input ENUM_TIMEFRAMES InpTimeframe = PERIOD_M15; // Unite de temps

input group "=== Gestion du risque ==="
input int    InpAtrPeriod   = 14;      // Periode ATR (pour SL/TP)
input double InpSLAtr       = 2.0;     // Stop Loss (x ATR)
input double InpTPAtr       = 4.0;     // Take Profit (x ATR) - ratio 1:2, win rate ~33% attendu
input double InpRiskPercent = 0.5;     // Risque par trade (% du capital)
input ulong  InpMagicNumber = 20261001; // Magic number

int fastHandle, slowHandle, atrHandle;
datetime lastBarTime = 0;

int OnInit()
  {
   fastHandle = iMA(_Symbol, InpTimeframe, InpFastPeriod, 0, MODE_EMA, PRICE_CLOSE);
   slowHandle = iMA(_Symbol, InpTimeframe, InpSlowPeriod, 0, MODE_EMA, PRICE_CLOSE);
   atrHandle  = iATR(_Symbol, InpTimeframe, InpAtrPeriod);
   if(fastHandle==INVALID_HANDLE || slowHandle==INVALID_HANDLE || atrHandle==INVALID_HANDLE)
     {
      Print("Erreur creation des indicateurs");
      return INIT_FAILED;
     }
   trade.SetExpertMagicNumber(InpMagicNumber);
   return INIT_SUCCEEDED;
  }

void OnDeinit(const int reason)
  {
   IndicatorRelease(fastHandle);
   IndicatorRelease(slowHandle);
   IndicatorRelease(atrHandle);
  }

bool HasOpenPosition()
  {
   for(int i = PositionsTotal()-1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(PositionSelectByTicket(ticket))
        {
         if(PositionGetString(POSITION_SYMBOL) == _Symbol &&
            PositionGetInteger(POSITION_MAGIC) == (long)InpMagicNumber)
            return true;
        }
     }
   return false;
  }

double CalcLotSize(double slDistance)
  {
   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double riskAmount = balance * (InpRiskPercent/100.0);
   double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(tickSize <= 0) tickSize = _Point;
   double valuePerUnit = (tickValue/tickSize) * slDistance;
   if(valuePerUnit <= 0) return 0;
   double lots = riskAmount / valuePerUnit;
   double minLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double lotStep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   lots = MathFloor(lots/lotStep) * lotStep;
   if(lots < minLot) lots = minLot;
   if(lots > maxLot) lots = maxLot;
   return lots;
  }

void OnTick()
  {
   datetime currentBarTime = iTime(_Symbol, InpTimeframe, 0);
   if(currentBarTime == lastBarTime) return;
   bool firstRun = (lastBarTime == 0);
   lastBarTime = currentBarTime;
   if(firstRun) return;

   // bougie qui vient de se cloturer = shift 1
   double fastBuf[], slowBuf[], atrBuf[];
   if(CopyBuffer(fastHandle, 0, 1, 3, fastBuf) <= 0) return;
   if(CopyBuffer(slowHandle, 0, 1, 3, slowBuf) <= 0) return;
   if(CopyBuffer(atrHandle, 0, 1, 1, atrBuf) <= 0) return;

   // fastBuf[0]=shift1(plus recent), fastBuf[1]=shift2 -> on regarde le croisement
   // entre la bougie shift2 et shift1
   ArraySetAsSeries(fastBuf, false); ArraySetAsSeries(slowBuf, false);
   // CopyBuffer avec start=1,count=3 retourne [shift3, shift2, shift1] par defaut (ordre chronologique)
   double fastPrev = fastBuf[1]; // shift2
   double fastCurr = fastBuf[2]; // shift1 (bougie cloturee)
   double slowPrev = slowBuf[1];
   double slowCurr = slowBuf[2];
   double atrVal = atrBuf[0];

   if(atrVal <= 0) return;

   bool crossUp   = (fastPrev <= slowPrev) && (fastCurr > slowCurr);
   bool crossDown = (fastPrev >= slowPrev) && (fastCurr < slowCurr);

   if(!HasOpenPosition())
     {
      double slDist = InpSLAtr * atrVal;
      double tpDist = InpTPAtr * atrVal;
      double lots = CalcLotSize(slDist);
      if(lots <= 0) return;

      if(crossUp)
        {
         double price = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
         double sl = price - slDist;
         double tp = price + tpDist;
         trade.Buy(lots, _Symbol, price, sl, tp, "Trend MA Cross LONG");
        }
      else if(crossDown)
        {
         double price = SymbolInfoDouble(_Symbol, SYMBOL_BID);
         double sl = price + slDist;
         double tp = price - tpDist;
         trade.Sell(lots, _Symbol, price, sl, tp, "Trend MA Cross SHORT");
        }
     }
  }
//+------------------------------------------------------------------+
