//+------------------------------------------------------------------+
//| FVG_Fill_EA_US30.mq5                                             |
//| Strategie Fair Value Gap Fill - version US30 uniquement          |
//| Validee par backtest 11 ans (2016-2026), M1, fenetre 14h-21h GMT |
//|                                                                    |
//| Regles :                                                          |
//| 1. Detection FVG (3 bougies consecutives)                         |
//| 2. Attente du remplissage COMPLET (max InpMaxWaitFill bougies)    |
//| 3. Confirmation de sortie: cloture au-dela du bord + marge ATR    |
//|    (max InpMaxWaitExit bougies apres remplissage)                 |
//| 4. Filtre de vitesse: remplissage <= InpMaxFillBars,               |
//|    confirmation <= InpMaxConfirmBars (sinon signal ignore)         |
//| 5. Une seule position a la fois (jamais de positions paralleles - |
//|    teste et confirme comme essentiel a l'edge)                    |
//| 6. SL = InpSLAtr x ATR, TP = InpTPAtr x ATR                       |
//| 7. Taille de position = InpRiskPercent% du capital                |
//+------------------------------------------------------------------+
#property copyright "Strategie validee par backtest"
#property version   "1.00"
#property strict

#include <Trade\Trade.mqh>
CTrade trade;

//--- Parametres d'entree
input group "=== Indicateurs ==="
input int    InpAtrPeriod        = 14;      // Periode ATR

input group "=== Fair Value Gap ==="
input double InpExitMarginAtr    = 0.5;     // Marge de confirmation de sortie (x ATR)
input int    InpMaxWaitFill      = 300;     // Delai max pour le remplissage (bougies)
input int    InpMaxWaitExit      = 50;      // Delai max pour la confirmation (bougies)
input int    InpMaxFillBars      = 5;       // Filtre vitesse: bougies max jusqu'au remplissage
input int    InpMaxConfirmBars   = 3;       // Filtre vitesse: bougies max jusqu'a la confirmation

input group "=== Fenetre horaire US30 (heure serveur - A AJUSTER selon decalage GMT) ==="
input int    InpSession1StartH   = 14;      // Fenetre - heure debut (14h GMT)
input int    InpSession1EndH     = 21;      // Fenetre - heure fin (21h GMT)
input bool   InpUseSession2      = false;   // US30 n utilise qu UNE seule fenetre
input int    InpSession2StartH   = 0;       // (non utilise pour US30)
input int    InpSession2EndH     = 0;       // (non utilise pour US30)

input group "=== Gestion du risque ==="
input double InpSLAtr            = 1.5;     // Stop Loss (x ATR)
input double InpTPAtr            = 8.0;     // Take Profit (x ATR)
input double InpRiskPercent      = 0.5;     // Risque par trade (% du capital)
input ulong  InpMagicNumber      = 20260930; // Magic number (different de la version DAX)

//--- Handles et variables globales
int atrHandle;
datetime lastBarTime = 0;

// Etat du FVG haussier en attente
bool   bullActive = false;
double bullTop = 0, bullBot = 0;
int    bullFormedBar = -1;
bool   bullFilled = false;
int    bullFilledBar = -1;
double bullAtrRef = 0;

// Etat du FVG baissier en attente
bool   bearActive = false;
double bearTop = 0, bearBot = 0;
int    bearFormedBar = -1;
bool   bearFilled = false;
int    bearFilledBar = -1;
double bearAtrRef = 0;

int barCounter = 0; // compteur de bougies depuis le demarrage (substitut a bar_index)

//+------------------------------------------------------------------+
int OnInit()
  {
   atrHandle = iATR(_Symbol, PERIOD_M1, InpAtrPeriod);
   if(atrHandle == INVALID_HANDLE)
     {
      Print("Erreur creation handle ATR");
      return INIT_FAILED;
     }
   trade.SetExpertMagicNumber(InpMagicNumber);
   return INIT_SUCCEEDED;
  }

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   IndicatorRelease(atrHandle);
  }

//+------------------------------------------------------------------+
// Verifie si l'heure (serveur) tombe dans une des fenetres configurees
bool InWindow(int hour)
  {
   bool inS1 = (hour >= InpSession1StartH) && (hour < InpSession1EndH);
   bool inS2 = false;
   if(InpUseSession2)
      inS2 = (hour >= InpSession2StartH) && (hour < InpSession2EndH);
   return inS1 || inS2;
  }

