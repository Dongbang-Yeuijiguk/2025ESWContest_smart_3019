// 대시보드 메인 화면 - 실내 환경 카드
import React from 'react';
import Heading from '@enact/sandstone/Heading';
import BodyText from '@enact/sandstone/BodyText';
import {Row, Column} from '@enact/ui/Layout';

import AirQualityAlertModal from './AirQualityAlertModal';

import tempIcon from '../../assets/icons/env/temperature.svg';
import humidityIcon from '../../assets/icons/env/humidity.svg';
import airIcon from '../../assets/icons/env/air-quality.svg';
import dustIcon from '../../assets/icons/env/finedust.svg';

// 로컬 토큰(컴포넌트를 독립적으로 유지)
const TYPE = { h2: 18, body: 14, label: 12 };
const LH = { tight: 1.1, normal: 1.35 };

const LG_BRAND = { red: '#A50034' };

// PM2.5(초미세먼지) 등급: ≤15 좋음, ≤35 보통, >35 나쁨
const pm25Label = (v) => {
  const n = Number(v);
  if (!Number.isFinite(n)) return '-';
  if (n <= 15) return '좋음';
  if (n <= 35) return '보통';
  return '나쁨';
};

// US AQI
// 0–50 좋음, 51–100 보통, 101–150 주의, 151–200 나쁨, 201–300 매우 나쁨, 301+ 위험
const aqiLabel = (v) => {
  const n = Number(v);
  if (!Number.isFinite(n)) return '-';
  if (n <= 50) return '좋음';
  if (n <= 100) return '보통';
  if (n <= 150) return '주의';
  if (n <= 200) return '나쁨';
  if (n <= 300) return '매우 나쁨';
  return '위험';
};


const AccentDot = ({isDark}) => (
  <div style={{
    width: 8, height: 8, borderRadius: 999, background: LG_BRAND.red,
    boxShadow: isDark ? '0 0 0 3px rgba(165,0,52,0.25)' : '0 0 0 3px rgba(165,0,52,0.12)'
  }} />
);

