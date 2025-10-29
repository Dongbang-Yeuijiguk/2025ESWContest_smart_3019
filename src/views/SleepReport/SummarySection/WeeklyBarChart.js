import React, {useContext} from 'react';
import { SleepDataContext } from '../../SleepReport';

// ---- Helpers ----
const pad2 = (n) => String(n).padStart(2, '0');

function parseHM(hm) {
  // Accept 'H:MM', 'HH:MM', and map '24:00' to '00:00' next day
  let [hs, ms] = hm.split(':');
  let h = Number(hs);
  let m = Number(ms);
  if (Number.isNaN(h) || Number.isNaN(m)) return 0;
  if (h === 24 && m === 0) h = 0;               // 24:00 -> 00:00
  h = ((h % 24) + 24) % 24;                     // wrap hour into 0..23
  m = clamp(m, 0, 59);                          // minute clamp
  return h * 60 + m;
}
function labelHM(totalMin) {
  const h = Math.floor(totalMin / 60) % 24;
  const m = totalMin % 60;
  const isAM = h < 12;
  const h12 = h % 12 === 0 ? 12 : h % 12;
  return `${h12}:${pad2(m)} ${isAM ? '오전' : '오후'}`;
}
function minutesBetween(bedMin, wakeMin) {
  let span = wakeMin - bedMin;
  if (span <= 0) span += 24 * 60;
  return span;
}
function clamp(v, a, b) { return Math.max(a, Math.min(b, v)); }
function scoreColor(score){
  if (score >= 80) return '#1DB954'; // good
  if (score >= 70) return '#FFB020'; // warn
  return '#FF4D4D';                  // bad
}
function normalizeFromApi(weekly) {
  if (!Array.isArray(weekly)) return null;
  try {
    return weekly.map(d => {
      const date = new Date(d.date);
      const start = d.sleep_start ?? d.start; // API or fallback
      const end   = d.sleep_end   ?? d.end;
      const score = Number(d.score ?? 0);
      return {date, start, end, score};
    }).filter(w => w.date instanceof Date && !isNaN(w.date));
  } catch (e) {
    return null;
  }
}

// ---- Dummy data (replace with API data later) ----
const DEFAULT_BEDTIME = '23:00';
const DEFAULT_WAKETIME = '07:00';

// Generate varied wake times and durations
const DUMMY_WEEK = (() => {
  const today = new Date();
  const out = [];
  const scoreChoices = [86, 72, 90, 78, 83, 68, 92];
  for (let i = 6; i >= 0; i--) {
    const d = new Date(today);
    d.setDate(today.getDate() - (6 - i));
    const bedChoices = ['22:50','23:10','23:30','02:20','23:40','00:00','23:00'];
    const wakeChoices = ['06:00','06:40','07:10','07:30','08:10','05:50','07:50'];
    out.push({
      date: d,
      start: bedChoices[i],
      end: wakeChoices[i],
      score: scoreChoices[i]
    });
  }
  return out;
})();