//+------------------------------------------------------------------+
// Calcule la taille de position pour un risque donne (en % du capital) et une distance de SL (en prix)
double CalcLotSize(double slDistance)
  {
   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double riskAmount = balance * (InpRiskPercent/100.0);

   double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(tickSize <= 0) tickSize = _Point;

   double valuePerUnit = (tickValue/tickSize) * slDistance; // perte si le SL est touche, pour 1.0 lot
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

//+------------------------------------------------------------------+
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

//+------------------------------------------------------------------+
// Reinitialise l'etat FVG au demarrage d'un nouveau jour (evite les faux positifs entre sessions)
void CheckNewDayReset()
  {
   MqlDateTime dtCur, dtLast;
   TimeToStruct(TimeCurrent(), dtCur);
   TimeToStruct(lastBarTime, dtLast);
   if(dtCur.day != dtLast.day)
     {
      bullActive = false; bearActive = false;
     }
  }

//+------------------------------------------------------------------+
void OnTick()
  {
   // Ne traiter qu'une fois par nouvelle bougie M1 (pas a chaque tick)
   datetime currentBarTime = iTime(_Symbol, PERIOD_M1, 0);
   if(currentBarTime == lastBarTime)
      return;

   bool firstRun = (lastBarTime == 0);
   lastBarTime = currentBarTime;
   barCounter++;

   if(firstRun)
      return; // pas assez d'historique pour comparer au demarrage

   // Index des bougies: 0 = bougie qui vient de se cloturer (la precedente, complete)
   //                     shift 1 = bougie i-1, shift 2 = bougie i-2, etc.
   // On travaille sur la bougie qui VIENT de se terminer -> shift = 1
   int i = 1;

   double atrBuf[];
   ArraySetAsSeries(atrBuf, true);
   if(CopyBuffer(atrHandle, 0, i, 1, atrBuf) <= 0) return;
   double atrVal = atrBuf[0];
   if(atrVal <= 0) return;

   double hi0 = iHigh(_Symbol, PERIOD_M1, i);
   double lo0 = iLow(_Symbol, PERIOD_M1, i);
   double cl0 = iClose(_Symbol, PERIOD_M1, i);
   double hi2 = iHigh(_Symbol, PERIOD_M1, i+2);
   double lo2 = iLow(_Symbol, PERIOD_M1, i+2);

   MqlDateTime dt;
   TimeToStruct(iTime(_Symbol, PERIOD_M1, i), dt);
   int hour = dt.hour;
   bool windowOk = InWindow(hour);

   // ===== 1. DETECTION D'UN NOUVEAU FVG (si aucune position ouverte et aucun FVG deja en attente) =====
   bool noOpenPosition = !HasOpenPosition();

   if(windowOk && noOpenPosition && !bullActive)
     {
      if(lo0 > hi2) // FVG haussier
        {
         bullActive = true;
         bullBot = hi2;
         bullTop = lo0;
         bullFormedBar = barCounter;
         bullFilled = false;
         bullAtrRef = atrVal;
        }
     }
   if(windowOk && noOpenPosition && !bearActive)
     {
      if(hi0 < lo2) // FVG baissier
        {
         bearActive = true;
         bearTop = lo2;
         bearBot = hi0;
         bearFormedBar = barCounter;
         bearFilled = false;
         bearAtrRef = atrVal;
        }
     }

   // ===== 2. GESTION DU FVG HAUSSIER EN ATTENTE =====
   if(bullActive && noOpenPosition)
     {
      int barsSinceFormed = barCounter - bullFormedBar;
      // IMPORTANT: ne jamais verifier le remplissage sur la bougie de formation elle-meme
      // (barsSinceFormed==0) - il faut au moins 1 bougie d ecart, comme en Python.
      if(!bullFilled && barsSinceFormed >= 1)
        {
         if(barsSinceFormed > InpMaxWaitFill)
            bullActive = false;
         else if(lo0 <= bullBot)
           {
            bullFilled = true;
            bullFilledBar = barCounter;
           }
        }
      else if(barCounter - bullFilledBar >= 1)
        {
         int barsSinceFilled = barCounter - bullFilledBar;
         double trigger = bullTop + InpExitMarginAtr*bullAtrRef;
         if(barsSinceFilled > InpMaxWaitExit)
            bullActive = false;
         else if(cl0 > trigger)
           {
            // filtre de vitesse
            int fillBars = bullFilledBar - bullFormedBar;
            int confirmBars = barCounter - bullFilledBar;
            bullActive = false;
            if(fillBars <= InpMaxFillBars && confirmBars <= InpMaxConfirmBars)
               OpenPosition(ORDER_TYPE_BUY, bullAtrRef);
           }
        }
     }

   // ===== 3. GESTION DU FVG BAISSIER EN ATTENTE =====
   if(bearActive && noOpenPosition)
     {
      int barsSinceFormedB = barCounter - bearFormedBar;
      // Meme correctif que pour le haussier: jamais sur la bougie de formation elle-meme.
      if(!bearFilled && barsSinceFormedB >= 1)
        {
         if(barsSinceFormedB > InpMaxWaitFill)
            bearActive = false;
         else if(hi0 >= bearTop)
           {
            bearFilled = true;
            bearFilledBar = barCounter;
           }
        }
      else if(barCounter - bearFilledBar >= 1)
        {
         int barsSinceFilledB = barCounter - bearFilledBar;
         double triggerB = bearBot - InpExitMarginAtr*bearAtrRef;
         if(barsSinceFilledB > InpMaxWaitExit)
            bearActive = false;
         else if(cl0 < triggerB)
           {
            int fillBarsB = bearFilledBar - bearFormedBar;
            int confirmBarsB = barCounter - bearFilledBar;
            bearActive = false;
            if(fillBarsB <= InpMaxFillBars && confirmBarsB <= InpMaxConfirmBars)
               OpenPosition(ORDER_TYPE_SELL, bearAtrRef);
           }
        }
     }

   CheckNewDayReset();
  }

//+------------------------------------------------------------------+
void OpenPosition(ENUM_ORDER_TYPE orderType, double atrRef)
  {
   if(HasOpenPosition()) return; // securite anti-doublon

   double slDist = InpSLAtr * atrRef;
   double tpDist = InpTPAtr * atrRef;

   double price, sl, tp;
   if(orderType == ORDER_TYPE_BUY)
     {
      price = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      sl = price - slDist;
      tp = price + tpDist;
     }
   else
     {
      price = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      sl = price + slDist;
      tp = price - tpDist;
     }

   double lots = CalcLotSize(slDist);
   if(lots <= 0)
     {
      Print("Taille de position calculee invalide, trade annule");
      return;
     }

   if(orderType == ORDER_TYPE_BUY)
      trade.Buy(lots, _Symbol, price, sl, tp, "FVG Fill LONG");
   else
      trade.Sell(lots, _Symbol, price, sl, tp, "FVG Fill SHORT");
  }
//+------------------------------------------------------------------+
