// 자동화 루틴 설정 모달
import BodyText from '@enact/sandstone/BodyText';
import Switch from '@enact/sandstone/Switch';
import {Row} from '@enact/ui/Layout';
import React, {useState} from 'react';

const TYPE = { h3: 16, body: 14, label: 12, tiny: 10 };
const LG_BRAND = {
  borderLight: 'rgba(0,0,0,0.08)',
  borderDark: 'rgba(255,255,255,0.12)'
};

// 간단 GhostButton (Dashboard와 유사 스타일)
const GhostButton = ({children, isDark, onClick, size = 'small'}) => {
  const accent = '#A50034';
  const text = isDark ? '#fff' : '#111';
  const hoverBg = isDark ? 'rgba(165,0,52,0.14)' : 'rgba(165,0,52,0.10)';
  const style = {
    display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
    padding: size==='small' ? '4px 8px' : '5px 10px',
    borderRadius: 999, border: `1px solid ${accent}`,
    color: text, background: 'transparent', fontWeight: 700, fontSize: 14,
    cursor: 'pointer', userSelect: 'none',
    boxShadow: isDark ? '0 1px 4px rgba(0,0,0,0.35)' : '0 1px 4px rgba(0,0,0,0.08)'
  };
  return (
    <div
      role="button"
      onClick={onClick}
      style={style}
      onMouseEnter={e => e.currentTarget.style.background = hoverBg}
      onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
    >{children}</div>
  );
};

// 간단 Stepper (길게 누르면 연속 증가/감소)
const Stepper = ({value, setValue, min, max, isDark, unit='℃', step = 1}) => {
  // hold timers per button
  let decTimeout, decInterval, incTimeout, incInterval;
  const initialDelay = 350;   // ms before repeat starts
  const repeatDelay  = 50;    // ms per repeat

  const dec = () => setValue(t => Math.max(min, (Number(t)||min) - step));
  const inc = () => setValue(t => Math.min(max, (Number(t)||min) + step));

  const startHoldDec = () => {
    // start repeating after initial delay
    decTimeout = setTimeout(() => {
      decInterval = setInterval(dec, repeatDelay);
    }, initialDelay);
  };
  const stopHoldDec = () => {
    clearTimeout(decTimeout); clearInterval(decInterval);
  };

  const startHoldInc = () => {
    incTimeout = setTimeout(() => {
      incInterval = setInterval(inc, repeatDelay);
    }, initialDelay);
  };
  const stopHoldInc = () => {
    clearTimeout(incTimeout); clearInterval(incInterval);
  };

  const btnStyle = {
    width: 22, height: 22, borderRadius: 6, display:'flex', alignItems:'center', justifyContent:'center',
    border: `1px solid ${isDark ? 'rgba(255,255,255,0.35)' : 'rgba(0,0,0,0.28)'}`, cursor:'pointer', userSelect:'none',
    color: isDark ? '#fff' : '#111'
  };

  return (
    <div style={{display:'flex', alignItems:'center', gap: 6}}>
      <div
        role="button"
        onClick={dec}
        onMouseDown={startHoldDec}
        onMouseUp={stopHoldDec}
        onMouseLeave={stopHoldDec}
        onTouchStart={startHoldDec}
        onTouchEnd={stopHoldDec}
        style={btnStyle}
        aria-label="감소"
      >&lt;</div>

      <BodyText style={{minWidth: 52, textAlign: 'center', fontSize: `${TYPE.h3}px`, fontWeight: 800, lineHeight: '22px', height: 22, color: (isDark ? '#fff' : '#111')}}>
        {value}{unit}
      </BodyText>

      <div
        role="button"
        onClick={inc}
        onMouseDown={startHoldInc}
        onMouseUp={stopHoldInc}
        onMouseLeave={stopHoldInc}
        onTouchStart={startHoldInc}
        onTouchEnd={stopHoldInc}
        style={btnStyle}
        aria-label="증가"
      >&gt;</div>
    </div>
  );
};

