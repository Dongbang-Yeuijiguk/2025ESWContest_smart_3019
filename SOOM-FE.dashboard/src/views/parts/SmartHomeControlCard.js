// 대시보드 메인 화면 - 스마트홈 제어 카드
import React, {useState, useEffect, useRef} from 'react';
import Heading from '@enact/sandstone/Heading';
import BodyText from '@enact/sandstone/BodyText';
import Switch from '@enact/sandstone/Switch';
import {Row, Column} from '@enact/ui/Layout';

import lightingIcon from '../../assets/icons/smarthome/light.svg';
import acIcon from '../../assets/icons/smarthome/air-conditioner.svg';
import purifierIcon from '../../assets/icons/smarthome/air-purifier.svg';
import curtainOpenIcon from '../../assets/icons/smarthome/curtain_open.svg';
import curtainClosedIcon from '../../assets/icons/smarthome/curtain_closed.svg';

import { postRoutine } from '../../utils/postRoutine';
import AutomationPanel from './AutomationPanel';


// ---- Device Control API Helpers ----
const API_BASE = import.meta?.env?.VITE_API_BASE

async function sendDeviceCommand(device_type, payload) {
  try {
    if (typeof window !== 'undefined' && window.__SUPPRESS_DEVICE_POSTS) {
      // eslint-disable-next-line no-console
      console.warn('[DeviceControl] Suppressed (plan mode):', device_type, payload);
      return;
    }
    await fetch(`${API_BASE}/api/v1/dashboard/control/device`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ device_type, payload })
    });
  } catch (e) {
    // eslint-disable-next-line no-console
    console.error('[DeviceControl] Failed to send', device_type, payload, e);
  }
}

// Simple debounce hook for slider-like controls
function useDebounce(fn, delay = 800) {
  const timerRef = useRef(null);
  return (...args) => {
    clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => fn(...args), delay);
  };
}

// AC fan mapping (UI labels → API modes)
const AC_FAN_MAP = {
  '미약': 'breeze',
  '약': 'low',
  '중': 'medium',
  '강': 'high',
  '파워': 'turbo',
  '자동': 'auto'
};

// Local tokens (self-contained)
const TYPE = { h2: 20, h3: 16, body: 14, label: 14, tiny: 12 };
const LH = { tight: 1.1, normal: 1.35 };
const LG_BRAND = { red: '#A50034', pinkTint: 'rgba(165,0,52,0.06)', pinkTintStrong: 'rgba(165,0,52,0.12)' };

const AccentDot = ({isDark}) => (
  <div style={{ width: 8, height: 8, borderRadius: 999, background: LG_BRAND.red, boxShadow: isDark ? '0 0 0 3px rgba(165,0,52,0.25)' : '0 0 0 3px rgba(165,0,52,0.12)'}} />
);

const GhostButton = ({children, isDark, onClick, size = 'medium'}) => {
  const accent = LG_BRAND.red;
  const text = isDark ? '#fff' : '#111';
  const hoverBg = isDark ? 'rgba(165,0,52,0.14)' : 'rgba(165,0,52,0.10)';
  const {padY, padX, fz} = (
    size === 'small' ? {padY: 4, padX: 8,  fz: 12} :
    size === 'large' ? {padY: 8, padX: 16, fz: 16} :
    {padY: 6, padX: 12, fz: 14}
  );

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onClick}
      onMouseEnter={(e) => { e.currentTarget.style.background = hoverBg; }}
      onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent'; }}
      onFocus={(e) => { e.currentTarget.style.background = hoverBg; }}
      onBlur={(e) => { e.currentTarget.style.background = 'transparent'; }}
      style={{
        display:'inline-flex', alignItems:'center', justifyContent:'center',
        padding:`${padY}px ${padX}px`, borderRadius:999,
        border:`1px solid ${accent}`,
        background:'transparent', color:text,
        fontWeight:700, fontSize:fz, cursor:'pointer', userSelect:'none',
        transition:'background 0.2s ease, transform 0.12s ease, box-shadow 0.2s ease',
        boxShadow: isDark ? '0 1px 4px rgba(0,0,0,0.35)' : '0 1px 4px rgba(0,0,0,0.08)'
      }}
    >
      {children}
    </div>
  );
};

const ColorIcon = ({src, size = 112, color = LG_BRAND.red, scale = 0.9}) => (
  <div
    role="img"
    aria-hidden
    style={{
      width:size, height:size, backgroundColor:color,
      WebkitMaskImage:`url(${src})`, maskImage:`url(${src})`,
      WebkitMaskRepeat:'no-repeat', maskRepeat:'no-repeat',
      WebkitMaskPosition:'center', maskPosition:'center',
      WebkitMaskSize:`${Math.round(scale*100)}% ${Math.round(scale*100)}%`,
      maskSize:`${Math.round(scale*100)}% ${Math.round(scale*100)}%`
    }}
  />
);

