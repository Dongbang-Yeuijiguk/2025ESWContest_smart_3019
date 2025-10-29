

import React, {useState, useEffect} from 'react';

const Page = ({children}) => {
  const [scale, setScale] = useState(1);

  useEffect(() => {
    const onResize = () => {
      const vw = Math.max(1, window.innerWidth || document.documentElement.clientWidth);
      const vh = Math.max(1, window.innerHeight || document.documentElement.clientHeight);
      const s = (vw === 1024 && vh === 600) ? 1 : Math.min(vw / 1024, vh / 600);
      setScale(s);
    };
    onResize();
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, []);

  return (
    <div style={{
      width: '100vw',
      height: '100vh',
      margin: 0,
      padding: 0,
      overflow: 'hidden',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      background: '#fdfdfdff'
    }}>
      <div style={{
        width: 1024,
        height: 600,
        transform: `scale(${scale})`,
        transformOrigin: 'center center',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'flex-start',
        background: `linear-gradient(180deg, #fafbfd, rgba(165,0,52,0.06))`,
        borderRadius: 0,
        overflow: 'hidden'
      }}>
        <div style={{
          width: '100%',
          height: '100%',
          padding: '12px 24px 24px',
          boxSizing: 'border-box'
        }}>
          {children}
        </div>
      </div>
    </div>
  );
};

export default Page;