// iOS-like vertical WheelPicker for time selection
const WheelPicker = ({value, setValue, options, isDark, width=84, itemHeight=24, visibleCount=5, ariaLabel, formatter}) => {
  const half = Math.floor(visibleCount / 2);
  const idx = Math.max(0, options.findIndex(v => v === value));
  const clampIndex = (i) => Math.max(0, Math.min(options.length - 1, i));

  const onWheel = (e) => {
    e.preventDefault();
    const dir = e.deltaY > 0 ? 1 : -1;
    const next = clampIndex(idx + dir);
    setValue(options[next]);
  };

  // Touch drag (vertical) for TV remote/gesture-like feel
  let startY = null; let acc = 0;
  const onTouchStart = (e) => { startY = e.touches[0]?.clientY ?? null; acc = 0; };
  const onTouchMove = (e) => {
    if (startY == null) return;
    const y = e.touches[0]?.clientY ?? startY;
    const dy = y - startY;
    acc += dy;
    startY = y;
    if (Math.abs(acc) >= itemHeight * 0.6) {
      const step = acc > 0 ? -1 : 1; // swipe down -> previous
      const next = clampIndex(idx + step);
      setValue(options[next]);
      acc = 0;
    }
  };
  const onTouchEnd = () => { startY = null; acc = 0; };

  const containerStyle = {
    width,
    height: itemHeight * visibleCount,
    overflow: 'hidden',
    position: 'relative',
    borderRadius: 8,
    border: `1px solid ${isDark ? 'rgba(255,255,255,0.12)' : 'rgba(0,0,0,0.12)'}`,
    background: isDark ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.02)'
  };
  const listStyle = {
    position: 'absolute', left: 0, right: 0,
    top: `calc(50% - ${itemHeight/2}px - ${idx * itemHeight}px)`
  };
  const itemStyle = (active) => ({
    height: itemHeight, display:'flex', alignItems:'center', justifyContent:'center',
    fontSize: `${TYPE.h3}px`, fontWeight: active ? 800 : 600,
    color: active ? (isDark ? '#fff' : '#111') : (isDark ? 'rgba(255,255,255,0.5)' : 'rgba(0,0,0,0.5)')
  });
  const overlayLine = {
    position:'absolute', left:0, right:0,
    top: itemHeight * Math.floor(visibleCount/2), height: itemHeight,
    borderTop: `1.5px solid ${isDark ? 'rgba(255,255,255,0.25)' : 'rgba(0,0,0,0.15)'}`,
    borderBottom: `1.5px solid ${isDark ? 'rgba(255,255,255,0.25)' : 'rgba(0,0,0,0.15)'}`,
    pointerEvents:'none'
  };
  const overlayFadeTop = {
    position:'absolute', left:0, right:0, top:0, height: itemHeight * Math.floor(visibleCount/2),
    background: isDark
      ? 'linear-gradient(to bottom, rgba(0,0,0,0.5), rgba(0,0,0,0))'
      : 'linear-gradient(to bottom, rgba(255,255,255,0.9), rgba(255,255,255,0) )',
    pointerEvents:'none'
  };
  const overlayFadeBottom = {
    position:'absolute', left:0, right:0, bottom:0, height: itemHeight * Math.floor(visibleCount/2),
    background: isDark
      ? 'linear-gradient(to top, rgba(0,0,0,0.5), rgba(0,0,0,0))'
      : 'linear-gradient(to top, rgba(255,255,255,0.9), rgba(255,255,255,0) )',
    pointerEvents:'none'
  };

  return (
    <div
      role="listbox"
      aria-label={ariaLabel}
      onWheel={onWheel}
      onTouchStart={onTouchStart}
      onTouchMove={onTouchMove}
      onTouchEnd={onTouchEnd}
      style={containerStyle}
    >
      <div style={listStyle}>
        {options.map((opt, i) => (
          <div
            key={String(opt)}
            role="option"
            aria-selected={opt === value}
            onClick={() => setValue(opt)}
            style={itemStyle(opt === value)}
          >
            {(formatter ? formatter(opt) : String(opt).padStart(2,'0'))}
          </div>
        ))}
      </div>
      <div style={overlayLine} />
      <div style={overlayFadeTop} />
      <div style={overlayFadeBottom} />
    </div>
  );
};