export default function WeeklyBarChart({
  bedTime = DEFAULT_BEDTIME,
  wakeTime = DEFAULT_WAKETIME,
  week = DUMMY_WEEK,
  width = 640,
  rowHeight = 24,
  gap = 6,
  data = [],            // ← API weekly_pattern
  isDark = false        // ← theme
}) {
  // Theme palette
  const colors = {
    surface:    isDark ? '#1b1b1b' : '#fff',
    text:       isDark ? '#E5E7EB' : '#111',
    gridMajor:  isDark ? '#2f3236' : '#D0D0D0',
    gridMinor:  isDark ? '#232528' : '#EFEFEF',
    frameFill:  isDark ? '#151619' : '#FAFAFA',
    frameStroke:isDark ? '#2a2d31' : '#E5E5E5',
    dayLabel:   isDark ? '#AAB0B6' : '#555',
    axisLabel:  isDark ? '#AAB0B6' : '#666'
  };

  // Prefer API data (prop) > context > dummy week
  const ctx = useContext(SleepDataContext);
  const ctxWeek = normalizeFromApi(ctx?.remote?.weekly_pattern || ctx?.data?.weekly_pattern);
  const apiWeek = normalizeFromApi(data);
  const sourceWeek = (apiWeek && apiWeek.length > 0)
    ? apiWeek
    : ((ctxWeek && ctxWeek.length > 0) ? ctxWeek : week);

  const bedMin = parseHM(bedTime);
  const wakeMin = parseHM(wakeTime);
  const chartStartMin = 22 * 60; // 22:00 고정 시작
  const capEndMin = 9 * 60;      // 09:00 고정 종료(최소)
  const domainWake = minutesBetween(chartStartMin, wakeMin);
  const domainCap  = minutesBetween(chartStartMin, capEndMin);
  const domain = Math.max(domainWake, domainCap);

  const height = sourceWeek.length * rowHeight + (sourceWeek.length - 1) * gap + 70;
  const chartX = 52;                 // left padding for day labels
  const scoreColW = 48;              // right column width for score
  const chartW = width - chartX - scoreColW - 16; // reserve space

  const steps = Math.ceil(domain / 60) + 1;
  const hourTicks = Array.from({length: steps}, (_, k) => (chartStartMin + k * 60) % (24 * 60));

  const xFromClock = (clockMin) => {
    let delta = clockMin - chartStartMin;
    if (delta < 0) delta += 24 * 60;
    const ratio = clamp(delta / domain, 0, 1);
    return chartX + ratio * chartW;
  };

  const labelStart = labelHM(chartStartMin);
  const labelEnd = labelHM((chartStartMin + domain) % (24*60));

  // Sort by actual calendar date (oldest → newest)
  const sortedWeek = [...sourceWeek].sort((a,b) => a.date - b.date);

  return (
    <div style={{
      background: colors.surface, borderRadius: 12, padding: 12, color: colors.text,
      boxShadow: isDark ? '0 1px 4px rgba(0,0,0,0.4)' : '0 1px 4px rgba(0,0,0,0.05)'
    }}>
      <svg width={width} height={height} role="img" aria-label="주간 수면 시간 막대 그래프">
        <rect x={chartX} y={0} width={chartW} height={height-40} fill={colors.frameFill} stroke={colors.frameStroke} strokeWidth={1} />

        {/* vertical grid lines */}
        {hourTicks.map((t, idx) => {
          const x = xFromClock(t % (24*60));
          const major = (t % (24*60)) % 180 === 0;
          return (
            <line key={idx} x1={x} x2={x} y1={0} y2={height-40} stroke={major ? colors.gridMajor : colors.gridMinor} strokeWidth={major ? 1 : 0.8} />
          );
        })}

        {/* day labels (MM/DD) */}
        {sortedWeek.map((w, i) => {
          const y = i * (rowHeight + gap) + 10;
          const mm = w.date.getMonth() + 1;
          const dd = w.date.getDate();
          const label = `${mm}/${dd}`;
          return (
            <text key={`lab-${i}`} x={chartX-12} y={y + rowHeight/2 + 4} fill={colors.dayLabel} fontSize={12} textAnchor="end">{label}</text>
          );
        })}

        {/* bars */}
        {sortedWeek.map((w, i) => {
          const y = i * (rowHeight + gap) + 8;
          const s = parseHM(w.start);
          const e = parseHM(w.end);
          const sx = xFromClock(s);
          const ex = xFromClock(e);
          let x1 = sx, x2 = ex;
          if (ex <= sx) x2 = chartX + chartW;
          x1 = clamp(x1, chartX, chartX + chartW);
          x2 = clamp(x2, chartX, chartX + chartW);
          const wpx = Math.max(10, x2 - x1);
          const r = Math.min(6, rowHeight/3);

          const barH = Math.max(8, rowHeight - 12);
          const duration = minutesBetween(s, e);
          const isGood = duration >= 420 && duration <= 540;
          const color = isGood ? '#1DB954' : '#FF4D4D';

          return (
            <g key={`bar-${i}`}>
              <rect x={x1} y={y} width={wpx} height={barH} rx={r} ry={r} fill={color} opacity={0.9} />
            </g>
          );
        })}

        {/* score pills column */}
        {sortedWeek.map((w, i) => {
          const y = i * (rowHeight + gap) + 6;
          const pillW = 38, pillH = 18, r = 9;
          const cx = chartX + chartW + (scoreColW/2);
          const px = cx - pillW/2;
          const py = y + (rowHeight-6)/2 - pillH/2;
          const fill = scoreColor(w.score ?? 0);
          const label = String(w.score ?? '');
          return (
            <g key={`score-${i}`}>
              <rect x={px} y={py} width={pillW} height={pillH} rx={r} ry={r} fill={fill} opacity={0.95} />
              <text x={cx} y={py + pillH/2 + 5} fill="#fff" fontSize={10} fontWeight={800} textAnchor="middle">{label}</text>
            </g>
          );
        })}

        {/* bottom axis labels */}
        <text x={chartX} y={height-12} fill={colors.axisLabel} fontSize={12} textAnchor="start">{labelStart}</text>
        <text x={chartX + chartW} y={height-12} fill={colors.axisLabel} fontSize={12} textAnchor="end">{labelEnd}</text>
      </svg>
    </div>
  );
}