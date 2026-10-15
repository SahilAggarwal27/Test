#!/usr/bin/env python3
# Cross Expiry engine v2 — rules exactly as traded live (Sahil, Oct 2026):
#  Daily (index with the nearest expiry): strikes fixed at 10:05 (CE = strike above spot, PE = strike below);
#   each side INDEPENDENTLY: sell when premium breaks the 09:20-10:05 LOW, SL = 09:20-10:05 HIGH, re-enter on a
#   fresh break after SL. A side that is already held (e.g. a carried / rolled position) is not doubled.
#  Carried positions, next morning at 10:05: profit >= 80% of the sell price -> close; in loss -> SL moves to that
#   day's 09:20-10:05 high of the same contract; otherwise keep the existing SL. Before 10:05 the old SL stands
#   (an opening gap fills at market).
#  Expiry day (Tue/Thu): everything on the expiring contract is squared at 14:00. The side(s) still open at 14:00
#   (CE, PE or both) are rolled into the OTHER index's next expiry: strike fixed at 10:05, sold at the 14:00
#   market price, SL = that contract's 09:20-10:05 high. SL frozen after 15:15 on expiry days.
#  Scenarios (params.ceMode): live = roll held (carry rules above) | sq14 = no roll | roll1525 = roll squared at
#   the exit time (15:25) | roll1003 = roll squared next trading day at 10:05.
import io, os, sys, shutil
P = os.environ.get("BT_HTML", "backtester.html")
s = io.open(P, encoding="utf-8").read()
if "/*CEV2*/" in s:
    print("Already fixed."); sys.exit(0)
A = "function runBacktestCrossExpiry(params){"
if s.count(A) != 1 or "function ceStrike(" not in s:
    print("ABORT: anchor not found."); sys.exit(1)