// 공용 Pill — 활성 시 흰 글자 강제 + 대비 강화 (webOS 대응)
const Pill = ({active, onClick, children, isDark}) => {
  const baseBorder = isDark ? 'rgba(255,255,255,0.28)' : 'rgba(0,0,0,0.18)';
  const baseText = isDark ? '#fff' : '#111';
  const bg = active
    ? (isDark ? 'rgba(165,0,52,0.80)' : '#A50034')
    : (isDark ? 'rgba(255,255,255,0.02)' : 'rgba(0,0,0,0.02)');
  const labelColor = active ? '#ffffff' : baseText; // 활성 시 항상 흰색

  return (
    <div
      role="button"
      onClick={onClick}
      style={{
        padding: '6px 10px',
        borderRadius: 999,
        border: `1px solid ${active ? 'transparent' : baseBorder}`,
        background: bg,
        color: labelColor,
        fontWeight: 700,
        cursor: 'pointer',
        userSelect: 'none',
        fontSize: `${TYPE.label}px`,
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: 28,
        boxShadow: active ? '0 4px 12px rgba(165,0,52,0.25)' : 'none',
        transition: 'background .2s ease, box-shadow .2s ease'
      }}
    >
      <span style={{color: labelColor, WebkitTextFillColor: labelColor, fontWeight: 800, lineHeight: 1, pointerEvents:'none'}}>
        {children}
      </span>
    </div>
  );
};

// Read 'on'/'off' status from localStorage and map to boolean
const readStatusLS = (key, defOn = true) => {
  try {
    if (typeof window === 'undefined' || !window.localStorage) return defOn;
    const v = window.localStorage.getItem(key);
    if (v === null) return defOn;
    return v === 'on';
  } catch (e) { return defOn; }
};

