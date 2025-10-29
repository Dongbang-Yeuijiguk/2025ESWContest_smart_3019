import React, { useEffect, useRef } from 'react';

// LG style tokens (local fallback — replace if you have a global tokens file)
const LG_BRAND = {
  red: '#A50034',
  borderLight: 'rgba(0,0,0,0.08)',
  shadow: '0 10px 28px rgba(0,0,0,0.12)'
};

/**
 * BaseModal
 * - A11y: role="dialog", aria-modal, ESC to close, backdrop click to close
 * - Focus management: focus trap to the modal content on open; restore on close
 * - Scroll lock: prevent body scroll while open
 */
export default function BaseModal({
  open,
  title,
  onClose,
  children,
  width = 560,
  maxWidth = '96vw',
  height,
  isDark = false,
  footer = null,
  hideClose = false,
}) {
  const dialogRef = useRef(null);
  const lastActiveRef = useRef(null);

  // Scroll lock & focus restore
  useEffect(() => {
    if (!open) return;
    lastActiveRef.current = document.activeElement;
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const t = setTimeout(() => {
      dialogRef.current?.focus();
    }, 0);
    return () => {
      document.body.style.overflow = prevOverflow;
      clearTimeout(t);
      if (lastActiveRef.current && typeof lastActiveRef.current.focus === 'function') {
        lastActiveRef.current.focus();
      }
    };
  }, [open]);

  // ESC close
  useEffect(() => {
    if (!open) return;
    const onKey = (e) => {
      if (e.key === 'Escape') onClose?.();
      // rudimentary focus trap
      if (e.key === 'Tab' && dialogRef.current) {
        const focusables = dialogRef.current.querySelectorAll(
          'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
        );
        if (focusables.length === 0) return;
        const first = focusables[0];
        const last = focusables[focusables.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  if (!open) return null;

  const stop = (e) => e.stopPropagation();
  const headerId = 'modal-title-' + Math.random().toString(36).slice(2, 8);

  return (
    <div
      onClick={onClose}
      style={{
        position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.45)',
        display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000
      }}
      aria-hidden={!open}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby={headerId}
        tabIndex={-1}
        ref={dialogRef}
        onClick={stop}
        style={{
          width, maxWidth,
          height: height || 'auto', maxHeight: '90vh', overflow: 'auto',
          background: isDark ? '#1b1b1b' : '#fff', borderRadius: 12,
          border: isDark ? '1px solid rgba(255,255,255,0.10)' : `1px solid ${LG_BRAND.borderLight}`,
          boxShadow: isDark ? '0 3px 10px rgba(0,0,0,0.60)' : '0 3px 10px rgba(0,0,0,0.12)',
          color: isDark ? '#F3F4F6' : '#111',
        }}
      >
        {/* Header */}
        <div style={{
          position:'sticky', top:0, background: isDark ? '#1b1b1b' : '#fff',
          padding: '10px 12px', borderBottom: isDark ? '1px solid rgba(255,255,255,0.10)' : `1px solid ${LG_BRAND.borderLight}`,
          display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8
        }}>
          <div id={headerId} style={{fontSize: 18, fontWeight: 900, color: isDark ? '#F3F4F6' : '#111', lineHeight: 1}}>{title}</div>
          {!hideClose && (
            <button
              onClick={onClose}
              style={{
                border: `1.5px solid ${LG_BRAND.red}`,
                color: LG_BRAND.red,
                background: 'transparent',
                borderRadius: 999,
                padding: '6px 10px',
                fontWeight: 900,
                fontSize: 14,
                cursor: 'pointer'
              }}
              aria-label="닫기"
            >
              닫기
            </button>
          )}
        </div>

        {/* Body */}
        <div style={{ padding: 12 }}>
          {children}
        </div>

        {/* Footer */}
        {footer && (
          <div style={{
            position:'sticky', bottom:0, background: isDark ? '#1b1b1b' : '#fff',
            padding: '10px 12px',
            borderTop: isDark ? '1px solid rgba(255,255,255,0.10)' : `1px solid ${LG_BRAND.borderLight}`
          }}>
            {footer}
          </div>
        )}
      </div>
    </div>
  );
}