// src/views/SleepReport/index.js
import React, {useState, useEffect, createContext} from 'react';
export const SleepDataContext = createContext(null);
import BodyText from '@enact/sandstone/BodyText';
import Button from '@enact/sandstone/Button';
import {Column, Row} from '@enact/ui/Layout';

import WeeklyBarChart from './SummarySection/WeeklyBarChart';
import SleepComment from './SummarySection/SleepComment';
import FactorCards from './Card/FactorCard';

const LG_BRAND = {
  red: '#A50034',
  pinkTint: 'rgba(165,0,52,0.06)',
  pinkTintStrong: 'rgba(165,0,52,0.12)',
  borderLight: 'rgba(0,0,0,0.08)',
  borderDark: 'rgba(255,255,255,0.12)',
  neutralBg: '#F7F8FA',
  surface: '#FFFFFF',
  shadowSoft: '0 6px 24px rgba(0,0,0,0.06)',
  shadowHover: '0 10px 28px rgba(0,0,0,0.10)'
};

// ---- Sleep API helper ----
const SLEEP_REPORT_ENDPOINT = process.env.REACT_APP_SLEEP_REPORT_ENDPOINT || '/api/v1/dashboard/sleep/report';
async function fetchSleepReport(dateISO){
  const date = dateISO || new Date().toISOString().slice(0,10);
  const url = `${SLEEP_REPORT_ENDPOINT}/${encodeURIComponent(date)}`;
  const res = await fetch(url, {method:'GET'});
  if(!res.ok) throw new Error(`HTTP ${res.status}`);
  return await res.json();
}

