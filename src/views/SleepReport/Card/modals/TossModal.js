import React, {useMemo, useContext} from 'react';
import BaseModal from './BaseModal';

import {SleepDataContext} from '../../../SleepReport';
import '../../label.css';

const LG = {
  red: '#A50034',
  redSoft: 'rgba(165,0,52,0.18)',
  redTrack: 'rgba(165,0,52,0.12)',
  borderLight: 'rgba(0,0,0,0.08)'
};

function fmtHM(dateOrIso){
  if(!dateOrIso) return '--:--';
  const d = new Date(dateOrIso);
  if (isNaN(d.getTime())) return '--:--';
  const hh = String(d.getHours()).padStart(2,'0');
  const mm = String(d.getMinutes()).padStart(2,'0');
  return `${hh}:${mm}`;
}

function TossTrack({startIso, endIso, events=[], isDark=false}){
  const redTrackBg = isDark ? 'rgba(165,0,52,0.22)' : LG.redTrack;
  const redSoftRing = isDark ? 'rgba(165,0,52,0.35)' : LG.redSoft;

  const eventIsos = useMemo(() => {
    const arr = Array.isArray(events) ? events : [];
    return arr
      .map(v => (typeof v === 'string' ? v : (v && (v.start || v.time))))
      .filter(Boolean);
  }, [events]);

  const {start, end, span} = useMemo(()=>{
    let s = startIso ? new Date(startIso).getTime() : NaN;
    let e = endIso ? new Date(endIso).getTime() : NaN;

    if ((isNaN(s) || isNaN(e)) && Array.isArray(eventIsos) && eventIsos.length){
      const times = eventIsos.map(v=>new Date(v).getTime()).filter(t=>!isNaN(t));
      if (times.length){
        if (isNaN(s)) s = Math.min(...times);
        if (isNaN(e)) e = Math.max(...times);
      }
    }

    if (isNaN(s)) s = Date.now() - 8*60*60*1000; // fallback: now-8h
    if (isNaN(e)) e = Date.now();                 // fallback: now
    if (e <= s) e = s + 60*60*1000;               // ensure span >= 1h

    return {start: s, end: e, span: Math.max(1, e - s)};
  }, [startIso, endIso, eventIsos]);

  const pos = (iso)=>{
    const t = new Date(iso).getTime();
    if (isNaN(t)) return '0%';
    const p = (t - start) / span; // 0..1
    return `${Math.max(0, Math.min(1, p)) * 100}%`;
  };

  // label ticks: start / first event / second event / end (fallback to thirds if not enough events)
  const [l2, l3] = useMemo(()=>{
    const valid = (Array.isArray(eventIsos) ? eventIsos : [])
      .map(v=>new Date(v))
      .filter(d=>!isNaN(d.getTime()));
    if (valid.length >= 2) return [valid[0], valid[1]];
    const t1 = new Date(start + span * 1/3);
    const t2 = new Date(start + span * 2/3);
    return [t1, t2];
  }, [eventIsos, start, span]);

  return (
    <div style={{marginTop: 8}}>
      <div style={{position:'relative', height: 16, background: redTrackBg, borderRadius: 4, boxShadow: `inset 0 0 0 1px ${redSoftRing}`}}>
        {/* inner thin line for depth */}
        <div style={{position:'absolute', left: 6, right: 6, top: '50%', height: 1.5, background: redSoftRing, transform:'translateY(-50%)'}} />
        {eventIsos.map((iso, i) => (
          <div key={i} style={{position:'absolute', left: pos(iso), top: 0, bottom: 0, width: 3, transform: 'translateX(-50%)', background: LG.red, borderRadius: 1.5, boxShadow: `0 0 0 1px ${redSoftRing}`}} />
        ))}
      </div>
      <div style={{display:'flex', justifyContent:'space-between', marginTop: 6, color: isDark ? '#AAB0B6' : '#6B6F76', fontSize: 10}}>
        <div>{fmtHM(startIso)}</div>
        <div>{fmtHM(l2)}</div>
        <div>{fmtHM(l3)}</div>
        <div>{fmtHM(endIso)}</div>
      </div>
    </div>
  );
}

const toneLabel = (tone)=> tone==='good' ? '좋음' : (tone==='bad' ? '주의' : '보통');

const Badge = ({tone='warn', children}) => (
  <span className={`factor-badge ${tone}`} style={{fontSize:12}}>
    {children ?? toneLabel(tone)}
  </span>
);

export default function TossModal({
  open,
  onClose,
  startIso,
  endIso,
  events = [],
  count = 0,
  awakeMinutes = 0,
  tone = 'warn',
  isDark = false,
}){
  // Read live data from SleepDataContext
  const ctx = useContext(SleepDataContext);
  const src = (ctx?.remote || ctx?.data) || {};
  const rustle = src?.rustle || {};

  // Prefer explicit props if provided; otherwise, use context-backed values
  const finalStartIso = startIso || src?.sleep_time || null;
  const finalEndIso = endIso || src?.wake_time || null;

  const ctxEvents = Array.isArray(rustle.records) ? rustle.records : [];
  const finalEvents = (Array.isArray(events) && events.length > 0) ? events : ctxEvents;

  const finalCount = Number.isFinite(count) && count > 0
    ? count
    : (Number(rustle.total_count) || (Array.isArray(finalEvents) ? finalEvents.length : 0));

  const awakeFromCtx = Number(src?.sleep_awake_minutes);
  const finalAwakeMinutes = Number.isFinite(awakeMinutes) && awakeMinutes > 0 ? awakeMinutes : (Number.isFinite(awakeFromCtx) ? awakeFromCtx : 0);

  const rustleScore = Number(rustle.score);
  const toneByScore = (s)=> (Number.isFinite(s) ? (s>=80 ? 'good' : (s>=50 ? 'normal' : 'bad')) : 'normal');
  const finalTone = toneByScore(rustleScore);

  return (
    <BaseModal open={open} title="뒤척임" onClose={onClose} isDark={isDark} width={520}>
      <div style={{fontSize: 14, color: isDark ? '#E5E7EB' : '#444', lineHeight: 1.4}}>뒤척임이 일어난 시간대와 횟수를 확인하세요.</div>

      <div style={{marginTop: 10}}>
        <TossTrack startIso={finalStartIso} endIso={finalEndIso} events={finalEvents} isDark={isDark} />
      </div>

      <div style={{display:'flex', justifyContent:'space-between', alignItems:'center', marginTop: 10}}>
        <div style={{fontSize: 12, fontWeight: 400, color: isDark ? '#F3F4F6' : '#111'}}>뒤척임 횟수: {finalCount}회</div>
        <Badge tone={finalTone} />
      </div>
    </BaseModal>
  );
}