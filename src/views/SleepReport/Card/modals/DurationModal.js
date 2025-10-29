import React, {useMemo, useState, useContext} from 'react';
import BaseModal from './BaseModal';
import '../../label.css';
import {SleepDataContext} from '../../../SleepReport';

const LG_BRAND = { red: '#A50034' };

const SegmentButton = ({children, active, onClick}) => (
  <button
    onClick={onClick}
    style={{
      padding:'6px 10px',
      borderRadius:999,
      border: active ? '2px solid transparent' : `2px solid ${LG_BRAND.red}`,
      background: active ? LG_BRAND.red : 'transparent',
      color: active ? '#fff' : LG_BRAND.red, // Ensure white text when active
      fontSize:14,
      fontWeight:900,
      lineHeight:1,
      minWidth:96,
      cursor:'pointer',
      boxShadow: active ? '0 2px 6px rgba(165,0,52,0.25)' : 'none',
      transition:'all 0.2s ease-in-out'
    }}
  >{children}</button>
);

const toneDefaultLabel = (tone)=> tone==='good' ? '좋음' : (tone==='bad' ? '주의' : '보통');
const RatingBadge = ({tone='good', children}) => (
  <span className={`factor-badge ${tone}`}>
    {children ?? toneDefaultLabel(tone)}
  </span>
);

  const OptimalRangeBar = ({
    valueMin = 0,
    optimalStart = 7*60, // 7h
    optimalEnd = 9*60,   // 9h
    totalSpan = 12*60,   // total scale span to display (default 12h)
  }) => {
    // Center domain around the midpoint of the optimal band (8h)
    const mid = (optimalStart + optimalEnd) / 2; // 8h
    const domainStart = mid - totalSpan / 2;
    const domainEnd = mid + totalSpan / 2;

    // Larger visuals
    const width = 640; const height = 100; const radius = 999;
    const padX = 48; const barY = 42; const barH = 12; const knobW = 8; const knobH = 20;

    const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
    const scale = (v)=>{
      const clamped = clamp(v, domainStart, domainEnd);
      return padX + ((clamped - domainStart) / (domainEnd - domainStart)) * (width - padX*2);
    };

    const optX1 = scale(optimalStart);
    const optX2 = scale(optimalEnd);
    const knobX = scale(valueMin);

    return (
      <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} style={{display:'block'}}>
        {/* base bar */}
        <rect x={padX} y={barY} width={width-padX*2} height={barH} fill="#DCDCDC" />
        {/* optimal band (centered) */}
        <rect x={optX1} y={barY} width={Math.max(0, optX2-optX1)} height={barH} fill="#6EA8FF" />
        {/* knob */}
        <rect x={knobX - knobW/2} y={barY - (knobH-barH)/2} width={knobW} height={knobH} rx={4} fill="#3A3A3A" />

        {/* labels */}
        <text x={optX1} y={barY+44} textAnchor="middle" fontSize={12} fill="#808080">7 시간</text>
        <text x={optX2} y={barY+44} textAnchor="middle" fontSize={12} fill="#808080">9 시간</text>

        {/* legend */}
        <rect x={padX} y={barY+56} width={10} height={10} fill="#6EA8FF" />
        <text x={padX+24} y={barY+70} fontSize={12} fill="#666">최적 범위</text>
      </svg>
    );
  };

