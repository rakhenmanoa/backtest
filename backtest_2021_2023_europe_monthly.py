import pandas as pd, numpy as np
YEARS=[2021,2022,2023]

def calc(year):
 f=f"DAT_ASCII_JPXJPY_M1_{year}.csv"; raw=pd.read_csv(f,header=None,sep=r"[,;\s]+",engine="python").iloc[:,:7]; raw.columns=["date","time","open","high","low","close","volume"]
 raw["dt"]=pd.to_datetime(raw.date.astype(str)+raw.time.astype(str).str.zfill(6),format="%Y%m%d%H%M%S",errors="coerce")
 for c in ["open","high","low","close"]: raw[c]=pd.to_numeric(raw[c],errors="coerce")
 raw=raw.dropna(subset=["dt","open","high","low","close"]).set_index("dt").sort_index()
 b=raw.resample("5min",label="right",closed="right").agg(open=("open","first"),high=("high","max"),low=("low","min"),close=("close","last")).dropna(); tp=(b.high+b.low+b.close)/3; b["vwap"]=tp.groupby(b.index.date).transform(lambda x:x.cumsum()/np.arange(1,len(x)+1))
 pc=b.close.shift(); tr=pd.concat([b.high-b.low,(b.high-pc).abs(),(b.low-pc).abs()],axis=1).max(axis=1); b["atr"]=tr.ewm(alpha=1/14,adjust=False,min_periods=14).mean()
 d=b.close.diff(); g=d.clip(lower=0); l=-d.clip(upper=0); ag=g.ewm(alpha=.5,adjust=False,min_periods=2).mean(); al=l.ewm(alpha=.5,adjust=False,min_periods=2).mean(); rs=ag/al.replace(0,np.nan); b["rsi2"]=100-100/(1+rs); b.loc[al.eq(0)&ag.gt(0),"rsi2"]=100; b.loc[ag.eq(0)&al.gt(0),"rsi2"]=0
 q=b.resample("15min",label="right",closed="right").agg(open=("open","first"),high=("high","max"),low=("low","min"),close=("close","last")).dropna(); pc=q.close.shift(); tr=pd.concat([q.high-q.low,(q.high-pc).abs(),(q.low-pc).abs()],axis=1).max(axis=1); up=q.high.diff(); dn=-q.low.diff(); pdm=up.where((up>dn)&(up>0),0.); mdm=dn.where((dn>up)&(dn>0),0.); a=tr.ewm(alpha=1/14,adjust=False,min_periods=14).mean(); pdi=100*pdm.ewm(alpha=1/14,adjust=False,min_periods=14).mean()/a; mdi=100*mdm.ewm(alpha=1/14,adjust=False,min_periods=14).mean()/a; dx=100*(pdi-mdi).abs()/(pdi+mdi).replace(0,np.nan); b["adx15"]=dx.ewm(alpha=1/14,adjust=False,min_periods=14).mean().reindex(b.index,method="ffill")
 out=[]; pos=None
 for i,r in enumerate(b.itertuples()):
  ts=b.index[i]; eu=420<=ts.hour*60+ts.minute<960
  if pos:
   ex=why=None
   if pos["side"]=="L":
    if r.low<=pos["sl"]: ex,why=pos["sl"],"SL"
    elif r.high>=pos["tp"]: ex,why=pos["tp"],"VWAP"
   else:
    if r.high>=pos["sl"]: ex,why=pos["sl"],"SL"
    elif r.low<=pos["tp"]: ex,why=pos["tp"],"VWAP"
   if ex is None and i-pos["i"]>=12: ex,why=r.close,"TIMEOUT"
   if ex is not None:
    rr=(ex-pos["e"])/pos["risk"] if pos["side"]=="L" else (pos["e"]-ex)/pos["risk"]; out.append([ts,rr,why]); pos=None; continue
  if not pos and eu and all(np.isfinite(x) for x in [r.rsi2,r.atr,r.vwap,r.adx15]) and r.adx15<25:
   if r.rsi2<10 and r.close<=r.vwap-1.5*r.atr: risk=1.2*r.atr; pos={"side":"L","e":r.close,"sl":r.close-risk,"tp":r.vwap,"risk":risk,"i":i}
   elif r.rsi2>95 and r.close>=r.vwap+2*r.atr: risk=1.2*r.atr; pos={"side":"S","e":r.close,"sl":r.close+risk,"tp":r.vwap,"risk":risk,"i":i}
 t=pd.DataFrame(out,columns=["exit_time","r","reason"]); t["year"]=year; return t
all=pd.concat([calc(y) for y in YEARS],ignore_index=True); all.to_csv("trades_2021_2023_europe.csv",index=False)
for p,g in all.assign(month=all.exit_time.dt.to_period("M")).groupby("month"):
 w=(g.r>0).sum(); loss=(g.r<0).sum(); pf=g.loc[g.r>0,"r"].sum()/abs(g.loc[g.r<0,"r"].sum()) if loss else np.inf; print(f"MONTH={p} TRADES={len(g)} WINS={w} WIN_RATE={w/len(g)*100:.2f} NET_R={g.r.sum():.3f} PF={pf:.3f}")
print("TOTAL",len(all),(all.r>0).sum(),all.r.sum())
