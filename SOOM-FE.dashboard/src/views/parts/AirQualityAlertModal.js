/* global localStorage */
import React, { useEffect, useState } from 'react';

/**
 * AirQualityAlertModal
 * Displays a warning modal when AQI (air_quality) is above threshold.
 * Can be dismissed or snoozed for a duration (default: 30 minutes).
 *
 * Props:
 *  - aqi (number): current AQI value
 *  - threshold (number): alert trigger AQI (default 301)
 *  - isDark (boolean): dark mode toggle for styling
 */
export default function AirQualityAlertModal({ aqi, threshold = 301, isDark = false }) {
  const [show, setShow] = useState(false);

  const SNOOZE_KEY = 'AIR_ALERT_SNOOZE_UNTIL';
  const SNOOZE_MIN = 30; // minutes

  useEffect(() => {
    const n = Number(aqi);
    if (!Number.isFinite(n)) return;

    const now = Date.now();
    const snoozeUntil = Number(localStorage.getItem(SNOOZE_KEY) || 0);

    if (n >= threshold && now >= snoozeUntil) {
      setShow(true);
    } else if (n < threshold && show) {
      setShow(false);
    }
  }, [aqi, threshold]);

  const dismiss = () => {
    try {
      const until = Date.now() + SNOOZE_MIN * 60 * 1000;
      localStorage.setItem(SNOOZE_KEY, String(until));
    } catch (_) {}
    setShow(false);
  };

  if (!show) return null;

  return (
    <div
      style={{
        position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)',
        display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 9999,
        backdropFilter: 'blur(6px)'
      }}
    >
      <div
        style={{
          width: 'min(780px, 58vw)',
          background: isDark ? 'rgba(30,30,30,0.95)' : '#fff',
          color: isDark ? '#fff' : '#222',
          borderRadius: '20px',
          boxShadow: '0 8px 40px rgba(0,0,0,0.25)',
          padding: '48px 48px 32px',
          fontFamily: 'Pretendard, sans-serif',
          animation: 'fadeIn 0.25s ease-out'
        }}
      >
        <div style={{display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:18}}>
          <h3 style={{margin:0, fontSize:'clamp(28px, 1.6vw, 40px)', fontWeight:700}}>⚠️ 공기질 경보</h3>
          <button
            onClick={() => setShow(false)}
            style={{border:'none', background:'transparent', color:isDark?'#ccc':'#999', fontSize:14, cursor:'pointer'}}
          >닫기</button>
        </div>

        <div style={{marginTop:8, marginBottom:16}}>
          <p style={{margin:0, fontSize:'clamp(24px, 1.5vw, 32px)', fontWeight:500, lineHeight:1.7}}>
            현재 실내 공기질이 <b style={{color:'#e53935', fontWeight:700}}>AQI {aqi}</b> 수준으로 상당히 나쁩니다.
          </p>
          <p style={{marginTop:12, fontSize:'clamp(20px, 1.3vw, 26px)', color:isDark?'#ddd':'#555', lineHeight:1.7}}>
            실내 공기질이 좋지 않습니다.<br />
            잠시 창문을 열어 환기시키고, 공기청정기를 가동하세요.<br />
            가스밸브나 냄새의 원인이 될 수 있는 요소가 없는지도 점검하세요.<br />
            민감군은 실내 오염원으로부터 떨어져 휴식을 취하는 것을 권장합니다.
          </p>
        </div>

        <div style={{display:'flex', gap:10, justifyContent:'flex-end'}}>
          <button
            onClick={() => setShow(false)}
            style={{
              border:'none', borderRadius:8, padding:'14px 24px', cursor:'pointer',
              background:'#e53935', color:'#fff', fontWeight:700,
              fontSize:'clamp(16px, 1vw, 20px)'
            }}
          >확인</button>
        </div>
      </div>
    </div>
  );
}