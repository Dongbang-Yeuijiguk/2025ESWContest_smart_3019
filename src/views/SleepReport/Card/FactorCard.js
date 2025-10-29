import React, {useState, useContext} from 'react';
import BodyText from '@enact/sandstone/BodyText';
import { SleepDataContext } from '../../SleepReport';

import DurationModal from './modals/DurationModal';
import TossModal from './modals/TossModal';
import RespirationModal from './modals/RespirationModal';

import '../label.css';

// ---- Brand tokens (local copy) ----
const LG_BRAND = {
  red: '#A50034',
  pinkTint: 'rgba(165,0,52,0.06)',
  pinkTintStrong: 'rgba(165,0,52,0.12)',
  borderLight: 'rgba(0,0,0,0.08)',
  surface: '#FFFFFF',
  shadowSoft: '0 6px 24px rgba(0,0,0,0.06)',
  shadowHover: '0 10px 28px rgba(0,0,0,0.10)'
};

const diffISO = (sISO, eISO) => {
  if (!sISO || !eISO) return 0;
  const s = new Date(sISO).getTime();
  const e = new Date(eISO).getTime();
  if (!Number.isFinite(s) || !Number.isFinite(e)) return 0;
  return Math.max(0, Math.round((e - s) / 60000));
};

const toneByScore = (s) => {
  if (!Number.isFinite(s)) return 'normal';
  if (s >= 80) return 'good';
  if (s >= 50) return 'normal';
  return 'bad';
};

// ---- Grid cards ----
const ratingStyles = {
  good:   { label: '좋음',  text: '#1B5E20', border: 'rgba(27,94,32,0.35)', bg: 'rgba(27,94,32,0.08)' },
  normal: { label: '보통',  text: '#7A4A00', border: 'rgba(250,170,20,0.55)', bg: 'rgba(250,170,20,0.12)' },
  bad:    { label: '주의',  text: '#A50034', border: 'rgba(165,0,52,0.55)', bg: 'rgba(165,0,52,0.10)' }
};
const grid = { display:'grid', gridTemplateColumns:'repeat(3, minmax(300px, 1fr))', gap:12, width:'100%' };
const card = { background:'#fff', borderRadius:12, boxShadow:'0 1px 4px rgba(0,0,0,0.06)', outline:'1px solid rgba(0,0,0,0.06)', padding:12, display:'flex', flexDirection:'column', minHeight:120 };
const head = { display:'flex', alignItems:'center', justifyContent:'space-between', marginBottom:6 };
const title = { fontSize:18, fontWeight:800, color:'#111' };

function Badge({tone='good'}) {
  const s = ratingStyles[tone] || ratingStyles.good;
  return <span className={`factor-badge ${tone}`} style={{
    color:s.text, 
    backgroundColor:s.bg, 
    border:`1px solid ${s.border}`, 
    borderRadius:8, 
    padding:'2px 8px', 
    fontWeight:700
  }}>{s.label}</span>;
}
function Lines({items=[]}){
  // 내부 본문 텍스트 크게 + 간격 더 촘촘하게
  return (
    <div style={{display:'grid', rowGap:2, marginTop:2}}>
      {items.map((line,i)=>(
        <div key={i} style={{fontSize:14, lineHeight:1.3, fontWeight:600, color:'#222'}}>{line}</div>
      ))}
    </div>
  );
}

export default function FactorCards({ data, factors, averages }){
  const ctx = useContext(SleepDataContext);
  const source = data && Object.keys(data||{}).length ? data
                : (ctx && (ctx.remote || ctx.data)) ? (ctx.remote || ctx.data)
                : {};

  const [detailOpen, setDetailOpen] = useState(null); // 'duration'|'toss'|'respiration'
  const {avgWeek, avgMonth} = averages || {};
  const totalMin = diffISO(source?.sleep_time, source?.wake_time);
  const h = Math.floor(totalMin / 60);
  const m = totalMin % 60;

  const tossCount = Number(source?.rustle?.total_count ?? (Array.isArray(source?.toss_and_turn_times) ? source.toss_and_turn_times.length : 0));
  const awakeMinutes = source?.sleep_awake_minutes ?? (factors?.toss?.awakeMinutes ?? 35);

  const avgResp = Number(source?.breathing?.average_bpm ?? factors?.respiration?.avgPerMin ?? 0);
  const safeAvgResp = Number.isFinite(avgResp) && avgResp > 0 ? avgResp : 13.2;
  const apneaCount = Array.isArray(source?.breathing?.unbreath_events) ? source.breathing.unbreath_events.length : (factors?.respiration?.apneaCount ?? 0);

  const respScore = Number(source?.breathing?.score);

  const durationScore = Number(source?.sleep_score);
  const isGoodDuration = totalMin >= 420 && totalMin <= 540;
  const durationTone = isGoodDuration ? 'good' : (durationScore >= 50 ? 'normal' : 'bad');
  const tossScore = Number(source?.rustle?.score);
  const tossTone = tossScore >= 80 ? 'good' : tossScore >= 50 ? 'normal' : 'bad';
  const respTone = toneByScore(respScore);

  const items = [
    { key:'duration',    title:'수면 시간',   tone:durationTone,
      lines:[`수면 시간: ${Number.isFinite(h)?h:'-'}시간 ${Number.isFinite(m)?m:'-'}분`] },
    { key:'toss',        title:'뒤척임',     tone:tossTone,
      lines:[`뒤척임 횟수: ${tossCount}회`]},
    { key:'respiration', title:'호흡',       tone:respTone,
      lines:[`평균 호흡수: ${safeAvgResp.toFixed(2)}회`, `수면중 무호흡: ${apneaCount}회`] },
  ];

  return (
    <>
      <div style={grid}>
        {items.map(d => (
          <div
            key={d.key}
            role="button"
            tabIndex={0}
            onClick={()=>setDetailOpen(d.key)}
            onKeyDown={(e)=>{if(e.key==='Enter'||e.key===' ') setDetailOpen(d.key);}}
            style={{...card, cursor:'pointer'}}
          >
            <div style={head}>
              <div style={title}>{d.title}</div>
              <Badge tone={d.tone} />
            </div>
            <Lines items={d.lines} />
          </div>
        ))}
      </div>
      
      {/*
      <DepthModal
        open={detailOpen==='depth'}
        onClose={()=>setDetailOpen(null)}
        segments={depthSegments}
        endIso={data?.sleep_end_time || '2025-10-11T06:00:00'}
      />
      */}

      <DurationModal
        open={detailOpen==='duration'}
        onClose={()=>setDetailOpen(null)}
        progress={factors?.duration?.progress||0}
        averages={averages||{}}
      />

      <TossModal
        open={detailOpen==='toss'}
        onClose={()=>setDetailOpen(null)}
      />

      <RespirationModal
        open={detailOpen==='respiration'}
        onClose={()=>setDetailOpen(null)}
      />
    </>
  );
}