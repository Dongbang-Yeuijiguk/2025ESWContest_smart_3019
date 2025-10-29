// 대시보드 메인 화면 - 수면 리포트 카드
import React, {useEffect, useMemo, useState} from 'react';
import Heading from '@enact/sandstone/Heading';
import BodyText from '@enact/sandstone/BodyText';
import {Row, Column} from '@enact/ui/Layout';

// Local design tokens (self-contained)
const TYPE = { h2: 20, body: 14, tiny: 12 };

const SLEEP_REPORT_ENDPOINT = process.env.REACT_APP_SLEEP_REPORT_ENDPOINT || '/api/v1/dashboard/sleep/report';
async function prefetchTodaySleep(){
  try {
    const date = new Date().toISOString().slice(0,10);
    const url = `${SLEEP_REPORT_ENDPOINT}/${encodeURIComponent(date)}`;
    const res = await fetch(url);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    if (typeof window !== 'undefined' && window.sessionStorage) { window.sessionStorage.setItem('sleepReport', JSON.stringify(data)); }
  } catch (e) {
    // ignore – we'll fetch again on the page
  }
}
const LH = { tight: 1.1, normal: 1.35 };
const LG_BRAND = { red: '#A50034', borderDark: 'rgba(255,255,255,0.12)', borderLight: 'rgba(0,0,0,0.08)' };

// ---- Mock sleep dataset (until server API is ready) ----
const mockSleep = {
  date: '2025-09-14',
  total_sleep_duration_minutes: 420,
  sleep_start_time: '2025-09-13T23:00:00',
  sleep_end_time: '2025-09-14T06:00:00',
  sleep_score: 82,
  bpm_average: [70, 68, 66, 65, 64, 63, 62, 63, 64, 66, 68, 70],
  bpm_max:     [76, 74, 72, 71, 70, 69, 68, 69, 71, 73, 75, 77],
  bpm_min:     [64, 62, 60, 59, 58, 57, 56, 57, 58, 60, 61, 62],
  bpm_per_10min: [70, 68, 66, 65, 64, 63, 62, 63, 64, 66, 68, 70],
  toss_and_turn_times: [
    '2025-09-13T23:20:00',
    '2025-09-14T01:40:00'
  ]
};

// ---- Mock history for sleep score (x: date, y: score) ----
const mockSleepHistory = [
  {date: '2025-09-01', score: 48},
  {date: '2025-09-02', score: 55},
  {date: '2025-09-03', score: 82},
  {date: '2025-09-04', score: 68},
  {date: '2025-09-05', score: 73},
  {date: '2025-09-06', score: 45},
  {date: '2025-09-07', score: 65},
  {date: '2025-09-08', score: 68},
  {date: '2025-09-09', score: 37},
  {date: '2025-09-10', score: 79},
  {date: '2025-09-11', score: 74},
  {date: '2025-09-12', score: 81},
  {date: '2025-09-13', score: 86},
  {date: '2025-09-14', score: 82}
];

// Score color by band
const scoreColor = (s) => {
  if (s >= 80) return '#10b981';   // green (80~100)
  if (s >= 50) return '#eab308';    // yellow (51~79)
  return '#ef4444';                // red (<=50)
};

const AccentDot = ({isDark}) => (
  <div style={{
    width: 8, height: 8, borderRadius: 999, background: LG_BRAND.red,
    boxShadow: isDark ? '0 0 0 3px rgba(165,0,52,0.25)' : '0 0 0 3px rgba(165,0,52,0.12)'
  }} />
);

const GhostButton = ({children, isDark, onClick}) => (
  <div
    role="button" tabIndex={0} onClick={onClick}
    style={{
      display:'inline-flex', alignItems:'center', justifyContent:'center',
      padding:'6px 12px', borderRadius:999, border:`1px solid ${LG_BRAND.red}`,
      background:'transparent', color: isDark ? '#fff' : '#111',
      fontWeight:700, fontSize:14, cursor:'pointer',
      boxShadow: isDark ? '0 1px 4px rgba(0,0,0,0.35)' : '0 1px 4px rgba(0,0,0,0.08)'
    }}
  >
    {children}
  </div>
);

