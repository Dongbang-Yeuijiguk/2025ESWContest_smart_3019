// src/index.js
import {createRoot} from 'react-dom/client';
import App from './App';
import {ThemeProvider} from './theme/ThemeContext';
import './theme/global.css';

const container = document.getElementById('root') || document.getElementById('app');
const root = createRoot(container);

root.render(
  <ThemeProvider initial="light">
    <App />
  </ThemeProvider>
);