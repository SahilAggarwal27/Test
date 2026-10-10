#!/usr/bin/env python3
# Cross Expiry: add the DAILY 10:03 leg seen in the contract notes (Mon/Wed/Fri entries).
# On days with no expiry, on the index with the nearest expiry (Fri-Tue NIFTY, Wed-Thu SENSEX):
# sell the ATM side that first breaks below its 10:03 low, SL = 09:20-10:03 window high,
# carry overnight until SL (gap -> fill at market), square at the roll time on that index's
# expiry day. After an SL, a fresh entry is allowed the next day. Trades tagged D-SL / D-SQ.
import io, os, sys, shutil
P = os.environ.get("BT_HTML", "backtester.html")
s = io.open(P, encoding="utf-8").read()
if "/*DAILY*/" in s:
    print("Already fixed."); sys.exit(0)
A1 = "  let pos=null;  // {inst, side, strike, exp, et, ep, sl, entryDate}\n"
B1 = A1 + r"""  let dpos=null;   /*DAILY*/ // daily 10:03 leg, independent of the roll
  const closeD=(exitDate,xt,xp,reason)=>{
    const lot=lotFor(dpos.inst,exitDate)*params.lots, pnl=(dpos.ep-xp)*lot;
    trades.push({date:dpos.entryDate, exitDate, instrument:dpos.inst, leg:dpos.side, strike:dpos.strike, et:dpos.et, ep:dpos.ep, xt, xp, reason:'D-'+reason, pnl});
    dailyPnl.push({date:exitDate, dow:dowArr[(new Date(exitDate).getDay()+6)%7], instrument:dpos.inst, atm:dpos.strike, pnl, nTrades:1, slHits:(reason==='SL'?1:0)});
    dpos=null;
  };
"""
A2 = "    const expiringToday=pair.filter(ix=>exp[ix]===date);\n"
B2 = A2 + r"""    // D) DAILY 10:03 leg: manage the carried one, then (no-expiry days) open a fresh one
    let dStop=null; const mornM=parseTime(MORN);
    if(dpos){
      const sq=(exp[dpos.inst]===date), endM=sq?E:CLOSE, slCut=isTueThu(date)?NOSL_AFTER:Infinity;
      const ser=ceLeg(date,dpos.inst,dpos.strike,dpos.exp,dpos.side); let first=true, done=false;
      for(const r of ser){ const m=parseTime(r.time); if(m>endM) break;
        if(m<=slCut && r.h>=dpos.sl){ dStop=m; closeD(date, r.time, first?Math.max(dpos.sl,r.p):dpos.sl, 'SL'); done=true; break; }
        first=false; }
      if(!done && sq){ const c=ser.filter(r=>parseTime(r.time)<=E); const b=c.length?c[c.length-1]:null;
        if(b) closeD(date, b.time, b.p, 'SQ'); else dpos=null; }
    }
    if(!dpos && !expiringToday.length && (dStop===null || dStop<=mornM)){
      let inst=null, best=null;
      for(const ix of pair){ if(exp[ix] && exp[ix]>date && (best===null||exp[ix]<best)){ best=exp[ix]; inst=ix; } }
      const atm=inst?ceAtm(date,inst,MORN):null;
      if(atm!==null){
        const legs={CE:ceLeg(date,inst,atm,best,'CE'), PE:ceLeg(date,inst,atm,best,'PE')}, ref={}, w0=parseTime('09:20');
        for(const sd of ['CE','PE']){ const L=legs[sd], a0=L.find(r=>r.time===MORN); let hi=null;
          for(const r of L){ const m=parseTime(r.time); if(m>=w0 && m<=mornM && (hi===null||r.h>hi)) hi=r.h; }
          ref[sd]=(a0 && hi!==null && hi>a0.l)?{lo:a0.l,hi}:null; }
        const tm={}; for(const sd of ['CE','PE']) if(ref[sd]) for(const r of legs[sd]){ if(parseTime(r.time)>mornM) (tm[r.time]=tm[r.time]||{})[sd]=r; }
        for(const t of Object.keys(tm).sort((a,b)=>parseTime(a)-parseTime(b))){ const row=tm[t];
          if(!dpos){ for(const sd of ['CE','PE']){ const rr=row[sd]; if(rr && rr.l<=ref[sd].lo){ dpos={inst, side:sd, strike:atm, exp:best, et:t, ep:ref[sd].lo, sl:ref[sd].hi, entryDate:date}; break; } } }
          else { const rr=row[dpos.side]; if(rr && rr.h>=dpos.sl){ closeD(date, t, dpos.sl, 'SL'); break; } }
        }
      }
    }
"""
for a in (A1, A2):
    if s.count(a) != 1:
        print("ABORT: anchor not found: " + a[:60]); sys.exit(1)
s = s.replace(A1, B1).replace(A2, B2)
shutil.copyfile(P, P + ".bak7")
io.open(P, "w", encoding="utf-8").write(s)
print("Daily 10:03 leg added.")