export default function AutomationPanel(props) {
  const {
    isDark, textPrimary, textSecondary,
    routineType,
    devicePlans, // { wake: {lighting, curtains, ac, purifier}, sleep: {...} }
    preferredTemp, setPreferredTemp,
    wakeHour, setWakeHour,
    wakeMinute, setWakeMinute,
    wakeRetryMin, setWakeRetryMin,
    wakeAlarmOn, setWakeAlarmOn,
    sleepAlarmOn, setSleepAlarmOn,
    onSave
  } = props;
  const rt = routineType || 'wake';
  const showWake = rt === 'wake';
  const showSleep = rt === 'sleep';

  // Local UI state for routines (separate wake/sleep)
  const [wakeEnabled, setWakeEnabled] = useState(() => readStatusLS('soom.routine.wake.status', true));
  const [wakeActions, setWakeActions] = useState({lightOn:true, curtainOpen:true, coffee:true, music:false});

  const [sleepEnabled, setSleepEnabled] = useState(() => readStatusLS('soom.routine.sleep.status', true));
  const [sleepActions, setSleepActions] = useState({lightDim:true, curtainClose:true, acCool:false, purifier:false});
  const [sleepTemp, setSleepTemp] = useState(23);
  const [sleepHour, setSleepHour] = useState(23);
  const [sleepMinute, setSleepMinute] = useState(0);
  const [sleepRetryMin, setSleepRetryMin] = useState(10);


  const [wakePlan, setWakePlan] = useState({ lighting: true, curtains: true, ac: false, purifier: false });
  const [sleepPlan, setSleepPlan] = useState({ lighting: true, curtains: true, ac: false, purifier: true });

  const toggleWake = (key) => setWakeActions(prev => ({...prev, [key]: !prev[key]}));
  const toggleSleep = (key) => setSleepActions(prev => ({...prev, [key]: !prev[key]}));


  const handleSave = () => {
    // Use plans provided by parent so wake/sleep stay independent and persist
    const wakeDevices  = devicePlans?.wake  || { lighting:{}, curtains:{}, ac:{}, purifier:{} };
    const sleepDevices = devicePlans?.sleep || { lighting:{}, curtains:{}, ac:{}, purifier:{} };

    const payload = {
      routine: {
        wake: {
          status: (wakeEnabled ? 'on' : 'off'),
          enabled: !!wakeEnabled,
          time: { hour: (Number(sleepHour) % 24) || 0, minute: Number(sleepMinute) || 0 },          retryMin: Number(wakeRetryMin)||0,
          alarm: !!wakeAlarmOn,
          temp: Number(preferredTemp)||24,
          actions: { ...wakeActions },
          devices: { ...wakeDevices }
        },
        sleep: {
          status: (sleepEnabled ? 'on' : 'off'),
          enabled: !!sleepEnabled,
          time: { hour: Number(sleepHour)||0, minute: Number(sleepMinute)||0 },
          retryMin: Number(sleepRetryMin)||0,
          alarm: !!sleepAlarmOn,
          temp: Number(sleepTemp)||24,
          actions: { ...sleepActions },
          devices: { ...sleepDevices }
        }
      }
    };

    onSave && onSave(payload);
  };

  React.useEffect(() => {
    try {
      if (typeof window !== 'undefined' && window.localStorage)
        window.localStorage.setItem('soom.routine.wake.status', wakeEnabled ? 'on' : 'off');
    } catch (_) {}
  }, [wakeEnabled]);

  React.useEffect(() => {
    try {
      if (typeof window !== 'undefined' && window.localStorage)
        window.localStorage.setItem('soom.routine.sleep.status', sleepEnabled ? 'on' : 'off');
    } catch (_) {}
  }, [sleepEnabled]);

  return (
    <div style={{width: '100%', maxWidth:'920px', margin: '0 auto', color: textPrimary}}>
      <div style={{display: 'grid', gridTemplateColumns: (showWake && showSleep) ? 'repeat(2, 1fr)' : '1fr', gap: 10}}>
        {/* ===== 기상 시 (Wake Routine) ===== */}
        {showWake && (
        <div style={{width:'100%', borderRadius:10, padding:'10px', outline: `1px solid ${isDark ? LG_BRAND.borderDark : LG_BRAND.borderLight}`}}>
          <Row style={{justifyContent:'space-between', alignItems:'center'}}>
            <BodyText style={{color:textPrimary, fontSize:`${TYPE.h3}px`, fontWeight:800}}>기상 루틴 실행</BodyText>
            <Switch selected={wakeEnabled} onToggle={() => setWakeEnabled(v=>!v)} aria-label="기상 루틴 실행" />
          </Row>
          {wakeEnabled && (
            <>
              {/* 스마트 기기 제어 */}
              <Row style={{justifyContent:'space-between', alignItems:'center', gap:6, marginTop:4, flexWrap:'wrap'}}>
                <BodyText style={{color:(isDark ? '#fff' : '#111'), fontWeight:800, fontSize:`${TYPE.body}px`}}>기기 상세 조정</BodyText>
                <Row style={{gap:4}}>
                    <GhostButton isDark={isDark} size="small" onClick={() => document.dispatchEvent(new CustomEvent('openDeviceDetail',{detail:{device:'lighting', context:'wake'}}))}>조명 설정</GhostButton>
                    <GhostButton isDark={isDark} size="small" onClick={() => document.dispatchEvent(new CustomEvent('openDeviceDetail',{detail:{device:'curtains', context:'wake'}}))}>커튼 설정</GhostButton>
                    <GhostButton isDark={isDark} size="small" onClick={() => document.dispatchEvent(new CustomEvent('openDeviceDetail',{detail:{device:'ac', context:'wake'}}))}>에어컨 설정</GhostButton>
                    <GhostButton isDark={isDark} size="small" onClick={() => document.dispatchEvent(new CustomEvent('openDeviceDetail',{detail:{device:'purifier', context:'wake'}}))}>공기청정기 설정</GhostButton>
                </Row>
              </Row>

              {/* 기상 시간 */}
              <Row style={{justifyContent:'space-between', alignItems:'center', marginTop:4}}>
                <BodyText style={{color:(isDark ? '#fff' : '#111'), fontWeight:800, fontSize:`${TYPE.body}px`}}>기상 시간</BodyText>
                <Row style={{alignItems:'center', gap:6}}>
                  <WheelPicker
                    ariaLabel="기상 시각(시)"
                    value={wakeHour}
                    setValue={setWakeHour}
                    options={[...Array(24)].map((_, i) => i)}
                    isDark={isDark}
                    width={84}
                  />
                  <WheelPicker
                    ariaLabel="기상 시각(분)"
                    value={wakeMinute}
                    setValue={setWakeMinute}
                    options={[0,5,10,15,20,25,30,35,40,45,50,55]}
                    isDark={isDark}
                    width={84}
                  />
                </Row>
              </Row>
              {/* Combined 알림/재알림 Row */}
              <Row style={{justifyContent:'space-between', alignItems:'center', marginTop:4}}>
                <BodyText style={{color:(isDark ? '#fff' : '#111'), fontWeight:800, fontSize:`${TYPE.body}px`}}>내일 기상 알림 / 미기상 재알림</BodyText>
                <Row style={{alignItems:'center', gap:6}}>
                  <Switch selected={wakeAlarmOn} onToggle={() => setWakeAlarmOn(v=>!v)} aria-label="기상 알림 토글" />
                  <Row style={{alignItems:'center', gap:4, opacity: wakeAlarmOn ? 1 : 0.5, pointerEvents: wakeAlarmOn ? 'auto' : 'none'}}>
                    {[5,10,15,30].map(n => (
                      <Pill key={`wake-${n}`} isDark={isDark} active={wakeRetryMin === n} onClick={() => setWakeRetryMin(n)}>{n}분</Pill>
                    ))}
                  </Row>
                </Row>
              </Row>
            </>
          )}
        </div>
        )}
        {/* ===== 취침 시 (Sleep Routine) ===== */}
        {showSleep && (
        <div style={{width:'100%', borderRadius:10, padding:'10px', outline: `1px solid ${isDark ? LG_BRAND.borderDark : LG_BRAND.borderLight}`}}>
          <Row style={{justifyContent:'space-between', alignItems:'center'}}>
            <BodyText style={{color:textPrimary, fontSize:`${TYPE.h3}px`, fontWeight:800}}>취침 루틴 실행</BodyText>
            <Switch selected={sleepEnabled} onToggle={() => setSleepEnabled(v=>!v)} aria-label="취침 루틴 실행" />
          </Row>
          {sleepEnabled && (
            <>
              {/* 스마트 기기 제어 */}
              <Row style={{justifyContent:'space-between', alignItems:'center', gap:6, marginTop:4, flexWrap:'wrap'}}>
                <BodyText style={{color:(isDark ? '#fff' : '#111'), fontWeight:800, fontSize:`${TYPE.body}px`}}>기기 상세 조정</BodyText>
                <Row style={{gap:4}}>
                    <GhostButton isDark={isDark} size="small" onClick={() => document.dispatchEvent(new CustomEvent('openDeviceDetail',{detail:{device:'lighting', context:'sleep'}}))}>조명 설정</GhostButton>
                    <GhostButton isDark={isDark} size="small" onClick={() => document.dispatchEvent(new CustomEvent('openDeviceDetail',{detail:{device:'curtains', context:'sleep'}}))}>커튼 설정</GhostButton>
                    <GhostButton isDark={isDark} size="small" onClick={() => document.dispatchEvent(new CustomEvent('openDeviceDetail',{detail:{device:'ac', context:'sleep'}}))}>에어컨 설정</GhostButton>
                    <GhostButton isDark={isDark} size="small" onClick={() => document.dispatchEvent(new CustomEvent('openDeviceDetail',{detail:{device:'purifier', context:'sleep'}}))}>공기청정기 설정</GhostButton>
                </Row>
              </Row>

              {/* 취침 시간 */}
              <Row style={{justifyContent:'space-between', alignItems:'center', marginTop:4}}>
                <BodyText style={{color:(isDark ? '#fff' : '#111'), fontWeight:800, fontSize:`${TYPE.body}px`}}>취침 시간</BodyText>
                <Row style={{alignItems:'center', gap:6}}>
                  <WheelPicker
                    ariaLabel="취침 시각(시)"
                    value={sleepHour}
                    setValue={setSleepHour}
                    options={[...Array(28)].map((_, i) => i)} // 0..27 → 다음날 03시까지
                    formatter={(v) => String(v % 24).padStart(2,'0')}
                    isDark={isDark}
                    width={84}
                  />
                  <WheelPicker
                    ariaLabel="취침 시각(분)"
                    value={sleepMinute}
                    setValue={setSleepMinute}
                    options={[0,5,10,15,20,25,30,35,40,45,50,55]}
                    isDark={isDark}
                    width={84}
                  />
                </Row>
              </Row>
              {/* Combined 알림/재알림 Row */}
              <Row style={{justifyContent:'space-between', alignItems:'center', marginTop:4}}>
                <BodyText style={{color:(isDark ? '#fff' : '#111'), fontWeight:800, fontSize:`${TYPE.body}px`}}>오늘 취침 알림 / 미취침 재알림</BodyText>
                <Row style={{alignItems:'center', gap:6}}>
                  <Switch selected={sleepAlarmOn} onToggle={() => setSleepAlarmOn(v=>!v)} aria-label="취침 알림 토글" />
                  <Row style={{alignItems:'center', gap:4, opacity: sleepAlarmOn ? 1 : 0.5, pointerEvents: sleepAlarmOn ? 'auto' : 'none'}}>
                    {[5,10,15,30].map(n => (
                      <Pill key={`sleep-${n}`} isDark={isDark} active={sleepRetryMin === n} onClick={() => setSleepRetryMin(n)}>{n}분</Pill>
                    ))}
                  </Row>
                </Row>
              </Row>
            </>
          )}
        </div>
        )}
      </div>

      <Row style={{justifyContent:'center', marginTop: 4}}>
        <GhostButton isDark={isDark} onClick={handleSave}>설정 저장</GhostButton>
      </Row>
    </div>
  );
}