const RATING_TOKENS = {
  good: {label: '좋음', bg: 'rgba(16,185,129,0.12)', border: '1px solid rgba(16,185,129,0.35)', color: '#0f5132'},
  normal: {label: '보통', bg: 'rgba(234,179,8,0.12)',  border: '1px solid rgba(234,179,8,0.35)',  color: '#7a5d00'},
  bad:  {label: '주의', bg: 'rgba(239,68,68,0.12)',  border: '1px solid rgba(239,68,68,0.35)',  color: '#7f1d1d'}
};
const RatingBadge = ({title, rating = 'normal'}) => {
  const t = RATING_TOKENS[rating] || RATING_TOKENS.normal;
  return (
    <div style={{
      display:'inline-flex', alignItems:'center', gap:6,
      padding:'6px 10px', borderRadius:999,
      background:t.bg, border:t.border, color:t.color,
      fontWeight:800, fontSize:12, lineHeight:'1.1em'
    }}>
      <span>{title}</span>
      <span style={{opacity:0.9}}>· {t.label}</span>
    </div>
  );
};

const pad2 = (n) => String(n).padStart(2, '0');
const fmtHm = (dateStr) => {
  if (!dateStr) return '--:--';
  const d = new Date(dateStr);
  if (isNaN(d.getTime())) return '--:--';
  return `${pad2(d.getHours())}:${pad2(d.getMinutes())}`;
};

const diffMinutesISO = (startISO, endISO) => {
  if (!startISO || !endISO) return 0;
  const s = new Date(startISO).getTime();
  const e = new Date(endISO).getTime();
  if (!Number.isFinite(s) || !Number.isFinite(e)) return 0;
  return Math.max(0, Math.round((e - s) / 60000));
};

const toneByScore = (s) => (Number.isFinite(s) ? (s >= 80 ? 'good' : (s >= 50 ? 'normal' : 'bad')) : null);

const toneLabel = {good:'좋음', normal:'보통', bad:'주의'};
const toneColor = {
  good:   {fg:'#1B5E20', bg:'rgba(27,94,32,0.10)', bar:'#2E7D32', border:'rgba(27,94,32,0.35)'},
  normal: {fg:'#7A4A00', bg:'rgba(250,170,20,0.12)', bar:'#B26A00', border:'rgba(250,170,20,0.45)'},
  bad:    {fg:'#A50034', bg:'rgba(165,0,52,0.10)', bar:'#C2185B', border:'rgba(165,0,52,0.45)'}
};

// Inline SVG chart for sleep score history
const SleepScoreChart = ({data = [], dark = false, height = 160, padding = 16}) => {
  if (!Array.isArray(data) || data.length === 0) return null;
  const width = Math.max(48 * data.length, 320); // narrower scaling, smaller min width
  const vbW = width, vbH = height;
  const pad = padding;

  const scores = data.map(d => Number(d.score) || 0);
  const minY = 0;          // score range 0~100
  const maxY = 100;

  const stepX = (vbW - pad * 2) / Math.max(1, data.length - 1);
  const yScale = (s) => pad + (vbH - pad * 2) * (1 - (s - minY) / (maxY - minY));

  const points = data.map((d, i) => [pad + i * stepX, yScale(d.score)]);
  const path = points.map((p, i) => (i === 0 ? `M ${p[0]},${p[1]}` : `L ${p[0]},${p[1]}`)).join(' ');

  const gridYVals = [20, 40, 60, 80];

  return (
    <svg viewBox={`0 0 ${vbW} ${vbH}`} preserveAspectRatio="xMidYMid meet" style={{width: '100%', height: '100%'}}>
      {/* grid lines */}
      {gridYVals.map(v => (
        <line key={v} x1={pad} x2={vbW - pad} y1={yScale(v)} y2={yScale(v)} stroke={dark ? 'rgba(255,255,255,0.12)' : 'rgba(0,0,0,0.08)'} strokeWidth="1" vectorEffect="non-scaling-stroke" />
      ))}
      {/* polyline */}
      <path d={path} fill="none" stroke={dark ? 'rgba(255,255,255,0.5)' : 'rgba(0,0,0,0.4)'} strokeWidth="2" strokeLinecap="round" vectorEffect="non-scaling-stroke" />
      {/* points */}
      {points.map(([x,y], i) => (
        <g key={i}>
          <circle cx={x} cy={y} r="4" fill={scoreColor(scores[i])} />
        </g>
      ))}
      {/* y-axis labels (right side) */}
      {[20,40,60,80,100].map(v => (
        <text key={v} x={vbW - pad + 6} y={yScale(v) + 4} fontSize="10" fill={dark ? 'rgba(255,255,255,0.7)' : 'rgba(0,0,0,0.6)'}>{v}</text>
      ))}
      {/* x-axis labels (bottom) – show every date */}
      {data.map((d, i) => {
        const dateObj = new Date(d.date);
        const label = isNaN(dateObj) ? d.date : `${dateObj.getMonth()+1}/${dateObj.getDate()}`;
        const x = points[i][0];
        return (
          <text key={i} x={x} y={vbH - 4} fontSize="10" textAnchor="middle" fill={dark ? 'rgba(255,255,255,0.7)' : 'rgba(0,0,0,0.6)'}>{label}</text>
        );
      })}
    </svg>
  );
};

