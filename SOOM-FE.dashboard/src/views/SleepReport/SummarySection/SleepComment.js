import React, {useContext} from 'react';
import { SleepDataContext } from '../../SleepReport';

// 코멘트 생성 규칙 기반 요약 박스
// props:
//  - durationMin: 총 수면 분
//  - depthPercent: 깊은 수면 비율(%)
//  - tossCount: 뒤척임 횟수
//  - respirationBpm: 분당 호흡수
//  - consistencyMin: 취침/기상 변동(분, +면 지연, -면 앞당김)
//  - style: 추가 스타일 병합용(optional)
export default function SleepComment({
  durationMin = 0,
  depthPercent = 0,
  tossCount = 0,
  respirationBpm = 0,
  consistencyMin = 0,
  style = {},
}) {
  // Context defaults if props are missing
  const ctx = useContext(SleepDataContext);
  const src = (ctx?.remote || ctx?.data) || {};

  const calcDiffMin = (sISO, eISO) => {
    if (!sISO || !eISO) return 0;
    const s = new Date(sISO).getTime();
    const e = new Date(eISO).getTime();
    if (!Number.isFinite(s) || !Number.isFinite(e)) return 0;
    return Math.max(0, Math.round((e - s) / 60000));
  };

  if (!durationMin || durationMin <= 0) {
    durationMin = calcDiffMin(src.sleep_time, src.wake_time);
  }
  if (!tossCount || tossCount < 0) {
    tossCount = Number(src?.rustle?.total_count ?? 0);
  }
  if (!respirationBpm || respirationBpm <= 0) {
    respirationBpm = Number(src?.breathing?.average_bpm ?? 0);
  }

  // recompute after fallback
  // ----- 오늘의 수면점수 헤더 -----
  const toneByScore = (s) => (Number.isFinite(s) ? (s >= 80 ? 'good' : (s >= 50 ? 'normal' : 'bad')) : 'normal');
  const toneLabel = {good:'좋음', normal:'보통', bad:'주의'};
  const toneColor = {
    good:   {fg:'#1B5E20', bg:'rgba(27,94,32,0.10)', bar:'#2E7D32', border:'rgba(27,94,32,0.35)'},
    normal: {fg:'#7A4A00', bg:'rgba(250,170,20,0.12)', bar:'#B26A00', border:'rgba(250,170,20,0.45)'},
    bad:    {fg:'#A50034', bg:'rgba(165,0,52,0.10)', bar:'#C2185B', border:'rgba(165,0,52,0.45)'}
  };

  // 전체 점수 우선: total_quality_score -> 없으면 sleep_score 사용
  const rawOverall = Number.isFinite(src?.total_quality_score) ? Math.round(src.total_quality_score)
                    : (Number.isFinite(src?.sleep_score) ? Math.round(src.sleep_score) : null);
  const overallTone = toneByScore(rawOverall);
  const h = Math.floor(durationMin / 60);
  const m = durationMin % 60;

  // ---- 규칙 ----
  const isDurationGood = durationMin >= 420 && durationMin <= 540; // 7~9h
  const hasDepth = Number.isFinite(depthPercent) && depthPercent > 0;

  const tossHigh = Number.isFinite(tossCount) ? tossCount >= 12 : false; // heuristic
  const tossLow  = Number.isFinite(tossCount) ? (tossCount > 0 && tossCount < 6) : false;

  const hasResp  = Number.isFinite(respirationBpm) && respirationBpm > 0;
  const respOut  = hasResp ? (respirationBpm < 12 || respirationBpm > 20) : false; // normal 12~20 bpm
  const respGood = hasResp ? (respirationBpm >= 12 && respirationBpm <= 20) : false;

  const inconsistent = Number.isFinite(consistencyMin) ? Math.abs(consistencyMin) > 60 : false; // > 1h shift
  const consistent   = Number.isFinite(consistencyMin) ? (Math.abs(consistencyMin) <= 30 && consistencyMin !== 0) : false;

  const title = `오늘 수면 시간은 ${h}시간 ${m}분이에요.`;

  const paragraphs = [];
  if (!isDurationGood) {
    if (durationMin < 420) {
      paragraphs.push('권장 수면 시간(7~9시간)보다 짧아요. 오늘은 취침 준비를 조금 더 일찍 시작해 보세요.');
    } else {
      paragraphs.push('권장 수면 시간(7~9시간)을 넘어섰어요. 지나치게 길어진 수면은 낮 피로감을 유발할 수 있어요.');
    }
  } else {
    paragraphs.push('권장 수면 시간 범위 안에서 잘 주무셨어요. 일정한 패턴을 유지하면 다음 날 컨디션이 더 좋아집니다.');
  }

  if (tossHigh) paragraphs.push('뒤척임이 잦았어요. 매트리스/베개 점검 또는 실내 온·습도(18~20°C, 40~60%) 조절을 권장합니다.');
  if (respOut) paragraphs.push('호흡수가 평소 범위를 벗어났어요. 감기 기운이나 코막힘 등의 영향이 있는지 확인해 보세요.');
  if (inconsistent) paragraphs.push('취침/기상 시간이 들쑥날쑥해요. 일정한 수면 리듬을 위해 ±30분 이내로 맞춰보세요.');

  // 긍정 피드백 (조건이 좋은 경우)
  if (tossLow) paragraphs.push('뒤척임이 적었어요. 적절한 실내 환경과 안정적인 컨디션이 유지되고 있어요.');
  if (respGood) paragraphs.push('호흡 리듬이 안정적이었어요. 수면 중 회복 효율이 좋았을 가능성이 높아요.');
  if (consistent) paragraphs.push('취침/기상 시간이 비교적 일정했어요. 꾸준함이 수면의 질을 가장 크게 높여줍니다.');

  const boxStyle = {
    background: '#fff',
    border: '1px solid rgba(0,0,0,0.08)',
    borderRadius: 10,
    padding: 10,
    boxShadow: '0 1px 4px rgba(0,0,0,0.04)',
    display: 'flex',
    flexDirection: 'column',
    justifyContent: 'center',
    ...style,
  };

  const titleStyle = { fontSize: 16, fontWeight: 900, color: '#111', marginBottom: 6 };
  const pStyle = { fontSize: 12, color: '#333', lineHeight: 1.5, margin: 0 };

  const headerRow = { display:'flex', alignItems:'center', justifyContent:'space-between', marginBottom:8 };
  const badgeStyle = {
    display:'inline-flex', alignItems:'center', gap:8,
    padding:'4px 10px', borderRadius:999,
    backgroundColor: toneColor[overallTone].bg,
    border: `1px solid ${toneColor[overallTone].border}`,
    color: toneColor[overallTone].fg, fontWeight:800, fontSize:12
  };
  const dotStyle = { width:10, height:10, borderRadius:'50%', background: toneColor[overallTone].fg };
  const barWrap = { height:6, width:'100%', borderRadius:999, background:'rgba(0,0,0,0.06)', overflow:'hidden', marginTop:6, marginBottom:2 };
  const barFill = { height:'100%', width: `${Math.max(0, Math.min(100, rawOverall||0))}%`, background: toneColor[overallTone].bar };

  return (
    <div style={boxStyle}>
      {rawOverall != null && (
        <div style={headerRow}>
          <div style={{fontSize:14, fontWeight:900, color:'#111'}}>오늘의 수면점수는</div>
          <div style={badgeStyle}>
            <span style={dotStyle} />
            <span>{rawOverall}점 · {toneLabel[overallTone]}</span>
          </div>
        </div>
      )}
      {rawOverall != null && (
        <div style={barWrap}><div style={barFill} /></div>
      )}
      <p style={{...pStyle, marginTop:5, marginBottom:5}}>{title}</p>
      {paragraphs.map((t, i) => (
        <p key={i} style={{...pStyle, marginTop: i === 0 ? 0 : 4}}>{t}</p>
      ))}
    </div>
  );
}