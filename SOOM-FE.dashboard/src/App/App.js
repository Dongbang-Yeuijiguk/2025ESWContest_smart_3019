// src/App/App.js
import React, {useEffect, useState, useCallback, useRef} from 'react';
import ThemeDecorator from '@enact/sandstone/ThemeDecorator';

import Dashboard from '../views/Dashboard';
import SleepReport from '../views/SleepReport';
// -------- Error Boundary to surface runtime errors instead of blank screen --------
class AppErrorBoundary extends React.Component {
  constructor(props){
    super(props);
    this.state = {error:null};
  }
  static getDerivedStateFromError(error){
    return {error};
  }
  componentDidCatch(error, info){
    // eslint-disable-next-line no-console
    console.error('App crashed:', error, info);
  }
  render(){
    if(this.state.error){
      return (
        <div style={{padding:16, color:'#fff'}}>
          <h3>앱 오류가 발생했습니다</h3>
          <pre style={{whiteSpace:'pre-wrap'}}>{String(this.state.error)}</pre>
        </div>
      );
    }
    return this.props.children;
  }
}

// ---- Minimal hash router (no react-router) -------------------------------------
const getPath = () => {
  const h = (typeof window !== 'undefined' && window.location && window.location.hash) ? window.location.hash : '';
  // normalize like `#/sleep-report` or `#/`
  if (!h || h === '#' || h === '') return '/';
  return h.replace(/^#/, '');
};

const App = () => {
  const [path, setPath] = useState(getPath());
  const [isDark, setIsDark] = useState(false);
  const wrapRef = useRef(null);
  const [dbg, setDbg] = useState({vw:0, vh:0, iw:0, ih:0, dpr:1});

  useEffect(() => {
    const onHashChange = () => setPath(getPath());
    window.addEventListener('hashchange', onHashChange);
    return () => window.removeEventListener('hashchange', onHashChange);
  }, []);

      useEffect(() => {
    function fit() {
      const el = wrapRef.current;
      if (!el) return;

      const baseW = 1024, baseH = 600;
      const vw = Math.round(window.innerWidth);
      const vh = Math.round(window.innerHeight);

      // 전체가 보이도록 '축소만' 허용 (확대 금지)
      const raw = Math.min(vw / baseW, vh / baseH);
      const scale = raw > 1 ? 1 : raw;

      // 좌상단에 고정 배치
      el.style.left = '0px';
      el.style.top  = '0px';
      el.style.transform = scale === 1 ? 'none' : `scale(${scale})`;
    }
    fit();
    window.addEventListener('resize', fit);
    const tick = () => {
      const vw = Math.round(window.visualViewport ? window.visualViewport.width  : window.innerWidth);
      const vh = Math.round(window.visualViewport ? window.visualViewport.height : window.innerHeight);
      setDbg({vw, vh, iw: window.innerWidth, ih: window.innerHeight, dpr: Number(window.devicePixelRatio || 1)});
    };
    tick();
    window.addEventListener('resize', tick);
    return () => {
      window.removeEventListener('resize', tick);
      window.removeEventListener('resize', fit);
    };
  }, []);

  // navigation helpers
  const goHome = useCallback(() => { window.location.hash = '/'; }, []);
  const goSleep = useCallback(() => { window.location.hash = '/sleep-report'; }, []);

  // eslint-disable-next-line no-console
  console.log('Render <App /> path:', path);

  return (
    <AppErrorBoundary>
      {/* Fullscreen stage */}
      <div style={{position:'fixed', inset:0, width:'100vw', height:'100vh', overflow:'hidden', background: isDark ? '#0f1012' : '#fafbfd', color: isDark ? '#F3F4F6' : '#111'}}>
        {/* Fixed-size canvas that we scale & center */}
        <div ref={wrapRef} style={{position:'absolute', width:1024, height:600, transformOrigin:'top left'}}>
          <button
            onClick={() => setIsDark(v => !v)}
            style={{position:'absolute', top: 6, right: 8, padding:'4px 8px', fontSize:12, borderRadius:6, border: '1px solid rgba(0,0,0,0.2)', background: isDark ? '#1b1b1b' : '#ffffff', color: isDark ? '#E5E7EB' : '#111'}}
            aria-label="Toggle dark mode"
          >{isDark ? 'Dark' : 'Light'}</button>
          {path === '/sleep-report' ? (
            // SleepReport page (no Sandstone Header to avoid dependency)
            <div style={{display:'flex', flexDirection:'column', width:1024, height:600, overflow:'hidden'}}>
              <div style={{display:'flex', alignItems:'center', gap:8, padding:'8px 12px', borderBottom: isDark ? '1px solid rgba(255,255,255,0.08)' : '1px solid rgba(0,0,0,0.06)'}}>
                <button onClick={goHome} style={{fontSize:14, color: isDark ? '#E5E7EB' : '#111'}}>←</button>
                <div style={{fontSize:14, fontWeight:700, color: isDark ? '#F3F4F6' : '#111'}}>수면 리포트</div>
              </div>
              <div style={{flex:1, overflow:'auto', maxHeight:'calc(600px - 48px)', background: isDark ? '#0f1012' : '#fafbfd', color: isDark ? '#F3F4F6' : '#111'}}>
                <SleepReport isDark={isDark} />
              </div>
            </div>
          ) : (
            // Dashboard page
            <Dashboard isDark={isDark} onGo={goSleep} onGoSleep={goSleep} />
          )}
        </div>
      </div>
    </AppErrorBoundary>
  );
};

export default ThemeDecorator(App);