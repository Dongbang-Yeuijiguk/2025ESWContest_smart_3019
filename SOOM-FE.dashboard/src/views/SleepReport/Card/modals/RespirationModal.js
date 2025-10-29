import React, {useMemo, useContext} from 'react';
import BaseModal from './BaseModal';
import '../../label.css';
import {SleepDataContext} from '../../../SleepReport';

/**
 * RespirationModal
 * Props:
 *  - open, onClose
 *  - data: {
 *      average_bpm: number,
 *      records: [{time: ISOString, bpm: number}],
 *      unbreath_events: [{time: ISOString}],
 *      total_count?: number,
 *      average_score?: number
 *    }
 */
export default function RespirationModal({open, onClose, data={}, title='호흡', isDark=false}){
  // Prefer explicit prop, else read from SleepDataContext (remote > data)
  const ctx = useContext(SleepDataContext);
  const breathing = (data && (data.records || data.average_bpm || data.unbreath_events)) ? data
                    : (ctx?.remote?.breathing) ? ctx.remote.breathing
                    : (ctx?.data?.breathing) ? ctx.data.breathing
                    : {};

  const records = Array.isArray(breathing.records) ? breathing.records : [];
  const events = Array.isArray(breathing.unbreath_events) ? breathing.unbreath_events : [];
  const avgBpm = Number.isFinite(breathing.average_bpm) ? breathing.average_bpm : null;

  const apneaCount = events.length;
  // 무호흡 이벤트가 하나라도 있으면 위험
  const apneaLabel = apneaCount > 0 ? '위험' : '이상 없음';
  const apneaTone = apneaCount > 0 ? 'bad' : 'good';

  // 점수 라벨 (>=80 좋음, >=50 보통, 그 아래 주의)
  const rawScore = Number.isFinite(breathing.score) ? breathing.score
                  : Number.isFinite(breathing.average_score) ? breathing.average_score
                  : null;
  let scoreLabel = null; let scoreTone = 'normal';
  if (rawScore != null) {
    if (rawScore >= 80) { scoreLabel = '좋음'; scoreTone = 'good'; }
    else if (rawScore >= 50) { scoreLabel = '보통'; scoreTone = 'normal'; }
    else { scoreLabel = '주의'; scoreTone = 'bad'; }
  }

  const COLORS = {
    text: isDark ? '#F3F4F6' : '#111',
    subtle: isDark ? '#AAB0B6' : '#555',
    label: isDark ? '#E5E7EB' : '#333',
    grid: isDark ? '#2f3236' : '#EAEAEA',
    frame: isDark ? '#2a2d31' : '#E5E5E5',
    bar: isDark ? '#80848a' : '#BDBDBD',
    line: '#9D2235', // brand color stays
    bgRect: isDark ? 'rgba(157,34,53,0.10)' : 'rgba(157,34,53,0.04)',
    apneaDash: '#9D2235'
  };

  // --- Dummy data for 10-minute intervals from 23:00 to 06:00 if no records exist ---
  const dummyRecords = [];
  if (!records.length) {
    const start = new Date('2025-10-08T23:00:00+09:00').getTime();
    const interval = 10 * 60 * 1000; // 10분 간격
    for (let i = 0; i < 42; i++) { // 7시간 → 42포인트
      const t = new Date(start + i * interval);
      const avg = 15 + Math.sin(i/6) * 2 + (Math.random() - 0.5) * 0.8;
      const min = avg - (0.8 + Math.random()*0.6);
      const max = avg + (0.8 + Math.random()*0.6);
      dummyRecords.push({time: t.toISOString(), avg_bpm: avg, min_bpm: min, max_bpm: max});
    }
  }
  const displayRecords = records.length ? records : dummyRecords;

  // ---- Build scales ----
  const parsed = useMemo(()=>{
    const pts = displayRecords
      .map(r => ({
        t: new Date(r.time).getTime(),
        min: Number(r.min_bpm ?? r.min ?? r.low ?? r.minBpm),
        max: Number(r.max_bpm ?? r.max ?? r.high ?? r.maxBpm),
        avg: Number(r.bpm ?? r.avg_bpm ?? r.avg ?? r.mean ?? r.average)
      }))
      .filter(p => !isNaN(p.t) && Number.isFinite(p.avg))
      .sort((a,b)=>a.t-b.t);
    if (pts.length === 0) return {pts:[], min:0, max:1, t0:0, t1:1};
    const min = Math.min(...pts.map(p=> Number.isFinite(p.min) ? p.min : p.avg));
    const max = Math.max(...pts.map(p=> Number.isFinite(p.max) ? p.max : p.avg));
    const t0 = pts[0].t;
    const t1 = pts[pts.length-1].t;
    return {pts, min, max, t0, t1};
  }, [displayRecords]);

  // ---- Densify to 10-minute grid between t0 and t1 ----
  const dense = useMemo(()=>{
    const pts = parsed.pts;
    if (!pts.length) return [];
    const step = 10 * 60 * 1000; // 10 minutes
    const res = [];
    let i = 0;
    for (let t = parsed.t0; t <= parsed.t1 + 1; t += step) {
      while (i < pts.length - 1 && pts[i+1].t < t) i++;
      const a = pts[i];
      const b = i < pts.length - 1 ? pts[i+1] : pts[i];
      const span = Math.max(1, (b.t - a.t));
      const r = Math.min(1, Math.max(0, (t - a.t) / span));
      const lerp = (va, vb) => (va!=null && isFinite(va) && vb!=null && isFinite(vb)) ? (va + (vb - va) * r) : (va!=null ? va : vb);
      const avg = lerp(a.avg, b.avg);
      const min = lerp(a.min ?? (a.avg-1), b.min ?? (b.avg-1));
      const max = lerp(a.max ?? (a.avg+1), b.max ?? (b.avg+1));
      res.push({ t, avg, min, max });
    }
    return res;
  }, [parsed]);

  const width = 540, height = 260;
  const pad = {l: 40, r: 32, t: 24, b: 44};
  const innerW = width - pad.l - pad.r;
  const innerH = height - pad.t - pad.b;

  const yMin = Math.max(0, Math.floor(parsed.min - 2));
  const yMax = Math.ceil(parsed.max + 2);
  const xScale = (t)=> pad.l + (parsed.t1===parsed.t0 ? 0 : (t-parsed.t0)/(parsed.t1-parsed.t0)) * innerW;
  const yScale = (v)=> pad.t + (1 - (v - yMin)/(yMax - yMin)) * innerH;

  // Simple moving average for smoother line (window=3)
  const linePts = useMemo(()=>{
    const arr = dense;
    if (arr.length === 0) return [];
    const w = 3;
    const smooth = arr.map((p,i)=>{
      const s = Math.max(0,i-w+1);
      const slice = arr.slice(s, i+1);
      const avg = slice.reduce((a,b)=>a+b.avg,0)/slice.length;
      return { t:p.t, v: avg };
    });
    return smooth.map(p=>({x:xScale(p.t), y:yScale(p.v)}));
  }, [dense]);

  // Bars (min-max).
  const bars = useMemo(()=>{
    const arr = dense;
    if (arr.length===0) return [];
    return arr.map(p=>{
      const x = xScale(p.t);
      const bw = Math.max(4, innerW / Math.max(36, arr.length*1.6));
      const y1 = yScale(Math.min(yMax, Number.isFinite(p.max) ? p.max : p.avg));
      const y2 = yScale(Math.max(yMin, Number.isFinite(p.min) ? p.min : p.avg));
      return {x: x - bw/2, y: Math.min(y1,y2), h: Math.max(2, Math.abs(y2 - y1)), w: bw};
    });
  }, [dense, innerW, yMin, yMax]);

  // Apnea events positions
  const apnea = useMemo(()=>{
    if (!events.length || parsed.pts.length===0) return [];
    return events.map(e=>{
      const t = new Date(e.time || e).getTime();
      if (isNaN(t)) return null;
      const x = xScale(t);
      return {x};
    }).filter(Boolean);
  }, [events, parsed]);

  return (
    <BaseModal open={open} onClose={onClose} title={title} isDark={isDark} width={520}>
      <div style={{display:'flex', flexDirection:'column', alignItems:'center', gap:10}}>
        <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} style={{display:'block', maxWidth:'100%'}}>
          {/* background */}
          <rect x={pad.l} y={pad.t} width={innerW} height={innerH} fill={COLORS.bgRect} rx="8" />
          {/* y grid (3 lines) */}
          {[0,0.5,1].map((p,i)=>{
            const y = pad.t + p*innerH;
            return <line key={i} x1={pad.l} y1={y} x2={width-pad.r} y2={y} stroke={COLORS.grid} />
          })}

          {/* min-max bars */}
          {bars.map((b,i)=>(
            <rect key={i} x={b.x} y={b.y} width={b.w} height={b.h} fill={COLORS.bar} rx="3" />
          ))}

          {/* average line */}
          {linePts.length>1 && (
            <path d={linePts.map((p,i)=> (i? 'L':'M')+p.x+','+p.y).join(' ')} stroke={COLORS.line} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" fill="none" />
          )}

          {/* apnea events */}
          {apnea.map((a,i)=>(
            <line key={i} x1={a.x} y1={pad.t} x2={a.x} y2={pad.t + innerH} stroke={COLORS.apneaDash} strokeDasharray="6 6" strokeWidth="2" opacity="0.7" />
          ))}

          {/* axes frame */}
          <rect x={pad.l} y={pad.t} width={innerW} height={innerH} fill="none" stroke={COLORS.frame} />


          {/* Time labels (start & end) */}
          <text x={pad.l} y={height - pad.b/2} fontSize="12" fill={COLORS.subtle} textAnchor="start">
            {new Date(parsed.t0).toLocaleTimeString('ko-KR', {hour:'2-digit', minute:'2-digit'})}
          </text>
          <text x={width - pad.r} y={height - pad.b/2} fontSize="12" fill={COLORS.subtle} textAnchor="end">
            {new Date(parsed.t1).toLocaleTimeString('ko-KR', {hour:'2-digit', minute:'2-digit'})}
          </text>

          {/* Apnea labels ABOVE each dashed line */}
          {apnea.map((a,i)=> (
            <text key={`label-${i}`} x={a.x} y={pad.t - 8} fontSize="12" fill={COLORS.line} textAnchor="middle">
              {new Date(events[i]?.time || events[i]).toLocaleTimeString('ko-KR', {hour:'2-digit', minute:'2-digit'})}
            </text>
          ))}
        </svg>
        {/* OUTSIDE legend: centered under the graph */}
        <div style={{
          width: width,
          display:'flex',
          justifyContent:'center',
          alignItems:'center',
          gap:12,
          marginTop: 6
        }}>
          <div style={{display:'flex', alignItems:'center', gap:8}}>
            <svg width="28" height="8" style={{display:'block'}}>
              <path d="M2 4 L26 4" stroke="#9D2235" strokeWidth="2" strokeLinecap="round" />
            </svg>
            <span style={{fontSize:12, color:COLORS.label}}>평균 (10분)</span>
          </div>
          <div style={{display:'flex', alignItems:'center', gap:8}}>
            <svg width="10" height="14" style={{display:'block'}}>
              <rect x="3" y="2" width="3" height="8" rx="2" fill={COLORS.bar} />
            </svg>
            <span style={{fontSize:12, color:COLORS.label}}>최소–최대 범위</span>
          </div>
          <div style={{display:'flex', alignItems:'center', gap:8}}>
            <svg width="10" height="16" style={{display:'block'}}>
              <line x1="5" y1="2" x2="5" y2="14" stroke={COLORS.apneaDash} strokeDasharray="4 4" strokeWidth="1.5" />
            </svg>
            <span style={{fontSize:12, color:COLORS.label}}>무호흡</span>
          </div>
        </div>
        {/* Summary row: score + apnea */}
        <div style={{
          width: width,
          display:'flex',
          justifyContent:'center',
          alignItems:'center',
          gap:12,
          marginTop: 8,
          flexWrap:'wrap'
        }}>
          {rawScore != null && (
            <div style={{fontSize:12, color:COLORS.label, display:'flex', alignItems:'center', gap:6}}>
              호흡 점수: <strong>{Math.round(rawScore)}</strong>
              <span className={`factor-badge ${scoreTone}`}>{scoreLabel}</span>
            </div>
          )}
          <div style={{fontSize:12, color:COLORS.label, display:'flex', alignItems:'center', gap:6}}>
            수면 중 무호흡: <strong>{apneaCount}</strong>회
            <span className={`factor-badge ${apneaTone}`}>{apneaLabel}</span>
          </div>
        </div>
      </div>
    </BaseModal>
  );
}