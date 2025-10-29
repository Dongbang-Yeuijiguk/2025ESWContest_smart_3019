/* eslint-env browser */
import {useState, useEffect, useRef} from 'react';

// Robust WebSocket detection (browser-only, no self/globalThis)
const WS = (typeof WebSocket !== 'undefined') ? WebSocket
  : (typeof window !== 'undefined' && 'WebSocket' in window) ? window.WebSocket
  : undefined;

// Fallback URL (only used if no env/overrides are present)
const FALLBACK_WS_URL = import.meta?.env?.VITE_ENV_WS_URL

export default function useEnvSocket(url) {
  const [env, setEnv] = useState({
    temperature: 28,
    humidity: 50,
    curtain: null,
    air_quality: 350,
    pm_10: 83,   // 미세먼지 (PM10)
    pm_2_5: 31   // 초미세먼지 (PM2.5)
  });

  const AQI_MAP = {
    VERY_GOOD: '매우 좋음',
    GOOD: '좋음',
    MODERATE: '보통',
    POOR: '나쁨',
    VERY_POOR: '매우 나쁨'
  };

  const reconnectRef = useRef({attempt: 0, timer: null, ws: null});

  useEffect(() => {
    let closedByUser = false;

    const connect = () => {
      if (!WS) {
        // eslint-disable-next-line no-console
        console.warn('[useEnvSocket] WebSocket constructor not found in this environment');
        return;
      }

      const _windowUrl = (typeof window !== 'undefined' && window.__SOOM_ENV__ && window.__SOOM_ENV__.VITE_ENV_WS_URL)
        ? window.__SOOM_ENV__.VITE_ENV_WS_URL
        : undefined;
      const _lsUrl = (typeof window !== 'undefined' && window.localStorage)
        ? window.localStorage.getItem('VITE_ENV_WS_URL')
        : undefined;
      const _viteUrl = (typeof import.meta !== 'undefined' && import.meta.env)
        ? import.meta.env.VITE_ENV_WS_URL
        : undefined;

      const finalUrl = url || _windowUrl || _lsUrl || _viteUrl || FALLBACK_WS_URL;

      // Avoid mixed-content blocks: if page is https but URL is ws://, upgrade to wss://
      let connectUrl = finalUrl;
      try {
        if (typeof window !== 'undefined' && window.location && window.location.protocol === 'https:' && /^ws:\/\//i.test(connectUrl)) {
          connectUrl = connectUrl.replace(/^ws:\/\//i, 'wss://');
        }
      } catch (_) {}

      const ws = new WS(connectUrl);
      reconnectRef.current.ws = ws;

      ws.onopen = () => {
        if (reconnectRef.current.timer) {
          clearTimeout(reconnectRef.current.timer);
          reconnectRef.current.timer = null;
        }
        reconnectRef.current.attempt = 0;
      };

      ws.onmessage = (evt) => {
        try {
          const raw = JSON.parse(evt.data);
          setEnv(prev => ({
            temperature: raw.temperature ?? prev.temperature,
            humidity: raw.humidity ?? prev.humidity,
            curtain: raw.curtain ?? prev.curtain,
            // Keep air_quality as raw numeric value (handled later in EnvCard.js)
            air_quality: Number(raw.air_quality ?? prev.air_quality),
            pm_10: Number(raw.pm_10 ?? prev.pm_10),
            pm_2_5: Number(raw.pm_2_5 ?? prev.pm_2_5)
          }));
        } catch (_) {}
      };

      ws.onclose = () => {
        if (closedByUser) return;
        const attempt = Math.min(6, reconnectRef.current.attempt + 1);
        reconnectRef.current.attempt = attempt;
        const delay = Math.round(500 * Math.pow(2, attempt));
        reconnectRef.current.timer = setTimeout(connect, delay);
      };

      ws.onerror = () => {
        try { ws.close(); } catch (_) {}
      };
    };

    connect();

    return () => {
      closedByUser = true;
      if (reconnectRef.current.timer) clearTimeout(reconnectRef.current.timer);
      if (reconnectRef.current.ws && WS && reconnectRef.current.ws.readyState === WS.OPEN) {
        reconnectRef.current.ws.close();
      }
    };
  }, [url]);

  return env;
}