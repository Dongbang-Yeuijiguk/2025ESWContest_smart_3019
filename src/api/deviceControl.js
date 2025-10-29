const API_BASE = process.env.VITE_API_URL || '';

/** 공통 전송 함수 */
export async function sendDeviceCommand(command) {
  const res = await fetch(`${API_BASE}/api/v1/dashboard/control/device`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(command)
  });
  if (!res.ok) {
    const txt = await res.text().catch(() => '');
    throw new Error(`[Device API] ${res.status} ${res.statusText} ${txt}`);
  }
  try { return await res.json(); } catch { return { ok: true }; }
}

/* -----------------------------
 * 에어컨 (AC)
 * --------------------------- */

// 한국어 라벨 → API 모드 매핑
const AC_MODE_MAP = {
  '미약': 'breeze',
  '약': 'low',
  '중': 'medium',
  '강': 'high',
  '파워': 'turbo',
  '자동': 'auto'
};

/** 에어컨 전원 on/off */
export function setACPower(on) {
  return sendDeviceCommand({
    device_type: 'ac',
    payload: { ac_power: on ? 'on' : 'off' }
  });
}

/** 에어컨 온도 설정 (정수/실수 모두 허용) */
export function setACTemperature(temp) {
  const value = Number(temp);
  if (Number.isNaN(value)) throw new Error('온도는 숫자여야 합니다.');
  return sendDeviceCommand({
    device_type: 'ac',
    payload: { target_ac_temperature: value }
  });
}

/** 에어컨 바람 세기(모드) 설정 */
export function setACMode(modeLabel) {
  const normalized = AC_MODE_MAP[modeLabel] || modeLabel.toLowerCase();
  return sendDeviceCommand({
    device_type: 'ac',
    payload: { target_ac_mode: normalized }
  });
}

/* -----------------------------
 * 조명 (Light)
 * --------------------------- */

/** 조명 전원 on/off */
export function setLightPower(on) {
  return sendDeviceCommand({
    device_type: 'light',
    payload: { light_power: on ? 'on' : 'off' }
  });
}

/** 조명 밝기 설정 (0~100) */
export function setLightLevel(level) {
  const value = Number(level);
  if (Number.isNaN(value) || value < 0 || value > 100) {
    throw new Error('조명 밝기는 0~100 사이 숫자여야 합니다.');
  }
  return sendDeviceCommand({
    device_type: 'light',
    payload: { target_light_level: value }
  });
}

/** 조명 색온도 설정 (Kelvin 단위, 예: 2700~6500) */
export function setLightTemperature(kelvin) {
  const value = Number(kelvin);
  if (Number.isNaN(value)) throw new Error('조명 색온도는 숫자여야 합니다.');
  return sendDeviceCommand({
    device_type: 'light',
    payload: { light_temperature: value }
  });
}

/* -----------------------------
 * 커튼 (Curtain)
 * --------------------------- */

/** 커튼 열림/닫힘 제어 (on = 닫힘, off = 열림) */
export function setCurtain(state /* 'on' | 'off' */) {
  if (state !== 'on' && state !== 'off') {
    throw new Error('커튼 상태는 on 또는 off 여야 합니다.');
  }

  // on = 닫힘, off = 열림 (서버 프로토콜 맞춤)
  const payloadState = state;

  return sendDeviceCommand({
    device_type: 'curtain',
    payload: { curtain: payloadState }
  });
}

/* -----------------------------
 * 공기청정기 (Air Purifier, AP)
 * --------------------------- */


/** 공기청정기 전원 on/off */
export function setAPPower(on) {
  return sendDeviceCommand({
    device_type: 'ap',
    payload: { ap_power: on ? 'on' : 'off' }
  });
}

/** 공기청정기 모드 설정 (예: auto, low, medium, high, turbo 등) */
export function setAPMode(mode) {
  return sendDeviceCommand({
    device_type: 'ap',
    payload: { target_ap_mode: mode }
  });
}

/** 공기청정기 상태 전송 (전원 + 모드) */
export function setAPState(on, mode) {
  return sendDeviceCommand({
    device_type: 'ap',
    payload: {
      ap_power: on ? 'on' : 'off',
      target_ap_mode: mode
    }
  });
}