const SmartTile = ({ img, label, isDark, onClick }) => {
  const [hovered, setHovered] = useState(false);
  const bg = isDark ? 'linear-gradient(145deg, #1c1c1c, #2a2a2a)' : 'linear-gradient(145deg, #ffffff, #f3f3f3)';
  const hoverBg = isDark ? 'linear-gradient(145deg, #2a2a2a, #1c1c1c)' : 'linear-gradient(145deg, #f3f3f3, #e7e7e7)';
  const border = isDark ? 'rgba(255,255,255,0.14)' : 'rgba(0,0,0,0.08)';
  const accent = isDark ? 'rgba(165,0,52,0.28)' : 'rgba(165,0,52,0.16)';
  const iconColor = hovered ? '#C5164F' : '#666';

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onClick}
      style={{
        display:'flex', flexDirection:'column', alignItems:'center', justifyContent:'center',
        gap:4, padding:10, minHeight:128, borderRadius:12,
        background: hovered ? hoverBg : bg, color: iconColor, cursor:'pointer',
        boxShadow:`0 4px 10px rgba(0,0,0,0.10), 0 0 0 1px ${accent}`,
        border:`1px solid ${border}`, userSelect:'none',
        transition:'background 0.25s ease, color 0.18s ease'
      }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      onFocus={() => setHovered(true)}
      onBlur={() => setHovered(false)}
    >
      <ColorIcon src={img} size={102} color={iconColor} scale={0.92} />
      <BodyText style={{ fontSize: 14, fontWeight: 800, textAlign: 'center', color: iconColor, lineHeight: '1.05em', marginTop: -8 }}>
        {label}
      </BodyText>
    </div>
  );
};

const SmartGrid = ({children}) => (
  <div style={{ display:'grid', gridTemplateColumns:'repeat(4, minmax(0, 1fr))', gap:10, marginTop:6 }}>
    {children}
  </div>
);

// ---- Lighting presets (Kelvin & Brightness) ----
const BRIGHTNESS_PRESETS = [25, 50, 75, 100];
const KELVIN_PRESETS = [
  {k: 2700, color: '#FFB56B', activity: '휴식'},
  {k: 4000, color: '#FFE1A7', activity: '독서'},
  {k: 5000, color: '#F0F4FF', activity: '공부'},
  {k: 6500, color: '#E3F0FF', activity: '청소'}
];

const Swatch = ({color, active, onClick, label, isDark, disabled = false}) => {
  const baseBorder = isDark ? 'rgba(255,255,255,0.28)' : 'rgba(0,0,0,0.18)';
  const ring = disabled
    ? `0 0 0 1px ${baseBorder}`
    : (active ? `0 0 0 2px ${LG_BRAND.red}, 0 0 0 6px rgba(165,0,52,0.20)` : `0 0 0 1px ${baseBorder}`);
  const labelColor = disabled ? (isDark ? 'rgba(255,255,255,0.5)' : '#999') : (isDark ? 'rgba(255,255,255,0.8)' : '#666');
  return (
    <div style={{display:'flex', flexDirection:'column', alignItems:'center', gap:6, opacity: disabled ? 0.5 : 1}}>
      <div
        role="button"
        aria-disabled={disabled}
        onClick={disabled ? undefined : onClick}
        style={{ width: 18, height: 18, borderRadius: '50%', background: color, boxShadow: ring, cursor: disabled ? 'not-allowed' : 'pointer', filter: disabled ? 'grayscale(0.2) saturate(0.7)' : 'none' }}
      />
      {label && (<BodyText style={{fontSize: `${TYPE.tiny}px`, color: labelColor}}>{label}</BodyText>)}
    </div>
  );
};

const Pill = ({active, onClick, children, isDark}) => {
  const baseBorder = isDark ? 'rgba(255,255,255,0.28)' : 'rgba(0,0,0,0.18)';
  const baseText = isDark ? '#fff' : '#111';
  const bg = active ? LG_BRAND.red : (isDark ? 'rgba(255,255,255,0.02)' : 'rgba(0,0,0,0.02)');
  const labelColor = active ? '#ffffff' : baseText; // 활성화 시 흰색 강제
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
        minHeight: 32,
        boxShadow: active ? '0 4px 12px rgba(165,0,52,0.25)' : 'none'
      }}
    >
      <span style={{color: labelColor, WebkitTextFillColor: labelColor, fontWeight: 800, lineHeight: 1}}>{children}</span>
    </div>
  );
};

