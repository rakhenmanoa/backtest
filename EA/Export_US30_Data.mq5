//+------------------------------------------------------------------+
//| Export_US30_Data.mq5                                             |
//| Script simple: exporte les bougies M1 d'une periode donnee vers  |
//| un fichier CSV, pour comparaison avec des donnees externes.      |
//| Utilisation: le glisser sur un graphique US30 (n'importe quelle  |
//| periode), il s'execute une fois et cree le fichier, puis s'arrete.|
//+------------------------------------------------------------------+
#property copyright "Export de donnees pour comparaison"
#property script_show_inputs

input string InpSymbol    = "US30m";           // Symbole a exporter
input datetime InpFrom    = D'2023.03.01 13:50'; // Date/heure de debut
input datetime InpTo      = D'2023.03.01 14:40'; // Date/heure de fin
input string InpFileName  = "export_us30.csv";  // Nom du fichier de sortie

void OnStart()
  {
   MqlRates rates[];
   int copied = CopyRates(InpSymbol, PERIOD_M1, InpFrom, InpTo, rates);

   if(copied <= 0)
     {
      Print("Erreur: aucune donnee recuperee. Code erreur: ", GetLastError());
      Print("Verifie que le symbole '", InpSymbol, "' est correct et que l'historique est disponible.");
      return;
     }

   int handle = FileOpen(InpFileName, FILE_WRITE|FILE_CSV|FILE_ANSI, ';');
   if(handle == INVALID_HANDLE)
     {
      Print("Erreur ouverture fichier: ", GetLastError());
      return;
     }

   FileWrite(handle, "DateTime", "Open", "High", "Low", "Close", "Volume");
   for(int i = 0; i < copied; i++)
     {
      FileWrite(handle, TimeToString(rates[i].time, TIME_DATE|TIME_MINUTES),
                DoubleToString(rates[i].open, _Digits),
                DoubleToString(rates[i].high, _Digits),
                DoubleToString(rates[i].low, _Digits),
                DoubleToString(rates[i].close, _Digits),
                (long)rates[i].tick_volume);
     }
   FileClose(handle);

   Print("Export termine: ", copied, " bougies ecrites dans ", InpFileName);
   Print("Le fichier se trouve dans le dossier MQL5/Files de ton terminal");
   Print("(Fichier -> Ouvrir le dossier de donnees -> MQL5 -> Files)");

   Alert("Export termine ! ", copied, " bougies dans ", InpFileName);
  }
//+------------------------------------------------------------------+