// Full-screen canvas that scales a fixed 1024×600 layout to the viewport
const Page = ({children, isDark=false}) => {
  const [scale, setScale] = useState(1);
  useEffect(() => {
    const onResize = () => {
      const vw = Math.max(1, window.innerWidth || document.documentElement.clientWidth);
      const vh = Math.max(1, window.innerHeight || document.documentElement.clientHeight);
      const s = Math.min(vw / 1024, vh / 600);
      setScale(s);
    };
    onResize();
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, []);

  return (
    <div style={{
      width: '100vw',
      height: '100vh',
      margin: 0,
      padding: 0,
      overflow: 'hidden',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      background: isDark ? '#0f1012' : LG_BRAND.neutralBg
    }}>
      <div style={{
        width: 1024,
        height: 600,
        transform: `scale(${scale})`,
        transformOrigin: 'center center',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'flex-start',
        background: isDark ? 'linear-gradient(180deg, #121316, rgba(165,0,52,0.10))' : `linear-gradient(180deg, #fafbfd, ${LG_BRAND.pinkTint})`,
        borderRadius: 0,
        overflow: 'hidden'
      }}>
        <div style={{
          width: '100%',
          height: '100%',
          padding: '6px 10px 10px',
          boxSizing: 'border-box'
        }}>
          {children}
        </div>
      </div>
    </div>
  );
};

const Card = ({children, style, isDark=false}) => (
  <div style={{
    borderRadius: 12,
    background: isDark ? '#1b1b1b' : LG_BRAND.surface,
    boxShadow: isDark ? '0 3px 12px rgba(0,0,0,0.5)' : '0 3px 10px rgba(0,0,0,0.06)',
    outline: `1px solid ${isDark ? LG_BRAND.borderDark : LG_BRAND.borderLight}`,
    padding: 12,
    transition: 'box-shadow 120ms ease, transform 120ms ease',
    willChange: 'transform',
    ...style
  }}
  onMouseEnter={e => { e.currentTarget.style.boxShadow = isDark ? '0 10px 28px rgba(0,0,0,0.6)' : LG_BRAND.shadowHover; e.currentTarget.style.transform = 'translateY(-2px)'; }}
  onMouseLeave={e => { e.currentTarget.style.boxShadow = isDark ? '0 3px 10px rgba(0,0,0,0.5)' : '0 3px 10px rgba(0,0,0,0.06)'; e.currentTarget.style.transform = 'none'; }}
  >{children}</div>
);

// Chip and StatusRow components
const Chip = ({label, tone='neutral', isDark=false}) => {
  const map = {
    good: {bg:'rgba(16,160,80,0.12)', color:'#0E6A3A', bd:'1px solid rgba(16,160,80,0.35)'},
    warn: {bg:'rgba(250,170,20,0.12)', color:'#7A4A00', bd:'1px solid rgba(250,170,20,0.45)'},
    bad:  {bg: LG_BRAND.pinkTint, color: LG_BRAND.red, bd:`1px solid ${LG_BRAND.red}`},
    neutral: {bg: isDark ? 'rgba(255,255,255,0.10)' : 'rgba(0,0,0,0.06)', color: isDark ? '#ddd' : '#444', bd: isDark ? '1px solid rgba(255,255,255,0.16)' : '1px solid rgba(0,0,0,0.10)'}
  };
  const s = map[tone] || map.neutral;
  return (
    <span style={{
      display:'inline-flex', alignItems:'center',
      padding:'4px 8px', borderRadius:999,
      background:s.bg, color:s.color, border:s.bd,
      fontSize:12, fontWeight:800, letterSpacing:0.1
    }}>{label}</span>
  );
};

const StatusRow = ({items=[], isDark=false}) => (
  <Row style={{gap: 6, marginTop: 6, flexWrap:'wrap'}}>
    {items.map((it, idx) => <Chip key={idx} label={it.label} tone={it.tone} isDark={isDark} />)}
  </Row>
);

// ---- Helpers & mock (remove when API connects) ----
const pad2 = (n) => String(n).padStart(2, '0');
const fmtDate = (iso) => {
  const d = new Date(iso);
  return `${d.getFullYear()}.${pad2(d.getMonth()+1)}.${pad2(d.getDate())}`;
};
const fmtHm = (iso) => {
  const d = new Date(iso);
  return `${pad2(d.getHours())}:${pad2(d.getMinutes())}`;
};

const start = new Date('2025-09-13T23:00:00');
const end   = new Date('2025-09-14T06:00:00');
const durationMin = Math.max(0, Math.round((end - start) / 60000));

// Generate 10-min bucket series length from start/end (e.g., 7h -> 42 buckets)
const buckets = Math.max(1, Math.round(durationMin / 10));
const mkSeries = (base=66, amp=4) => Array.from({length: buckets}, (_, i) => Math.round(base + amp * Math.sin(i/3)));
const bpm_average = mkSeries(66, 4);
const mockSleep = {
  date: '2025-09-14',
  total_sleep_duration_minutes: durationMin,
  sleep_start_time: start.toISOString(),
  sleep_end_time: end.toISOString(),
  sleep_score: 82,
  bpm_average,
  bpm_min: bpm_average.map(v => v - 6),
  bpm_max: bpm_average.map(v => v + 6),
  bpm_per_10min: bpm_average,
  toss_and_turn_times: [
    new Date(start.getTime() + 20 * 60000).toISOString(),
    new Date(start.getTime() + 160 * 60000).toISOString(),
  ],
};
// mock daily durations (minutes) for week/month ranges
const jitter = (min, delta=40) => Math.max(240, min + Math.round((Math.random()-0.5)*delta));
const genDurations = (n, base) => Array.from({length:n}, () => jitter(base, 80));
const weekDurations = genDurations(7, durationMin); // 7 days around current
const monthDurations = genDurations(30, durationMin); // 30 days around current

const avgMinutes = (arr) => Math.round(arr.reduce((a,b)=>a+b,0) / Math.max(1, arr.length));

const factors = {
  depth: {title:'수면 깊이', rating:'good', caption:'깊은 수면 비율', valueLabel:'32%', series: [6,10,14,18,22,18,14,10,6]},
  duration: {title:'수면 시간', rating:'bad', caption:'권장 7–9시간 대비', valueLabel: `${Math.floor(durationMin / 60)}h ${durationMin % 60}m`, progress: Math.min(100, Math.round((durationMin / (8*60)) * 100))},
  toss: {title:'뒤척임', rating:'warn', caption:'뒤척임 횟수', valueLabel: `${mockSleep.toss_and_turn_times.length}회`, series: [4,12,6,8,2,10,6,4,3,6]},
  respiration: {title:'호흡', rating:'good', caption:'분당 평균 호흡수', valueLabel:'14 bpm', series:[8,9,10,10,11,10,9,8,9]},
};

function SleepReport({onBack, isDark=false}) {
  // 1024×600 canvas inner content width = 1024 - padding(12*2) = 1000
  const CANVAS_W = 1024;
  const PADDING = 12; // matches Card padding
  const GUTTER = 8;   // Row gap
  const INNER_W = CANVAS_W - (PADDING * 2);
  const COL_W = Math.floor((INNER_W - GUTTER) / 2); // two columns within the card
  // Track today's date and update at midnight for subtitle
  const [today, setToday] = useState(new Date());
  useEffect(() => {
    // schedule an update at the next midnight so the label rolls over without reload
    const now = new Date();
    const nextMidnight = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1, 0, 0, 1);
    const timer = setTimeout(() => setToday(new Date()), nextMidnight - now);
    return () => clearTimeout(timer);
  }, [today]);
  console.log('SleepReport mounted');
  const [range, setRange] = useState('day');
  const [detailOpen, setDetailOpen] = useState(null); // 'depth' | 'duration' | ...
  const [durationRange, setDurationRange] = useState('day'); // 'day' | 'week' | 'month'

  // Remote data wiring (sessionStorage prefetch or live fetch in effect below)
  const [remote, setRemote] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Choose active data source (remote if available, else mock fallback)
  const data = remote || mockSleep;

  useEffect(() => {
    let ignore = false;
    async function run(){
      try{
        setLoading(true);
        setError(null);
        // read one-shot cache from sessionStorage if present
        const cached = (typeof window !== 'undefined' && window.sessionStorage) ? window.sessionStorage.getItem('sleepReport') : null;
        if(cached){
          const parsed = JSON.parse(cached);
          if(!ignore) setRemote(parsed);
          if (typeof window !== 'undefined' && window.sessionStorage) {
            window.sessionStorage.removeItem('sleepReport');
          }
        } else {
          const fresh = await fetchSleepReport();
          if(!ignore) setRemote(fresh);
        }
      } catch(e){
        if(!ignore) setError(e);
      } finally {
        if(!ignore) setLoading(false);
      }
    }
    run();
    return () => { ignore = true; };
  }, []);

  // Total minutes: prefer remote (wake - sleep) else mock value
  const total = (data?.sleep_time && data?.wake_time)
    ? Math.max(0, Math.round((new Date(data.wake_time) - new Date(data.sleep_time)) / 60000))
    : (data.total_sleep_duration_minutes || 0);
  const h = Math.floor(total / 60);
  const m = total % 60;
  const avgWeek = avgMinutes(weekDurations);
  const avgMonth = avgMinutes(monthDurations);

  // 진짜 오늘 날짜 보여주기 (KST 기준)
  const subtitleText = (() => {
    try {
      const parts = new Intl.DateTimeFormat('ko-KR', {
        timeZone: 'Asia/Seoul',
        year: 'numeric', month: '2-digit', day: '2-digit'
      }).formatToParts(today);
      const y = parts.find(p => p.type === 'year')?.value || String(today.getFullYear());
      const m = parts.find(p => p.type === 'month')?.value || pad2(today.getMonth()+1);
      const d = parts.find(p => p.type === 'day')?.value || pad2(today.getDate());
      return `${y}.${m}.${d}`;
    } catch (_) {
      return `${today.getFullYear()}.${pad2(today.getMonth()+1)}.${pad2(today.getDate())}`;
    }
  })();
  // Always embed within App's 1024x600 canvas; avoid double scaling
  const embedded = true;
  return (
    <SleepDataContext.Provider value={{data, remote, loading, error}}>
      <Column>
      {embedded ? (
        <Card isDark={isDark} style={{width: '100%', maxWidth: 1024, boxShadow: LG_BRAND.shadowSoft}}>
          {/* header row with back button and centered date */}
          <Row style={{justifyContent: 'center', alignItems: 'center', marginTop: 8, marginBottom: 0}}>
            <div style={{position: 'absolute', left: 16, display: 'flex', alignItems: 'center', height: '100%'}}>
              <button
                onClick={onBack}
                aria-label="뒤로가기"
                title="뒤로가기"
                style={{
                  display:'inline-flex', alignItems:'center', justifyContent:'center',
                  width: 28, height: 28, borderRadius: 8,
                  background: 'transparent', border: `1.5px solid ${LG_BRAND.red}`,
                  color: LG_BRAND.red, fontSize: 16, fontWeight: 900, cursor:'pointer'
                }}
              >
                ←
              </button>
            </div>
          </Row>
          {/* <RangeTabs range={range} onChange={setRange} /> */}

          <div style={{marginTop: 4, marginBottom: 4}}>
            <Row style={{gap: 8, alignItems: 'stretch'}}>
              <div style={{flex: `0 0 ${COL_W}px`, maxWidth: COL_W}}>
                <WeeklyBarChart bedTime="23:00" wakeTime="06:00" width={COL_W} rowHeight={22} gap={4} isDark={isDark} />
              </div>
              <SleepComment
                style={{flex: 1}}
                durationMin={total}
                depthPercent={parseInt((factors.depth.valueLabel||'0').replace('%',''), 10)}
                tossCount={data?.rustle?.total_count ?? (mockSleep.toss_and_turn_times?.length || 0)}
                respirationBpm={Math.round(data?.breathing?.average_bpm ?? parseInt((factors.respiration.valueLabel||'0').replace(' bpm',''), 10))}
                isDark={isDark}
              />
            </Row>
          </div>

          <div style={{marginTop: 10}}>
            <FactorCards isDark={isDark} />
          </div>
        </Card>
      ) : (
        <Page isDark={isDark}>
          <Card isDark={isDark} style={{width: '100%', maxWidth: 1024, boxShadow: LG_BRAND.shadowSoft}}>
            {/* header row with back button and centered date */}
            <Row style={{justifyContent: 'center', alignItems: 'center', marginTop: 8, marginBottom: 0}}>
              <div style={{position: 'absolute', left: 16, display: 'flex', alignItems: 'center', height: '100%'}}>
                <button
                  onClick={onBack}
                  aria-label="뒤로가기"
                  title="뒤로가기"
                  style={{
                    display:'inline-flex', alignItems:'center', justifyContent:'center',
                    width: 28, height: 28, borderRadius: 8,
                    background: 'transparent', border: `1.5px solid ${LG_BRAND.red}`,
                    color: LG_BRAND.red, fontSize: 16, fontWeight: 900, cursor:'pointer'
                  }}
                >
                  ←
                </button>
              </div>
              <BodyText style={{fontSize: 18, fontWeight: 800, color: isDark ? '#F3F4F6' : '#222', margin: '0 auto'}}>{subtitleText}</BodyText>
              {loading && <span style={{fontSize:10, opacity:0.7, marginLeft:6}}>불러오는 중…</span>}
              {error && <span style={{fontSize:10, color:'#ef4444', marginLeft:6}}>가져오기 실패</span>}
            </Row>
            {/* <RangeTabs range={range} onChange={setRange} /> */}

            <div style={{marginTop: 4, marginBottom: 4}}>
            <Row style={{gap: 8, alignItems: 'stretch'}}>
              <div style={{flex: `0 0 ${COL_W}px`, maxWidth: COL_W}}>
                <WeeklyBarChart
                  data={remote?.weekly_pattern}
                  bedTime={fmtHm(remote?.sleep_time || data.sleep_start_time)}
                  wakeTime={fmtHm(remote?.wake_time || data.sleep_end_time)}
                  width={COL_W}
                  rowHeight={22}
                  gap={4}
                  isDark={isDark}
                />              
                </div>
              <SleepComment
                style={{flex: 1}}
                durationMin={total}
                depthPercent={parseInt((factors.depth.valueLabel||'0').replace('%',''), 10)}
                tossCount={data?.rustle?.total_count ?? (mockSleep.toss_and_turn_times?.length || 0)}
                respirationBpm={Math.round(data?.breathing?.average_bpm ?? parseInt((factors.respiration.valueLabel||'0').replace(' bpm',''), 10))}
                isDark={isDark}
              />
            </Row>
            </div>

            <div style={{marginTop: 10}}>
              <FactorCards isDark={isDark} />
            </div>
          </Card>
        </Page>
      )}
      </Column>
    </SleepDataContext.Provider>
  );
}

export default SleepReport;