const Stepper = ({value, setValue, min = 16, max = 30, isDark, unit = '℃', ariaDec = '온도 내리기', ariaInc = '온도 올리기'}) => (
  <div style={{display:'flex', alignItems:'center', gap: 6}}>
    <div role="button" onClick={() => setValue(t => Math.max(min, (Number(t)||min) - 1))} style={{ width: 24, height: 24, borderRadius: 8, display:'flex', alignItems:'center', justifyContent:'center', border: `1px solid ${isDark ? 'rgba(255,255,255,0.28)' : 'rgba(0,0,0,0.18)'}`, cursor:'pointer', userSelect:'none' }} aria-label={ariaDec}>&lt;</div>
    <BodyText style={{color: isDark ? '#fff' : '#111', minWidth: 56, textAlign: 'center', fontSize: `${TYPE.h3}px`, fontWeight: 800, lineHeight: '24px', height: 24}}>
      {value}{unit}
    </BodyText>
    <div role="button" onClick={() => setValue(t => Math.min(max, (Number(t)||min) + 1))} style={{ width: 24, height: 24, borderRadius: 8, display:'flex', alignItems:'center', justifyContent:'center', border: `1px solid ${isDark ? 'rgba(255,255,255,0.28)' : 'rgba(0,0,0,0.18)'}`, cursor:'pointer', userSelect:'none' }} aria-label={ariaInc}>&gt;</div>
  </div>
);