const ICON_SIZE = 64;
const ColorIcon = ({src, size = ICON_SIZE, color = LG_BRAND.red, scale = 0.9}) => (
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

const EnvRowIcon = ({icon, label, value, isDark, textPrimary, textSecondary, minHeight = 40}) => (
  <div style={{
    display:'flex', alignItems:'center', justifyContent:'space-between',
    padding:'6px 8px', gap: 10, minHeight,
  }}>
    <div style={{display:'flex', alignItems:'center', gap: 10, minWidth: 0}}>
      <ColorIcon src={icon} size={28} color={isDark ? '#777' : '#888'} scale={0.9} />
      <div style={{display:'flex', flexDirection:'column', minWidth:0}}>
        {typeof label === 'string' ? (
          <BodyText style={{fontSize: `${TYPE.label}px`, color: textSecondary, lineHeight:'1.25em'}}>{label}</BodyText>
        ) : label}
      </div>
    </div>
    <BodyText style={{fontSize: `${TYPE.body}px`, fontWeight:800, color:textPrimary, whiteSpace:'nowrap', textAlign:'right'}}>
      {value}
    </BodyText>
  </div>
);

const EnvStat = ({icon, label, value, isDark, textPrimary, textSecondary}) => (
  <div style={{
    display:'flex', flexDirection:'column', alignItems:'center', justifyContent:'center',
    padding:'8px 6px', gap: 6, minHeight: 96, textAlign:'center', wordBreak:'keep-all'
  }}>
    <ColorIcon src={icon} size={30} color={isDark ? '#777' : '#888'} scale={0.9} />
    <BodyText style={{fontSize:`${TYPE.label}px`, lineHeight:'1.2em', color:textSecondary, whiteSpace:'normal', textAlign:'center'}}>{label}</BodyText>
    <BodyText style={{fontSize:`${TYPE.body}px`, lineHeight:'1.2em', fontWeight:800, color:textPrimary}}>{value}</BodyText>
  </div>
);

const EnvTile = ({icon, label, value, inline = false, secondLine, isDark, textPrimary, textSecondary}) => (
  <div style={{
    display:'flex', flexDirection:'row', alignItems:'center', justifyContent:'space-between',
    gap: 8, padding:'4px 6px',
    background:'transparent', border:'none', boxShadow:'none', height:32
  }}>
    <ColorIcon src={icon} size={32} color={isDark ? '#777' : '#888'} scale={0.9} />
    {inline ? (
      <>
        <BodyText style={{fontSize: `${TYPE.label}px`, color: textSecondary, opacity: 0.9, lineHeight: '1.1em'}}>{label}</BodyText>
        <BodyText style={{fontSize: `${TYPE.body}px`, fontWeight: 800, color: textPrimary, lineHeight: '1.1em'}}>{value}</BodyText>
      </>
    ) : (
      <>
        <BodyText style={{fontSize: `${TYPE.label}px`, color: textSecondary, opacity: 0.9, lineHeight: '1.05em'}}>{label}</BodyText>
        <BodyText style={{fontSize: `${TYPE.h2}px`, fontWeight: 800, color: textPrimary, lineHeight: '1em', marginBottom: 0}}>{value}</BodyText>
      </>
    )}
    {secondLine && (
      <BodyText style={{fontSize: `${TYPE.label}px`, color: textSecondary, opacity: 0.9, lineHeight: '1.1em', marginTop: 2}}>
        {secondLine}
      </BodyText>
    )}
  </div>
);

const EnvRow = ({label, value, textPrimary, textSecondary}) => (
  <Row
    style={{
      justifyContent: 'space-between',
      alignItems: 'center',
      padding: '8px 6px',
      borderBottom: '1px solid rgba(255,255,255,0.12)',
      minHeight: 36
    }}
  >
    <BodyText style={{fontSize: `${TYPE.label}px`, lineHeight: `${LH.normal}em`, opacity: 0.85, color: textSecondary}}>
      {label}
    </BodyText>
    <BodyText style={{fontSize: `${TYPE.body}px`, lineHeight: `${LH.normal}em`, fontWeight: 700, textAlign: 'right', minWidth: 48, color: textPrimary}}>
      {value}
    </BodyText>
  </Row>
);

const IconLabel = ({icon, label, isDark, textSecondary}) => (
  <div style={{display:'flex', flexDirection:'column', alignItems:'center', justifyContent:'center', height: 72, paddingTop: 4}}>
    <div style={{width: 38, height: 38, display:'flex', alignItems:'center', justifyContent:'center'}}>
      <ColorIcon src={icon} size={34} color={isDark ? '#777' : '#888'} scale={0.95} />
    </div>
    <BodyText style={{fontSize:`${TYPE.label}px`, lineHeight:'1.2em', color:textSecondary, marginTop: 6, textAlign:'center'}}>{label}</BodyText>
  </div>
);

const ValueBlock = ({children}) => (
  <div style={{display:'flex', flexDirection:'column', alignItems:'center', justifyContent:'flex-start', height: 56}}>
    {children}
  </div>
);

export default function EnvCard({
  isDark,
  textPrimary,
  textSecondary,
  env,                // {temperature, humidity, curtain, air_quality, pm_10, pm_2_5}
  autoMode,
  setAutoMode
}) {
  return (
    <Column className={isDark ? 'card card--dark' : 'card card--light'} style={{gap: 12, minHeight: 240, padding: '12px 12px 14px'}}>
      <Row style={{alignItems: 'center', gap: 8}}>
        <AccentDot isDark={isDark} />
        <Heading size="large" style={{color: textPrimary, fontSize: `${TYPE.h2}px`, lineHeight: `${LH.tight}em`, fontWeight: 800}}>
          실내 환경
        </Heading>
      </Row>

      {/* 상단: 아이콘 + 라벨 고정 라인 */}
      <div style={{ display:'grid', gridTemplateColumns:'repeat(4, 1fr)', gap: 8, alignItems:'center' }}>
        <IconLabel icon={tempIcon}    label="온도"     isDark={isDark} textSecondary={textSecondary} />
        <IconLabel icon={humidityIcon} label="습도"     isDark={isDark} textSecondary={textSecondary} />
        <IconLabel icon={airIcon}      label="공기질"   isDark={isDark} textSecondary={textSecondary} />
        <IconLabel icon={dustIcon}     label="미세먼지" isDark={isDark} textSecondary={textSecondary} />
      </div>

      {/* 하단: 값 / 세부 정보 라인 (아이콘 높이에 영향 없음) */}
      <div style={{ display:'grid', gridTemplateColumns:'repeat(4, 1fr)', gap: 8, alignItems:'start', marginTop: -10 }}>
        <ValueBlock>
          <BodyText style={{fontSize:`${TYPE.body}px`, fontWeight:800, color:textPrimary, lineHeight:'1em'}}>{`${env?.temperature ?? '-'}℃`}</BodyText>
        </ValueBlock>
        <ValueBlock>
          <BodyText style={{fontSize:`${TYPE.body}px`, fontWeight:800, color:textPrimary, lineHeight:'1em'}}>{`${env?.humidity ?? '-'}%`}</BodyText>
        </ValueBlock>
        <ValueBlock>
          <BodyText style={{fontSize:`${TYPE.body}px`, fontWeight:800, color:textPrimary}}>{aqiLabel(env?.air_quality)}</BodyText>
          <BodyText style={{fontSize:`${TYPE.label - 2}px`, color:textSecondary, opacity:0.8, marginTop: -20}}>{env?.air_quality ?? '-'} AQI</BodyText>
        </ValueBlock>
        <ValueBlock>
          <BodyText style={{fontSize:`${TYPE.body}px`, fontWeight:800, color:textPrimary}}>{pm25Label(env?.pm_2_5)}</BodyText>
          <BodyText style={{fontSize:`${TYPE.label - 2}px`, color:textSecondary, opacity:0.8, marginTop: -20}}>{env?.pm_2_5 ?? '-'} µg/m³</BodyText>
        </ValueBlock>
      </div>
      <AirQualityAlertModal aqi={env?.air_quality} isDark={isDark} />
    </Column>
  );
}