export default function SleepReportCard({
  isDark,
  textPrimary,
  textSecondary,
  onGo,
  onBack
}) {
  // Keep local state so card updates after prefetch completes
  const [sleep, setSleep] = useState(null);

  // 1) Initial read from sessionStorage (fast) + 2) prefetch latest then refresh state
  useEffect(() => {
    // initial read
    try {
      if (typeof window !== 'undefined' && window.sessionStorage) {
        const raw = window.sessionStorage.getItem('sleepReport');
        if (raw) {
          const json = JSON.parse(raw);
          if (json && typeof json === 'object') setSleep(json);
        }
      }
    } catch (_) {}

    // prefetch on dashboard entry, then update state from storage
    (async () => {
      try {
        await prefetchTodaySleep();
        if (typeof window !== 'undefined' && window.sessionStorage) {
          const raw2 = window.sessionStorage.getItem('sleepReport');
          if (raw2) {
            const json2 = JSON.parse(raw2);
            if (json2 && typeof json2 === 'object') setSleep(json2);
          }
        }
      } catch (_) {}
    })();
  }, []);

  const sleepData = sleep || mockSleep;
  // total duration: prefer API minutes, fallback to ISO diff
  const totalMin = Number.isFinite(sleepData?.total_sleep_duration_minutes)
    ? sleepData.total_sleep_duration_minutes
    : diffMinutesISO(sleepData?.sleep_time, sleepData?.wake_time);
  const totalH = Math.floor(totalMin / 60);
  const totalM = totalMin % 60;

  // --- Sleep factor badges (derived from incoming API) ---
  // 1) 수면 시간: 7~9h 우선, 그 외 점수 기준: >80 좋음, >50 보통, 그 외 주의
  const durationScore = Number(sleepData?.sleep_score);
  const isGoodDuration = totalMin >= 420 && totalMin <= 540;
  const durationRating = isGoodDuration
    ? 'good'
    : (Number.isFinite(durationScore)
        ? (durationScore > 80 ? 'good' : (durationScore > 50 ? 'normal' : 'bad'))
        : 'normal');

  // 2) 뒤척임: rustle.score 우선 → 없으면 총 횟수 기준
  const rustleCount = Number(sleepData?.rustle?.total_count);
  const tossCount = Number.isFinite(rustleCount)
    ? rustleCount
    : (Array.isArray(sleepData?.toss_and_turn_times) ? sleepData.toss_and_turn_times.length : 0);
  const tossScore = Number(sleepData?.rustle?.score);
  const tossRating = toneByScore(tossScore) || (tossCount <= 2 ? 'good' : (tossCount <= 5 ? 'normal' : 'bad'));

  // 3) 호흡: breathing.score 우선 → 없으면 평균 bpm(12~20 정상)
  const avgBpm = Number(sleepData?.breathing?.average_bpm);
  const respScore = Number(sleepData?.breathing?.score);
  const respirationRating = toneByScore(respScore) || (Number.isFinite(avgBpm)
    ? (avgBpm >= 12 && avgBpm <= 20 ? 'good' : 'bad')
    : 'normal');

  const factorBadges = useMemo(() => ([
    {title: '수면 시간', rating: durationRating},
    {title: '뒤척임',   rating: tossRating},
    {title: '평균 호흡', rating: respirationRating},
  ]), [durationRating, tossRating, respirationRating]);

  const history = useMemo(() => {
    const wp = Array.isArray(sleepData?.weekly_pattern) ? sleepData.weekly_pattern : null;
    if (wp && wp.length) {
      return wp.map(({date, score}) => ({
        date,
        score: Number(score) || 0
      }));
    }
    return mockSleepHistory;
  }, [sleepData]);
  const todayScore = Number(
    sleepData?.total_quality_score ?? sleepData?.sleep_score ?? 0
  );
  const todayColor = scoreColor(todayScore);

  const todayTone = toneByScore(todayScore) || 'normal';
  const headerRowStyle = { display:'flex', alignItems:'center', justifyContent:'space-between', width:'100%' };
  const badgeStyle = {
    display:'inline-flex', alignItems:'center', gap:8,
    padding:'4px 10px', borderRadius:999,
    backgroundColor: toneColor[todayTone].bg,
    border: `1px solid ${toneColor[todayTone].border}`,
    color: toneColor[todayTone].fg, fontWeight:800, fontSize:12
  };
  const dotStyle = { width:10, height:10, borderRadius:'50%', background: toneColor[todayTone].fg };
  const barWrap = { height:6, width:'100%', borderRadius:999, background:'rgba(0,0,0,0.06)', overflow:'hidden', marginTop:6, marginBottom:2 };
  const barFill = { height:'100%', width: `${Math.max(0, Math.min(100, todayScore||0))}%`, background: toneColor[todayTone].bar };

  return (
    <Column className={isDark ? 'card card--dark' : 'card card--light'} style={{gap: 10, padding: '16px'}}>
      <Row style={{justifyContent: 'space-between', alignItems: 'center'}}>
        <Row style={{alignItems: 'center', gap: 8}}>
          <AccentDot isDark={isDark} />
          <Heading size="large" style={{color: textPrimary, fontSize: `${TYPE.h2}px`, lineHeight: `${LH.tight}em`, fontWeight: 800}}>
            수면 리포트
          </Heading>
        </Row>
        <GhostButton isDark={isDark} onClick={async () => { await prefetchTodaySleep(); onGo && onGo(); }}>자세히</GhostButton>
      </Row>

      <Row style={{gap: 12, alignItems: 'center', flexWrap: 'wrap'}}>
        <Column style={{gap: 8, alignItems: 'center', flex: '0 0 220px', maxWidth: 240}}>
          <Row style={{alignItems: 'center', gap: 8}}>
            <Heading size="small" style={{color: textPrimary, fontSize: `${TYPE.body}px`, fontWeight: 700, margin: 0, lineHeight: '1.15em'}}>
              {(() => { const d = new Date(); const y = d.getFullYear(); const m = String(d.getMonth()+1).padStart(2,'0'); const day = String(d.getDate()).padStart(2,'0'); return `${y}. ${m}. ${day}`; })()}
            </Heading>
          </Row>
          <div style={{width:'100%'}}>
            <div style={{display:'flex', alignItems:'center', justifyContent:'center', gap:8}}>
              <span style={badgeStyle}>
                <span style={dotStyle} />
                <span>{todayScore}점 · {toneLabel[todayTone]}</span>
              </span>
            </div>
          </div>
          <div style={{display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6, marginTop: 6}}>
            {factorBadges.map(({title, rating}) => (
              <RatingBadge key={title} title={title} rating={rating} />
            ))}
          </div>
        </Column>

        <div
          style={{
            flex: '1 0 640px', minWidth: 640, height: 180, position: 'relative', borderRadius: 12,
            background: isDark ? '#1b1b1b' : '#ffffff',
            outline: isDark
              ? `1px solid ${LG_BRAND.borderDark}`
              : `1px solid ${LG_BRAND.borderLight}`,
            overflow: 'visible'
          }}
        >
          <SleepScoreChart dark={isDark} data={history} />
        </div>

      </Row>
    </Column>
  );
}