export default function SmartHomeControlCard({ isDark, textPrimary, textSecondary, curtainState: curtainStateProp }) {
  // Internal states (self-contained)
  const [smartOpen, setSmartOpen] = useState(false);
  const [selectedDevice, setSelectedDevice] = useState(null); // 'lighting' | 'curtains' | 'ac' | 'purifier' | 'automation'
  const [detailFromAutomation, setDetailFromAutomation] = useState(false);
  const [routineContext, setRoutineContext] = useState(null); // 'wake' | 'sleep' | null
  const [lightBrightness, setLightBrightness] = useState(70);
  const [lightCCT, setLightCCT] = useState(4000);
  const [curtainState, setCurtainState] = useState('off'); // 'on' | 'off'
  // 외부(env 훅)에서 전달된 커튼 상태와 동기화 (on/off 사용)
  useEffect(() => {
    if (typeof curtainStateProp === 'string' && curtainStateProp.length > 0) {
      const raw = curtainStateProp.toLowerCase();
      const normalized = raw === 'on' ? 'on' : raw === 'off' ? 'off' : null;
      if (normalized && normalized !== curtainState) setCurtainState(normalized);
    }
  }, [curtainStateProp, curtainState]);
  const [acPower, setAcPower] = useState(false);
  const [acTemp, setAcTemp] = useState(24);
  const [acFan, setAcFan] = useState('중');
  const [purifierPower, setPurifierPower] = useState(false);
  const [purifierMode, setPurifierMode] = useState('AUTO');
  // Automation states
  const [autoLightingOn, setAutoLightingOn] = useState(true);
  const [autoCurtainOn, setAutoCurtainOn] = useState(true);
  const [autoACOn, setAutoACOn] = useState(false);
  const [autoPurifierOn, setAutoPurifierOn] = useState(false);
  const [preferredTemp, setPreferredTemp] = useState(24);
  const [wakeHour, setWakeHour] = useState(7);
  const [wakeMinute, setWakeMinute] = useState(0);
  const [wakeRetryMin, setWakeRetryMin] = useState(10);
  const [wakeAlarmOn, setWakeAlarmOn] = useState(true);
  const [sleepAlarmOn, setSleepAlarmOn] = useState(true);
  // Automation routine tab: 'wake' | 'sleep'
  const [autoTab, setAutoTab] = useState('wake');

  const localTextSecondary = textSecondary ?? (isDark ? 'rgba(255,255,255,0.8)' : '#333');

  // Open device detail as a *plan* editor for the active routine tab (used by AutomationPanel)
  const openDetailWithContext = (device) => {
    setDetailFromAutomation(true);
    setRoutineContext(autoTab === 'sleep' ? 'sleep' : 'wake');
    setSelectedDevice(device);
    setSmartOpen(true);
  };
// ---- Routine-scoped planned device configs (independent of live states) ----
const [devicePlans, setDevicePlans] = useState({
  wake:  {
    lighting: { brightness: 70, cct: 4000 },
    curtains: { state: 'off' },
    ac:      { power: false, temp: 24, fan: '자동' },
    ap:      { power: false, mode: 'AUTO' }
  },
  sleep: {
    lighting: { brightness: 30, cct: 3500 },
    curtains: { state: 'on' },
    ac:      { power: false, temp: 23, fan: '자동' },
    ap:      { power: false, mode: 'AUTO' }
  }
});

// Load plans from localStorage on mount
useEffect(() => {
  try {
    const saved = JSON.parse(window.localStorage.getItem('SOOM_AUTOMATION_PLANS') || 'null');
    if (saved && (saved.wake || saved.sleep)) {
      setDevicePlans({
        wake:  { lighting: { brightness: 70, cct: 4000 }, curtains: { state: 'off' }, ac:{ power:false, temp:24, fan:'자동' }, ap:{ power:false, mode:'AUTO' }, ...(saved.wake  || {}) },
        sleep: { lighting: { brightness: 30, cct: 3500 }, curtains: { state: 'on'  }, ac:{ power:false, temp:23, fan:'자동' }, ap:{ power:false, mode:'AUTO' }, ...(saved.sleep || {}) }
      });
    }
  } catch (_) {}
}, []);

// Persist plans to localStorage whenever they change
useEffect(() => {
  try { window.localStorage.setItem('SOOM_AUTOMATION_PLANS', JSON.stringify(devicePlans)); } catch (_) {}
}, [devicePlans]);

// When opening from Automation with context, read plan; otherwise use live state
const isPlan = !!detailFromAutomation && (routineContext === 'wake' || routineContext === 'sleep');
const activeCtx = isPlan ? routineContext : null;
const planRef = isPlan ? devicePlans[activeCtx] : null;

// Suppress device-control POSTs globally during plan/automation editing
useEffect(() => {
  const suppress = isPlan || selectedDevice === 'automation' || detailFromAutomation;
  if (typeof window !== 'undefined') window.__SUPPRESS_DEVICE_POSTS = suppress;
  return () => {
    if (typeof window !== 'undefined') window.__SUPPRESS_DEVICE_POSTS = false;
  };
}, [isPlan, selectedDevice, detailFromAutomation]);

const viewLightBrightness = isPlan ? (planRef?.lighting?.brightness ?? lightBrightness) : lightBrightness;
const viewLightCCT        = isPlan ? (planRef?.lighting?.cct        ?? lightCCT)        : lightCCT;
const viewCurtainState    = isPlan ? (planRef?.curtains?.state      ?? curtainState)    : curtainState;

const viewAcPower = isPlan ? (planRef?.ac?.power ?? acPower) : acPower;
const viewAcTemp  = isPlan ? (planRef?.ac?.temp  ?? acTemp)  : acTemp;
const viewAcFan   = isPlan ? (planRef?.ac?.fan   ?? acFan)   : acFan;

const viewApPower = isPlan ? (planRef?.ap?.power ?? purifierPower) : purifierPower;
const viewApMode  = isPlan ? (planRef?.ap?.mode  ?? purifierMode)  : purifierMode;

  // Debounced senders
  const sendAcTempDebounced = useDebounce((temp) => {
    if (!isPlan && !(typeof window !== 'undefined' && window.__SUPPRESS_DEVICE_POSTS)) {
      sendDeviceCommand('air_conditioner', { target_ac_temperature: temp });
    }
  }, 800);

  const sendLightLevelDebounced = useDebounce((level) => {
    if (typeof window !== 'undefined' && window.__SUPPRESS_DEVICE_POSTS) return;
    const payload = {
      target_light_level: level,
      light_power: level > 0 ? 'on' : 'off',
      light_temperature: lightCCT
    };
    sendDeviceCommand('smart_light', payload);
  }, 600);

  // When AC temp changes (and AC is on), send debounced
  useEffect(() => {
    if (!isPlan && acPower && !(typeof window !== 'undefined' && window.__SUPPRESS_DEVICE_POSTS)) {
      sendAcTempDebounced(acTemp);
    }
  }, [acTemp, acPower, isPlan]);

  const firstRenderLightRef = useRef(true);

  // When light brightness changes, send debounced level/power (skip first render)
  useEffect(() => {
    if (firstRenderLightRef.current) {
      firstRenderLightRef.current = false;
      return;
    }

    if (!isPlan) {
      sendLightLevelDebounced(lightBrightness);
    }
  }, [lightBrightness, isPlan]);

  // Bridge: allow external customEvent("openDeviceDetail") if used elsewhere
  useEffect(() => {
    const handler = (e) => {
      const d = e.detail;
      if (d && typeof d === 'object') {
        setSelectedDevice(d.device);
        setRoutineContext(d.context || null);
      } else {
        setSelectedDevice(d);
        setRoutineContext(null);
      }
      setDetailFromAutomation(true);
      setSmartOpen(true);
    };
    document.addEventListener('openDeviceDetail', handler);
    return () => document.removeEventListener('openDeviceDetail', handler);
  }, []);

  return (
    <Column className={isDark ? 'card card--dark' : 'card card--light'} style={{gap: 10, minHeight: 240, padding: '12px 12px 14px'}}>
      <Row style={{justifyContent: 'space-between', alignItems: 'center'}}>
        <Row style={{alignItems: 'center', gap: 8}}>
          <AccentDot isDark={isDark} />
          <Heading size="large" style={{color: textPrimary, fontSize: `${TYPE.h2}px`, lineHeight: `${LH.tight}em`, fontWeight: 800}}>
            스마트홈 제어
          </Heading>
        </Row>
        <GhostButton
          isDark={isDark}
          onClick={() => { setDetailFromAutomation(false); setSelectedDevice('automation'); setSmartOpen(true); }}
        >
          자동화 루틴 설정
        </GhostButton>
      </Row>

      <SmartGrid>
        <SmartTile isDark={isDark} img={lightingIcon} label="조명"
          onClick={() => { setDetailFromAutomation(false); setRoutineContext(null); setSelectedDevice('lighting'); setSmartOpen(true); }} />
        <SmartTile isDark={isDark} img={curtainState === 'on' ? curtainClosedIcon : curtainOpenIcon} label="커튼"
          onClick={() => { setDetailFromAutomation(false); setRoutineContext(null); setSelectedDevice('curtains'); setSmartOpen(true); }} />
        <SmartTile isDark={isDark} img={acIcon} label="에어컨"
          onClick={() => { setDetailFromAutomation(false); setRoutineContext(null); setSelectedDevice('ac'); setSmartOpen(true); }} />
        <SmartTile isDark={isDark} img={purifierIcon} label="공기청정기"
          onClick={() => { setDetailFromAutomation(false); setRoutineContext(null); setSelectedDevice('purifier'); setSmartOpen(true); }} />
      </SmartGrid>

      {smartOpen && (
        <div
          style={{ position: 'fixed', inset: 0, zIndex: 9999, background: 'rgba(0,0,0,0.55)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
          role="dialog"
          aria-modal="true"
        >
          <div
            style={{
              position: 'relative', width: '96vw', maxWidth: selectedDevice === 'automation' ? '720px' : '560px', maxHeight: '90vh', overflowY: 'auto', borderRadius: 16, padding: 14,
              background: isDark ? 'linear-gradient(180deg, rgba(32,32,32,1), rgba(24,24,24,1))' : 'linear-gradient(180deg, #ffffff, #f6f6f6)',
              outline: isDark ? '1px solid rgba(255,255,255,0.12)' : '1px solid rgba(0,0,0,0.08)',
              boxShadow: isDark ? '0 20px 60px rgba(0,0,0,0.6)' : '0 20px 60px rgba(0,0,0,0.2)',
              border: isDark ? '1px solid rgba(165,0,52,0.28)' : '1px solid rgba(165,0,52,0.16)', boxSizing: 'border-box'
            }}
          >
            <Row style={{justifyContent: 'space-between', alignItems: 'center', marginBottom: 8}}>
              <Row style={{alignItems: 'center', gap: 8}}>
                <AccentDot isDark={isDark} />
                <Heading size="large" style={{color: textPrimary, fontSize: `${TYPE.h2}px`, lineHeight: `${LH.tight}em`, fontWeight: 800}}>
                  {selectedDevice === 'automation' && '자동화 루틴 설정'}
                  {selectedDevice === 'lighting' && (<>
                    조명 상세 설정
                    {detailFromAutomation && routineContext && (
                      <span style={{marginLeft: 8, fontSize: 12, color: isDark ? 'rgba(255,255,255,0.7)' : 'rgba(0,0,0,0.6)'}}>· {routineContext === 'wake' ? '기상 루틴' : '취침 루틴'}</span>
                    )}
                  </>)}
                  {selectedDevice === 'curtains' && (<>
                    커튼 상세 설정
                    {detailFromAutomation && routineContext && (
                      <span style={{marginLeft: 8, fontSize: 12, color: isDark ? 'rgba(255,255,255,0.7)' : 'rgba(0,0,0,0.6)'}}>· {routineContext === 'wake' ? '기상 루틴' : '취침 루틴'}</span>
                    )}
                  </>)}
                  {selectedDevice === 'ac' && (<>
                    에어컨 상세 설정
                    {detailFromAutomation && routineContext && (
                      <span style={{marginLeft: 8, fontSize: 12, color: isDark ? 'rgba(255,255,255,0.7)' : 'rgba(0,0,0,0.6)'}}>· {routineContext === 'wake' ? '기상 루틴' : '취침 루틴'}</span>
                    )}
                  </>)}
                  {selectedDevice === 'purifier' && (<>
                    공기청정기 상세 설정
                    {detailFromAutomation && routineContext && (
                      <span style={{marginLeft: 8, fontSize: 12, color: isDark ? 'rgba(255,255,255,0.7)' : 'rgba(0,0,0,0.6)'}}>· {routineContext === 'wake' ? '기상 루틴' : '취침 루틴'}</span>
                    )}
                  </>)}
                </Heading>
              </Row>
              <GhostButton isDark={isDark} size="small" onClick={() => {
                if (selectedDevice && selectedDevice !== 'automation' && detailFromAutomation) {
                  setSelectedDevice('automation');
                  setDetailFromAutomation(false);
                } else {
                  setSmartOpen(false);
                }
              }}>닫기</GhostButton>
            </Row>

            <Column style={{gap: 12}}>
              {selectedDevice === 'automation' && (
                <div style={{width:'100%', maxWidth:'1100px', margin:'0 auto'}}>
                  <Row style={{justifyContent:'center', marginTop: 6, marginBottom: 6, gap: 10}}>
                    <Pill isDark={isDark} active={autoTab === 'wake'} onClick={() => setAutoTab('wake')}>기상 루틴</Pill>
                    <Pill isDark={isDark} active={autoTab === 'sleep'} onClick={() => setAutoTab('sleep')}>취침 루틴</Pill>
                  </Row>
                  <AutomationPanel
                    isDark={isDark}
                    textPrimary={textPrimary}
                    textSecondary={localTextSecondary}
                    routineType={autoTab}
                    devicePlans={devicePlans}
                    autoLightingOn={autoLightingOn} setAutoLightingOn={setAutoLightingOn}
                    autoCurtainOn={autoCurtainOn} setAutoCurtainOn={setAutoCurtainOn}
                    autoACOn={autoACOn} setAutoACOn={setAutoACOn}
                    autoPurifierOn={autoPurifierOn} setAutoPurifierOn={setAutoPurifierOn}
                    preferredTemp={preferredTemp} setPreferredTemp={setPreferredTemp}
                    wakeHour={wakeHour} setWakeHour={setWakeHour}
                    wakeMinute={wakeMinute} setWakeMinute={setWakeMinute}
                    wakeRetryMin={wakeRetryMin} setWakeRetryMin={setWakeRetryMin}
                    wakeAlarmOn={wakeAlarmOn} setWakeAlarmOn={setWakeAlarmOn}
                    sleepAlarmOn={sleepAlarmOn} setSleepAlarmOn={setSleepAlarmOn}
                    onSave={async (payload) => {
                      await postRoutine(payload);
                      setSmartOpen(false);
                    }}
                    onOpenDetail={openDetailWithContext}
                  />
                </div>
              )}

              {selectedDevice === 'lighting' && (
                <Column style={{gap: 6}}>
                  <Row style={{justifyContent: 'space-between', alignItems: 'center'}}>
                    <BodyText style={{color: textPrimary, fontSize: `${TYPE.h3}px`, fontWeight: 800, lineHeight: `${LH.normal}em`}}>조명</BodyText>
                    <Switch 
                      selected={viewLightBrightness > 0}
                       onToggle={() => {
                        if (isPlan) {
                          const nextB = viewLightBrightness > 0 ? 0 : 100;
                          setDevicePlans(prev => ({
                            ...prev,
                            [activeCtx]: {
                              ...prev[activeCtx],
                              lighting: { ...(prev[activeCtx]?.lighting||{}), brightness: nextB }
                            }
                          }));
                        } else {
                          setLightBrightness(viewLightBrightness > 0 ? 0 : 100);
                        }
                      }}
                      aria-label="조명 전원 토글"
                      />
                  </Row>
                  <div style={{ borderRadius: 14, padding: '14px 16px', background: isDark ? LG_BRAND.pinkTintStrong : LG_BRAND.pinkTint, outline: isDark ? '1px solid rgba(165,0,52,0.28)' : '1px solid rgba(165,0,52,0.18)'}}>
                    <Column style={{gap: 16}}>
                      <Row style={{justifyContent: 'center', alignItems: 'center', opacity: viewLightBrightness > 0 ? 1 : 0.5, pointerEvents: viewLightBrightness > 0 ? 'auto' : 'none'}}>                        <div style={{display:'flex', alignItems:'center', gap: 10, flexWrap: 'wrap'}}>
                          {BRIGHTNESS_PRESETS.map(v => (
                            <Pill key={v} isDark={isDark} active={viewLightBrightness === v} onClick={() => {
                              if (isPlan) {
                                setDevicePlans(prev => ({
                                  ...prev,
                                  [activeCtx]: {
                                    ...prev[activeCtx],
                                    lighting: { ...(prev[activeCtx]?.lighting||{}), brightness: v }
                                  }
                                }));
                              } else {
                                setLightBrightness(v); // debounced effect will send
                              }
                            }}>{v}%</Pill>
                          ))}
                        </div>
                      </Row>
                      <Row style={{justifyContent: 'center', alignItems: 'center', marginTop: '20px'}}>
                        <div style={{display:'flex', alignItems:'center', gap: 8, flexWrap: 'wrap'}}>
                          {KELVIN_PRESETS.map(p => (
                            <Swatch key={p.k} color={p.color} label={`${p.activity}`} isDark={isDark}
                              active={viewLightBrightness >= 25 && viewLightCCT === p.k}
                              disabled={viewLightBrightness < 25}
                              onClick={() => { 
                                if (viewLightBrightness >= 25) { 
                                  if (isPlan) {
                                    setDevicePlans(prev => ({
                                      ...prev,
                                      [activeCtx]: {
                                        ...prev[activeCtx],
                                        lighting: { ...(prev[activeCtx]?.lighting||{}), cct: p.k }
                                      }
                                    }));
                                  } else {
                                    setLightCCT(p.k); 
                                    sendDeviceCommand('smart_light', {
                                      light_temperature: p.k,
                                      target_light_level: lightBrightness,
                                      light_power: lightBrightness > 0 ? 'on' : 'off'
                                    });
                                  }
                                } 
                              }}
                            />
                          ))}
                        </div>
                      </Row>
                    </Column>
                  </div>
                </Column>
              )}

              {selectedDevice === 'curtains' && (
                <Column style={{gap: 6}}>
                  <div style={{ borderRadius: 14, padding: '14px 16px', outline: isDark ? '1px solid rgba(165,0,52,0.28)' : '1px solid rgba(165,0,52,0.18)'}}>
                    <div style={{display:'flex', alignItems:'center', justifyContent:'center', gap: 12, flexWrap:'wrap'}}>
                      <div
                        role="button"
                        onClick={() => {
                          if (viewCurtainState !== 'off') {
                            if (isPlan) {
                              setDevicePlans(prev => ({
                                ...prev,
                                [activeCtx]: {
                                  ...prev[activeCtx],
                                  curtains: { ...(prev[activeCtx]?.curtains||{}), state: 'off' }
                                }
                              }));
                            } else {
                              setCurtainState('off');
                              sendDeviceCommand('smart_curtain', { curtain: 'off' });
                            }
                          }
                        }}
                        style={{
                          display:'flex',
                          flexDirection:'column',
                          alignItems:'center',
                          padding: 8,
                          gap: 2,
                          borderRadius: 16,
                          boxShadow: viewCurtainState === 'off'
                            ? `0 0 0 2px ${LG_BRAND.red}, 0 0 0 6px rgba(165,0,52,0.2)`
                            : `0 0 0 1px ${isDark ? 'rgba(255,255,255,0.18)' : 'rgba(0,0,0,0.12)'}`,
                          cursor:'pointer'
                        }}
                      >
                        <ColorIcon src={curtainOpenIcon} size={112} color={viewCurtainState === 'off' ? LG_BRAND.red : '#666'} scale={0.92} />
                        <BodyText style={{ fontSize: `${TYPE.label}px`, fontWeight: 800, color: viewCurtainState === 'off' ? LG_BRAND.red : textPrimary, marginTop: -8 }}>열림</BodyText>
                      </div>
                      <div
                        role="button"
                        onClick={() => {
                          if (viewCurtainState !== 'on') {
                            if (isPlan) {
                              setDevicePlans(prev => ({
                                ...prev,
                                [activeCtx]: {
                                  ...prev[activeCtx],
                                  curtains: { ...(prev[activeCtx]?.curtains||{}), state: 'on' }
                                }
                              }));
                            } else {
                              setCurtainState('on');
                              sendDeviceCommand('smart_curtain', { curtain: 'on' });
                            }
                          }
                        }}
                        style={{
                          display:'flex',
                          flexDirection:'column',
                          alignItems:'center',
                          padding: 8,
                          gap: 2,
                          borderRadius: 16,
                          boxShadow: viewCurtainState === 'on'
                            ? `0 0 0 2px ${LG_BRAND.red}, 0 0 0 6px rgba(165,0,52,0.2)`
                            : `0 0 0 1px ${isDark ? 'rgba(255,255,255,0.18)' : 'rgba(0,0,0,0.12)'}`,
                          cursor:'pointer'
                        }}
                      >
                        <ColorIcon src={curtainClosedIcon} size={112} color={viewCurtainState === 'on' ? LG_BRAND.red : '#666'} scale={0.92} />
                        <BodyText style={{ fontSize: `${TYPE.label}px`, fontWeight: 800, color: viewCurtainState === 'on' ? LG_BRAND.red : textPrimary, marginTop: -8 }}>닫힘</BodyText>
                      </div>
                    </div>
                  </div>
                </Column>
              )}

              {selectedDevice === 'purifier' && (
                <Column style={{gap: 6}}>
                  <Row style={{justifyContent: 'space-between', alignItems: 'center'}}>
                    <BodyText style={{color: textPrimary, fontSize: `${TYPE.h3}px`, fontWeight: 800, lineHeight: `${LH.normal}em`}}>공기청정기</BodyText>
                    <Switch selected={viewApPower} onToggle={() => {
                      if (isPlan) {
                        setDevicePlans(prev => ({
                          ...prev,
                          [activeCtx]: {
                            ...prev[activeCtx],
                            ap: { ...(prev[activeCtx]?.ap||{}), power: !viewApPower }
                          }
                        }));
                      } else {
                        setPurifierPower(v => { 
                          const next = !v; 
                          const mode = (purifierMode || 'AUTO').toLowerCase();
                          sendDeviceCommand('air_purifier', { ap_power: next ? 'on' : 'off', target_ap_mode: mode });
                          return next; 
                        });
                      }
                    }} aria-label="공기청정기 전원 토글" />
                  </Row>
                  <div style={{ borderRadius: 14, padding: '14px 16px', background: isDark ? LG_BRAND.pinkTintStrong : LG_BRAND.pinkTint, outline: isDark ? '1px solid rgba(165,0,52,0.28)' : '1px solid rgba(165,0,52,0.18)', opacity: viewApPower ? 1 : 0.5, pointerEvents: viewApPower ? 'auto' : 'none' }}>
                    <div style={{display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8, flexWrap: 'wrap', width: '100%'}}>
                      {['SLOW','LOW','MID','HIGH','POWER','AUTO'].map(m => (
                        <Pill key={m} isDark={isDark} active={viewApMode === m} onClick={() => { 
                          if (isPlan) {
                            setDevicePlans(prev => ({
                              ...prev,
                              [activeCtx]: {
                                ...prev[activeCtx],
                                ap: { ...(prev[activeCtx]?.ap||{}), mode: m }
                              }
                            }));
                          } else {
                            setPurifierMode(m); 
                            const mode = m.toLowerCase();
                            const power = (purifierPower ? 'on' : 'off');
                            sendDeviceCommand('air_purifier', { ap_power: power, target_ap_mode: mode });
                          }
                        }}>{m}</Pill>
                      ))}
                    </div>
                  </div>
                </Column>
              )}

              {selectedDevice === 'ac' && (
                <Column style={{gap: 6}}>
                  <Row style={{justifyContent: 'space-between', alignItems: 'center'}}>
                    <BodyText style={{color: textPrimary, fontSize: `${TYPE.h3}px`, fontWeight: 800, lineHeight: `${LH.normal}em`}}>에어컨</BodyText>
                  <Switch selected={viewAcPower} onToggle={() => { 
                    if (isPlan) {
                      setDevicePlans(prev => ({
                        ...prev,
                        [activeCtx]: {
                          ...prev[activeCtx],
                          ac: { ...(prev[activeCtx]?.ac||{}), power: !viewAcPower }
                        }
                      }));
                    } else {
                      setAcPower(v => { 
                        const next = !v; 
                        sendDeviceCommand('air_conditioner', { ac_power: next ? 'on' : 'off' });
                        return next; 
                      }); 
                    }
                  }} aria-label="에어컨 전원 토글" />
                  </Row>
                  <div style={{ borderRadius: 14, padding: '14px 16px', background: isDark ? LG_BRAND.pinkTintStrong : LG_BRAND.pinkTint, outline: isDark ? '1px solid rgba(165,0,52,0.28)' : '1px solid rgba(165,0,52,0.18)' }}>
                    <div style={{ display:'grid', gridTemplateColumns:'120px 1fr', rowGap: 8, columnGap: 10, alignItems:'center', width: '100%', opacity: viewAcPower ? 1 : 0.5, pointerEvents: viewAcPower ? 'auto' : 'none' }}>
                      <BodyText style={{color: '#000', fontSize: `${TYPE.body}px`, fontWeight: 800, justifySelf:'start'}}>온도</BodyText>
                      <div style={{display:'flex', alignItems:'center', justifyContent:'flex-end', justifySelf:'end'}}>
                        <Stepper
                          value={viewAcTemp}
                          setValue={(updater) => {
                            const next = typeof updater === 'function' ? updater(viewAcTemp) : updater;
                            if (isPlan) {
                              setDevicePlans(prev => ({
                                ...prev,
                                [activeCtx]: {
                                  ...prev[activeCtx],
                                  ac: { ...(prev[activeCtx]?.ac||{}), temp: next }
                                }
                              }));
                            } else {
                              setAcTemp(next);
                            }
                          }}
                          min={16}
                          max={30}
                          isDark={false}
                        />
                      </div>
                      <BodyText style={{color: '#000', fontSize: `${TYPE.body}px`, fontWeight: 800, justifySelf:'start'}}>바람 세기</BodyText>
                      <div style={{display:'flex', alignItems:'center', justifyContent:'flex-end', gap: 6, flexWrap: 'wrap', justifySelf:'end'}}>
                        {['미약','약','중','강','파워','자동'].map(label => (
                          <Pill
                            key={label}
                            isDark={false}
                            active={viewAcFan === label}
                            onClick={() => {
                              if (isPlan) {
                                setDevicePlans(prev => ({
                                  ...prev,
                                  [activeCtx]: {
                                    ...prev[activeCtx],
                                    ac: { ...(prev[activeCtx]?.ac||{}), fan: label }
                                  }
                                }));
                              } else {
                                setAcFan(label);
                                const mode = AC_FAN_MAP[label] || 'auto';
                                sendDeviceCommand('air_conditioner', { target_ac_mode: mode });
                              }
                            }}
                          >
                            {label}
                          </Pill>
                        ))}
                      </div>
                    </div>
                  </div>
                </Column>
              )}
            </Column>
          </div>
        </div>
      )}
    </Column>
  );
}