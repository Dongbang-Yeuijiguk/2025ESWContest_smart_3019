// src/views/Dashboard.js
import Heading from '@enact/sandstone/Heading';
import BodyText from '@enact/sandstone/BodyText';
import SwitchItem from '@enact/sandstone/SwitchItem';
import {Row, Column, Cell} from '@enact/ui/Layout';
import {useTheme} from '../theme/ThemeContext';
import {useState, useMemo, useEffect} from 'react';


import SleepReportCard from './parts/SleepReportCard';
import SleepReport from './SleepReport';
import EnvCard from './parts/EnvCard';
import SmartHomeControlCard from './parts/SmartHomeControlCard';

import useEnvSocket from '../hooks/useEnvSocket';
import Page from '../components/Page';
import '../theme/DashboardTheme.css';

// Typographic scale (tuned for 1024x600 dashboard)
const TYPE = { h1: 24, h2: 18, h3: 16, body: 14, label: 12, tiny: 10 };
const LH = { tight: 1.1, normal: 1.35 };

// LG brand tokens
const LG_BRAND = {
  red: '#A50034',        // LG Red
  pinkTint: 'rgba(165,0,52,0.06)',
  pinkTintStrong: 'rgba(165,0,52,0.12)',
  borderLight: 'rgba(0,0,0,0.08)',
  borderDark: 'rgba(255,255,255,0.12)'
};

const pad2 = (n) => String(n).padStart(2, '0');
const fmtHm = (dateStr) => { const d = new Date(dateStr); return `${pad2(d.getHours())}:${pad2(d.getMinutes())}`; };

const EnvRow = ({label, value, textPrimary, textSecondary}) => (
  <Row
    style={{
      justifyContent: 'space-between',
      alignItems: 'center',
      padding: '14px 8px',
      borderBottom: '1px solid rgba(255,255,255,0.12)',
      minHeight: 48
    }}
  >
    <BodyText style={{fontSize: `${TYPE.label}px`, lineHeight: `${LH.normal}em`, opacity: 0.85, color: textSecondary}}>
      {label}
    </BodyText>
    <BodyText style={{fontSize: `${TYPE.body}px`, lineHeight: `${LH.normal}em`, fontWeight: 700, textAlign: 'right', minWidth: 72, color: textPrimary}}>
      {value}
    </BodyText>
  </Row>
);

export default function Dashboard({onGo = () => {}}) {
  const {mode, toggleTheme} = useTheme();
  const [autoMode, setAutoMode] = useState(true);
  const [showSleepReport, setShowSleepReport] = useState(false);
  const env = useEnvSocket();

  const isDark = mode === 'dark';
  const themeClass = isDark ? 'dashboard-page dashboard-dark' : 'dashboard-page dashboard-light';


  return (
    <Page>
      <div className={themeClass}>
        <Column style={{gap: 10}}>

          {/* 상단 바: 좌측 SOOM, 우측 테마 토글 */}
          <Row className="dashboard-header" style={{justifyContent: 'space-between', alignItems: 'center', marginBottom: -40, marginTop: -24}}>
            <Heading size="large" style={{fontSize: `${TYPE.h1}px`, lineHeight: `${LH.tight}em`, fontWeight: 800}}>SOOM Dashboard</Heading>
            <SwitchItem selected={isDark} onToggle={toggleTheme}>
              {isDark ? '다크 모드' : '라이트 모드'}
            </SwitchItem>
          </Row>

          {/* 수면 리포트 (상태 전환) */}
          {showSleepReport ? (
            <SleepReport onBack={() => setShowSleepReport(false)} />
          ) : (
            <SleepReportCard
              isDark={isDark}
              onGo={() => setShowSleepReport(true)}
            />
          )}

          {!showSleepReport && (
            <Row style={{gap: 24, alignItems: 'stretch'}} wrap>
              {/* 실내 환경 */}
              <div className="dashboard-card" style={{flex: 0.7}}>
                <EnvCard
                  isDark={isDark}
                  env={env}
                  autoMode={autoMode}
                  setAutoMode={setAutoMode}
                />
              </div>

              {/* 스마트홈 제어 */}
              <div className="dashboard-card" style={{flex: 1.3}}>
                <SmartHomeControlCard
                  isDark={isDark}
                  curtainState={env?.curtain}
                />
              </div>
            </Row>
          )}

        </Column>
      </div>
    </Page>
  );
}