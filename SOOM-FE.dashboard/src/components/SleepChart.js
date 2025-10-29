// src/components/SleepChart.js
import React from 'react';

// Local brand token (avoid external imports)
const LG_BRAND = { red: '#A50034' };

function SleepChart({dark = false, data}) {
  // --- derive bucket count from time or array length ---
  const avgsRaw = data?.bpm_average || [];
  const minsRaw = data?.bpm_min || [];
  const maxsRaw = data?.bpm_max || [];

  const hasTime = !!(data?.sleep_start_time && data?.sleep_end_time);
  const startMs = hasTime ? new Date(data.sleep_start_time).getTime() : null;
  const endMs   = hasTime ? new Date(data.sleep_end_time).getTime()   : null;
  const durationMs = hasTime ? Math.max(0, endMs - startMs) : null;

  const bucketsFromTime = hasTime ? Math.max(1, Math.round(durationMs / (10 * 60 * 1000))) : 0;
  const buckets = bucketsFromTime || (avgsRaw.length || minsRaw.length || maxsRaw.length || 0);

  // normalize to bucket count (linear interpolation)
  const lerp = (a, b, t) => a + (b - a) * t;
  const normalizeSeries = (src, targetLen) => {
    if (!Array.isArray(src) || targetLen <= 0) return [];
    if (src.length === targetLen) return src.slice();
    if (src.length === 0) return Array.from({length: targetLen}, () => 0);
    if (targetLen === 1) return [Number(src[0] ?? 0)];
    const out = new Array(targetLen);
    const last = src.length - 1;
    for (let i = 0; i < targetLen; i++) {
      const pos = (last * i) / (targetLen - 1);
      const lo = Math.floor(pos);
      const hi = Math.min(last, lo + 1);
      const t = pos - lo;
      const a = Number(src[lo] ?? 0);
      const b = Number(src[hi] ?? a);
      out[i] = Math.round(lerp(a, b, t));
    }
    return out;
  };

  const avgs = normalizeSeries(avgsRaw, buckets);
  const mins = normalizeSeries(minsRaw, buckets);
  const maxs = normalizeSeries(maxsRaw, buckets);

  // axes + colors
  const stroke = LG_BRAND.red;
  const avgStroke = stroke;
  const rangeColor = dark ? 'rgba(255,255,255,0.25)' : 'rgba(0,0,0,0.25)';
  const axisColor  = dark ? 'rgba(255,255,255,0.18)' : 'rgba(0,0,0,0.12)';

  const width = 600;
  const height = 200;
  const padL = 28, padR = 10, padT = 10, padB = 28;
  const plotW = width - padL - padR;
  const plotH = height - padT - padB;

  const gMin = Math.min(...mins, ...avgs, ...maxs);
  const gMax = Math.max(...mins, ...avgs, ...maxs);
  const yMin = isFinite(gMin) ? gMin - 5 : 40;
  const yMax = isFinite(gMax) ? gMax + 5 : 120;
  const yScale = (v) => padT + (1 - (v - yMin) / (yMax - yMin)) * plotH;

  const xStep = buckets > 1 ? plotW / (buckets - 1) : plotW;
  const xAt = (i) => padL + i * xStep;

  const avgPath = avgs.map((v, i) => `${i === 0 ? 'M' : 'L'}${xAt(i)},${yScale(v)}`).join(' ');

  // Toss & turn markers
  const ttX = (() => {
    if (!hasTime || buckets < 2) return [];
    const bucketMs = 10 * 60 * 1000;
    return (data.toss_and_turn_times || []).map(ts => {
      const t = new Date(ts).getTime();
      const idx = Math.max(0, Math.min(buckets - 1, Math.round((t - startMs) / bucketMs)));
      return xAt(idx);
    });
  })();

  return (
    <svg width="100%" height="100%" viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none">
      <defs>
        <filter id="avgShadow" x="-10%" y="-20%" width="120%" height="140%">
          <feDropShadow dx="0" dy="2" stdDeviation="2" floodColor={avgStroke} floodOpacity="0.25" />
        </filter>
      </defs>

      {/* axes */}
      <g stroke={axisColor} strokeWidth="1">
        <line x1={padL} y1={height - padB} x2={width - padR} y2={height - padB} />
        <line x1={padL} y1={padT} x2={padL} y2={height - padB} />
      </g>

      {/* min-max ranges */}
      <g stroke={rangeColor} strokeWidth="6" strokeLinecap="round">
        {mins.map((mn, i) => (
          <line key={`r-${i}`} x1={xAt(i)} x2={xAt(i)} y1={yScale(mn)} y2={yScale(maxs[i] ?? mn)} />
        ))}
      </g>

      {/* average line */}
      <path d={avgPath} fill="none" stroke={avgStroke} strokeWidth="3" strokeLinejoin="round" strokeLinecap="round" filter="url(#avgShadow)" />

      {/* toss & turn markers */}
      <g>
        {ttX.map((x, i) => (
          <line key={`tt-${i}`} x1={x} x2={x} y1={padT} y2={height - padB} stroke={dark ? 'rgba(165,0,52,0.35)' : 'rgba(165,0,52,0.45)'} strokeDasharray="4 4" />
        ))}
      </g>
    </svg>
  );
}

export default SleepChart;