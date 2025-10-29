// src/theme/ThemeContext.js
import {createContext, useContext, useEffect, useMemo, useState} from 'react';

const ThemeContext = createContext({mode: 'dark', toggleTheme: () => {}});

export const ThemeProvider = ({children, initial = 'dark'}) => {
  const [mode, setMode] = useState(initial); // 'dark' | 'light'

  // body data-theme 적용 (전역 배경/텍스트 톤)
  useEffect(() => {
    document.body.setAttribute('data-theme', mode);
  }, [mode]);

  const value = useMemo(() => ({
    mode,
    toggleTheme: () => setMode(m => (m === 'dark' ? 'light' : 'dark'))
  }), [mode]);

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
};

export const useTheme = () => useContext(ThemeContext);