export default function DurationModal({open, onClose, progress=0, averages={}}){
  const [range, setRange] = useState('day');

  // Pull live data from SleepDataContext (remote > data)
  const ctx = useContext(SleepDataContext);
  const src = (ctx?.remote || ctx?.data) || {};

  // Helpers
  const toMinutesHM = (hm)=>{
    if (!hm || typeof hm !== 'string') return null;
    const [H, M] = hm.split(':').map(Number);
    if (!Number.isFinite(H) || !Number.isFinite(M)) return null;
    return H*60 + M;
  };
  const diffHM = (startHM, endHM)=>{
    if (startHM==null || endHM==null) return null;
    let d = endHM - startHM;
    if (d < 0) d += 24*60; // cross midnight
    return d;
  };
  const diffISO = (sISO, eISO)=>{
    if (!sISO || !eISO) return null;
    const s = new Date(sISO).getTime();
    const e = new Date(eISO).getTime();
    if (!Number.isFinite(s) || !Number.isFinite(e)) return null;
    const d = Math.max(0, Math.round((e - s)/60000));
    return d;
  };

  // Compute today (day) duration from ISO
  const dayTotalMinFromCtx = useMemo(()=> diffISO(src.sleep_time, src.wake_time) ?? 0, [src.sleep_time, src.wake_time]);

  // Compute weekly average from weekly_pattern
  const computedWeek = useMemo(()=>{
    const wp = Array.isArray(src.weekly_pattern) ? src.weekly_pattern : [];
    if (!wp.length) return {avgWeek: 0, weekMinutes: []};
    const mins = wp.map(({sleep_start, sleep_end}) => diffHM(toMinutesHM(sleep_start), toMinutesHM(sleep_end)) || 0);
    const sum = mins.reduce((a,b)=>a+b,0);
    const avg = Math.round(sum / (mins.length || 1));
    return {avgWeek: avg, weekMinutes: mins};
  }, [src.weekly_pattern]);

  // Merge with props fallback
  const avgWeek = averages?.avgWeek ?? computedWeek.avgWeek ?? 0;
  const weekMinutes = averages?.weekMinutes ?? computedWeek.weekMinutes ?? [];
  const avgMonth = averages?.avgMonth ?? 0; // no monthly source in API — keep prop fallback

  // Derive h/m for day view from context if props missing
  const totalMinDay = dayTotalMinFromCtx;
  const h = Math.floor(totalMinDay/60);
  const m = totalMinDay%60;

  // 일간 평가: 실제 취침~기상 시간으로 판정 (7~9시간 = 좋음, 그 외 보통)
  const isGoodRange = (min) => min >= 420 && min <= 540;
  const dayTone = isGoodRange(dayTotalMinFromCtx) ? 'good' : 'normal';
  const dayLabel = dayTone === 'good' ? '좋음' : '보통';

  // Weekly / Monthly tone & label (avg within 7~9h => good, else normal)
  const weekTone = isGoodRange(avgWeek) ? 'good' : 'normal';
  const weekLabel = weekTone === 'good' ? '좋음' : '보통';

  // 월간 평균(임의 하드코딩: 450분 = 7시간 30분)
  const avgMonthHard = averages?.avgMonth ?? 450;
  const monthTone = isGoodRange(avgMonthHard) ? 'good' : 'normal';
  const monthLabel = monthTone === 'good' ? '좋음' : '보통';

  const totalMin = useMemo(()=> totalMinDay, [totalMinDay]);
  return (
    <BaseModal open={open} title="수면 시간" onClose={onClose}>
      <div style={{display:'flex', justifyContent:'center', gap:8, marginTop:8}}>
        <SegmentButton active={range==='day'} onClick={()=>setRange('day')}>일간</SegmentButton>
        <SegmentButton active={range==='week'} onClick={()=>setRange('week')}>주간</SegmentButton>
        <SegmentButton active={range==='month'} onClick={()=>setRange('month')}>월간</SegmentButton>
      </div>

      {/* Status Row */}
      <div style={{display:'flex', justifyContent:'space-between', alignItems:'center', marginTop:8}}>
        <div style={{fontSize:12, color:'#666'}}>
          {range==='day' ? '오늘 수면' : range==='week' ? '주간 평균' : '월간 평균'}
        </div>
        <div style={{display:'flex', alignItems:'center', gap:8}}>
          <div style={{fontSize:16, fontWeight:900, color:'#111'}}>
            {range==='day' && `${h}h ${m}m`}
            {range==='week' && `${Math.floor(avgWeek/60)}h ${avgWeek%60}m`}
            {range==='month' && `${Math.floor(avgMonthHard/60)}h ${avgMonthHard%60}m`}
          </div>
          <RatingBadge
            tone={range==='day' ? dayTone : (range==='week' ? weekTone : monthTone)}
          >
            {range==='day' ? dayLabel : (range==='week' ? weekLabel : monthLabel)}
          </RatingBadge>
        </div>
      </div>

      {/* Visuals */}
      <div style={{marginTop:8, display:'flex', justifyContent:'center', alignItems:'center'}}>
        <OptimalRangeBar
          valueMin={
            range==='day'
              ? totalMin
              : range==='week'
              ? avgWeek
              : avgMonthHard
          }
          optimalStart={7*60}
          optimalEnd={9*60}
          totalSpan={12*60}
        />
      </div>

            {/* Guidance */}
      <div style={{fontSize:12, color:'#666', marginTop:8, display:'flex', justifyContent:'flex-end', paddingRight:12, lineHeight:1.5}}>
        {'각 막대의 파란 영역은 권장 범위(7~9시간)를, 마커는 실제 수면 시간을 나타냅니다.'}
      </div>
    </BaseModal>
  );
}