JS = r"""/*CEV2*/
function ceV2(params){
  const MORN='10:05', mornM=parseTime(MORN), W0=parseTime('09:20'), ROLL=parseTime(params.rollTime||'14:00');
  const CLOSE=parseTime('15:30'), FREEZE=parseTime('15:15'), EXITM=parseTime(params.exitTime||'15:25');
  const mode=params.ceMode||'live', pair=['NIFTY','SENSEX'];
  const dowArr=['Mon','Tue','Wed','Thu','Fri','Sat','Sun'];
  const fromD=(params.dateFrom||'').trim(), toD=(params.dateTo||'').trim();
  const dates=Object.keys(GROUPED).sort().filter(d=>(!fromD||d>=fromD)&&(!toD||d<=toD));
  const trades=[], dailyPnl=[]; let carrySkips=0; let open=[];
  const lvl=(date,inst,k,exp,side)=>{ let lo=null,hi=null; for(const r of ceLeg(date,inst,k,exp,side)){ const m=parseTime(r.time);
      if(m>=W0&&m<=mornM){ if(lo===null||r.l<lo) lo=r.l; if(hi===null||r.h>hi) hi=r.h; } } return (lo!==null&&hi!==null&&hi>lo)?{lo,hi}:null; };
  const book=(p,date,t,px,why)=>{ const lot=lotFor(p.inst,date)*params.lots, pnl=(p.ep-px)*lot;
    trades.push({date:p.entryDate, exitDate:date, instrument:p.inst, leg:p.side, strike:p.strike, et:p.et, ep:p.ep, xt:t, xp:px, reason:(p.kind==='D'?'':'R-')+why, pnl});
    dailyPnl.push({date, dow:dowArr[(new Date(date).getDay()+6)%7], instrument:p.inst, atm:p.strike, pnl, nTrades:1, slHits:(why==='SL'?1:0)}); };
  for(const date of dates){
    const exp={}; for(const ix of pair) exp[ix]=ceNearestExp(date,ix);
    const expDay=pair.some(ix=>exp[ix]===date), slCut=expDay?FREEZE:Infinity;
    let act=null; for(const ix of pair){ if(exp[ix] && exp[ix]>=date && (act===null||exp[ix]<exp[act])) act=ix; }
    const actExpiring = act && exp[act]===date;
    const freeAt={};            // side -> minute from which a new daily entry on `act` is allowed
    const openAt14=new Set();   // sides on the expiring contract still open at 14:00
    // 1) carried positions
    const keep=[];
    for(const p of open){
      const ser=ceLeg(date,p.inst,p.strike,p.exp,p.side);
      if(!ser.length){ keep.push(p); continue; }
      const sqDay=(p.exp<=date), endM=sqDay?ROLL:CLOSE;
      let done=false, first=true, lastBar=null;
      for(const r of ser){ const m=parseTime(r.time); if(m>endM) break; lastBar=r;
        if(p._chk!==date && m>=mornM){
          p._chk=date;
          if(p.kind==='R' && mode==='roll1003'){ book(p,date,r.time,r.p,'SQ1005'); done=true; break; }
          if(r.p<=0.2*p.ep){ book(p,date,r.time,r.p,'TP80'); done=true; break; }
          if(r.p>p.ep){ const lv=lvl(date,p.inst,p.strike,p.exp,p.side); if(lv) p.sl=lv.hi; }
        }
        if(m<=slCut && r.h>=p.sl){ book(p,date,r.time, first?Math.max(p.sl,r.p):p.sl, 'SL'); done=true; break; }
        first=false; }
      if(!done && sqDay){ if(lastBar){ book(p,date,lastBar.time,lastBar.p,'SQ14'); if(p.inst===act) openAt14.add(p.side); done=true; } }
      if(p.inst===act && !(p.exp<date)){ freeAt[p.side]=done ? Math.max(freeAt[p.side]||0, parseTime((trades[trades.length-1]||{}).xt||'00:00')) : Infinity; }
      if(!done) keep.push(p);
    }
    open=keep;
    // 2) fresh daily entries on the active index, each side independent, with re-entry
    if(act && exp[act]){
      const ex=exp[act], endM=actExpiring?ROLL:CLOSE;
      for(const side of ['CE','PE']){
        if(freeAt[side]===Infinity) continue;
        const k=ceStrike(date,act,MORN,side); if(k===null) continue;
        const lv=lvl(date,act,k,ex,side); if(!lv) continue;
        const start=Math.max(mornM, freeAt[side]||0);
        let pos=null, lastBar=null;
        for(const r of ceLeg(date,act,k,ex,side)){ const m=parseTime(r.time); if(m<=start) continue; if(m>endM) break; lastBar=r;
          if(pos){ if(m<=slCut && r.h>=pos.sl){ book(pos,date,r.time,pos.sl,'SL'); pos=null; } }
          else if(r.l<=lv.lo){ pos={kind:'D', inst:act, exp:ex, side, strike:k, et:r.time, ep:lv.lo, sl:lv.hi, entryDate:date, _chk:date}; } }
        if(pos){ if(actExpiring){ if(lastBar){ book(pos,date,lastBar.time,lastBar.p,'SQ14'); openAt14.add(side); } } else open.push(pos); }
      }
    }
    // 3) 14:00 roll of the side(s) open at 14:00 into the other index's next expiry
    if(actExpiring && mode!=='sq14' && openAt14.size){
      const nxt=pair.find(ix=>ix!==act), nexp=ceNearestExp(date,nxt);
      if(nexp && nexp>date){
        for(const side of ['CE','PE']){ if(!openAt14.has(side)) continue;
          const k=ceStrike(date,nxt,MORN,side); if(k===null){ carrySkips++; continue; }
          const ser=ceLeg(date,nxt,k,nexp,side), eb=ser.find(r=>parseTime(r.time)>=ROLL); const lv=lvl(date,nxt,k,nexp,side);
          if(!eb){ carrySkips++; continue; }
          const pos={kind:'R', inst:nxt, exp:nexp, side, strike:k, et:eb.time, ep:eb.p, sl:(lv?lv.hi:eb.h), entryDate:date, _chk:date};
          const endR=(mode==='roll1525')?EXITM:CLOSE; let done=false, lastBar=null;
          for(const r of ser){ const m=parseTime(r.time); if(m<ROLL) continue; if(m>endR) break; lastBar=r;
            if(m<=slCut && r.h>=pos.sl){ book(pos,date,r.time,pos.sl,'SL'); done=true; break; } }
          if(!done){ if(mode==='roll1525'){ if(lastBar) book(pos,date,lastBar.time,lastBar.p,'SQ1525'); } else open.push(pos); }
        }
      } else carrySkips++;
    }
  }
  const tByInst={}; trades.forEach(t=>tByInst[t.instrument]=(tByInst[t.instrument]||0)+1);
  let costs=0; for(const inst in tByInst){ const n=tByInst[inst], lq=SPECS[inst]?SPECS[inst].lot:0; costs+=n*params.brokerage*params.lots+n*params.slippage*lq*params.lots; }
  return {trades, dailyPnl, costs, carrySkips};
}
function runBacktestCrossExpiry(params){ return ceV2(params); }
function runBacktestCrossExpiryOld(params){"""
s = s.replace(A, JS)
shutil.copyfile(P, P + ".bak25")
io.open(P, "w", encoding="utf-8").write(s)
print("Cross Expiry engine v2 (live rules) installed.")
