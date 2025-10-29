import React, {useMemo} from 'react';
import BaseModal from './BaseModal';
import '../../label.css';

// Sleep stage rows (top -> bottom)
const ROWS = [
  {key:'awake', label:'수면 중 깸'},
  {key:'rem',   label:'렘 수면'},
  {key:'light', label:'얕은 수면'},
  {key:'deep',  label:'깊은 수면'},
];

// Flat style palette
const COLORS = {
  track: '#F3F4F6',  // 전체 트랙 (밝은 회색)
  grid: 'rgba(0,0,0,0.08)',
  text: '#444',
  barDefault: '#658ee1ff', // fallback
};


function parseTs(v){
  const d = new Date(v);
  return isNaN(d.getTime()) ? null : d.getTime();
}

function fmtHM(ts){
  if (ts == null) return '--:--';
  const d = new Date(ts);
  if (isNaN(d.getTime())) return '--:--';
  const hh = String(d.getHours()).padStart(2,'0');
  const mm = String(d.getMinutes()).padStart(2,'0');
  return `${hh}:${mm}`;
}

export default function DepthModal({
  open,
  onClose,
  segments = [], // [{startIso, state}] or [{start, state}]
  endIso,        // optional absolute end time
  title = '수면 깊이',
  cycles = 3,
  tone = 'good', // 'good' | 'warn' | 'bad'
}){
  // sanitize & sort
  const rows = ROWS;
  const data = useMemo(()=>{
    const arr = (Array.isArray(segments) ? segments : []).map(s=>({
      t: s.start ? parseTs(s.start) : (s.startIso ? parseTs(s.startIso) : parseTs(s.start_time || s.startTime)),
      state: (s.state || s.stage || s.value || '').toLowerCase()
    })).filter(s=>s.t!=null).sort((a,b)=>a.t-b.t);
    return arr;
  }, [segments]);

  const tStart = data.length ? data[0].t : null;
  const tEnd = useMemo(()=>{
    if (endIso) {
      const e = parseTs(endIso); if (e) return e;
    }
    if (data.length >= 2) return data[data.length-1].t + 10*60*1000; // last + 10m fallback
    if (data.length === 1) return data[0].t + 60*60*1000;           // +1h fallback
    return Date.now();
  }, [data, endIso]);

  const width = 1100; const height = 420; // modal 내부에서 충분한 크기
  const pad = {l: 40, r: 140, t: 28, b: 56};
  const innerW = width - pad.l - pad.r;
  const innerH = height - pad.t - pad.b;
  const rowH = innerH / rows.length;

  const scaleX = (ts)=>{
    if (tStart==null || tEnd==null || tEnd<=tStart) return pad.l;
    const p = (ts - tStart) / (tEnd - tStart);
    return pad.l + Math.max(0, Math.min(1, p)) * innerW;
  };

  // Build continuous blocks for each segment (from current start to next start)
  const blocks = useMemo(()=>{
    if (!data.length) return [];
    const arr = [];
    for (let i=0; i<data.length; i++){
      const cur = data[i];
      const next = data[i+1];
      const x1 = scaleX(cur.t);
      const x2 = scaleX(next ? next.t : tEnd);
      const rowIdx = rows.findIndex(r=>r.key===cur.state || (cur.state.includes('awake') && r.key==='awake'))
                   ?? rows.findIndex(r=>r.key==='light');
      const idx = rowIdx>=0 ? rowIdx : 2; // default light
      const yCenter = pad.t + idx * rowH + rowH/2;
      const h = Math.max(8, rowH*0.55);
      const y = yCenter - h/2;
      arr.push({x:x1, w:Math.max(1, x2-x1), y, h, rowIdx: idx});
    }
    return arr;
  }, [data, rows, rowH, tEnd]);

  // bottom ticks (start / mid / end)
  const ticks = useMemo(()=>{
    if (tStart==null || tEnd==null) return [];
    const mid = Math.round((tStart + tEnd)/2);
    return [tStart, mid, tEnd];
  }, [tStart, tEnd]);

  return (
    <BaseModal open={open} onClose={onClose} title={title}>
      <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} style={{display:'block', width:'100%'}}>
        {/* grid lines */}
        <line x1={pad.l} y1={pad.t} x2={pad.l} y2={height-pad.b} stroke={COLORS.grid} />
        <line x1={width-pad.r} y1={pad.t} x2={width-pad.r} y2={height-pad.b} stroke={COLORS.grid} />
        {rows.map((r,i)=>{
          const y = pad.t + i*rowH + rowH/2;
          return <line key={r.key} x1={pad.l} y1={y} x2={width-pad.r} y2={y} stroke={COLORS.grid} strokeDasharray="4 6" />
        })}

        {/* base tracks per row */}
        {rows.map((r,i)=>{
          const yCenter = pad.t + i*rowH + rowH/2;
          const h = Math.max(8, rowH*0.55);
          const y = yCenter - h/2;
          return (
            <rect key={r.key} x={pad.l} y={y} width={innerW} height={h} fill={COLORS.track} />
          );
        })}

        {/* active blocks */}
        {blocks.map((b,idx)=>(
          <rect
            key={idx}
            x={b.x}
            y={b.y}
            width={b.w}
            height={b.h}
            fill={COLORS.barDefault}
          />
        ))}

        {/* right labels */}
        {rows.map((r,i)=>{
          const y = pad.t + i*rowH + rowH/2 + 5;
          return (
            <text key={r.key} x={width-pad.r+12} y={y} fill={COLORS.text} fontSize={24}>{r.label}</text>
          );
        })}

        {/* bottom time ticks */}
        {ticks.map((t,i)=>{
          const x = scaleX(t);
          const y = height - pad.b + 28;
          return (
            <text key={i} x={x} y={y} textAnchor="middle" fill="#666" fontSize={24}>{fmtHM(t)}</text>
          );
        })}
      </svg>
      <div style={{
        display:'flex',
        justifyContent:'center',
        alignItems:'center',
        gap:12,
        marginTop: 8
      }}>
        <div style={{fontSize:24, color:'#333'}}>수면 주기 : <strong>{cycles}</strong>회</div>
        <span className={`factor-badge ${tone}`}>{tone==='good' ? '좋음' : (tone==='bad' ? '부족함' : '보통')}</span>
      </div>
    </BaseModal>
  );
}