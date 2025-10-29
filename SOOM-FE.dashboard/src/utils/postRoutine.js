const FINAL_API_BASE = import.meta?.env?.FINAL_API_BASE

export async function postRoutine(payload) {
  const base =
    typeof window !== 'undefined' && window.__API_BASE
      ? String(window.__API_BASE).replace(/\/$/, '')
      : FINAL_API_BASE;
  const url = `${base}/api/v1/routine/create`;

  const two = (n) => String(n).padStart(2, '0');
  const fanToMode = (label = '') => {
    const map = {
      '미약': 'breeze', 'breeze': 'breeze',
      '약': 'low', 'low': 'low',
      '중': 'medium', 'mid': 'medium', 'medium': 'medium',
      '강': 'high', 'high': 'high',
      '파워': 'power', 'power': 'power',
      '자동': 'auto', 'auto': 'auto'
    };
    const key = (label && label.toLowerCase) ? label.toLowerCase() : label;
    return map[key] || 'auto';
  };

  // Normalize status from various forms to 'on' | 'off'
  const toOnOff = (v, fallback = 'off') => {
    if (v === 'on') return 'enroll';
    if (v === 'off') return 'pause';
    if (typeof v === 'boolean') return v ? 'enroll' : 'pause';
    return fallback;
  };

  const buildBody = (type, r) => {
    const dev = r?.devices || {};
    const ac = dev.ac || {};
    const ap = dev.ap || {};
    const lt = dev.lighting || {};
    const ct = dev.curtains || {};
    const hh = two(Number(r?.time?.hour) || 0);
    const mm = two(Number(r?.time?.minute) || 0);

    return {
      routine_type: type,
      status: toOnOff(r?.status, toOnOff(r?.enabled, 'off')),
      set_time: `${hh}:${mm}:${String(new Date().getSeconds()).padStart(2, '0')}.${String(new Date().getMilliseconds()).padStart(3, '0')}`,
      alarm_type: r?.alarm ? 'on' : 'off',
      recall: r?.alarm ? (Number(r?.retryMin) || 0) : 0,
      ac_power: ac.power ? 'on' : 'off',
      target_ac_temperature: Number(ac.temp ?? r?.temp) || 24,
      target_ac_mode: fanToMode(ac.fan),
      ap_power: ap.power ? 'on' : 'off',
      target_ap_mode: (ap.mode || 'AUTO').toString().toLowerCase(),
      light_power: (Number(lt.brightness) || 0) > 0 ? 'on' : 'off',
      light_temperature: Number(lt.cct) || undefined,
      target_light_level: Number(lt.brightness) || 0,
      curtain: (ct.state === 'on' ? 'on' : 'off')
    };
  };

  try {
    if (payload?.routine?.wake) {
      await fetch(url, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(buildBody('wake', payload.routine.wake))
      });
    }
    if (payload?.routine?.sleep) {
      await fetch(url, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(buildBody('sleep', payload.routine.sleep))
      });
    }
  } catch (e) {
    console.error('[RoutineSave] POST failed', e);
  }
}