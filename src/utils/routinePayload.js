// src/utils/routinePayload.js
export const buildRoutinePayload = ({
  wakeEnabled, wakeHour, wakeMinute, wakeRetryMin, wakeAlarmOn,
  sleepEnabled, sleepHour, sleepMinute, sleepRetryMin, sleepAlarmOn,
  preferredTemp, sleepTemp,
  autoLightingOn, autoCurtainOn, autoACOn, autoPurifierOn
}) => {
  const two = n => String(n).padStart(2,'0');
  const toTime = (h,m) => `${two(h)}:${two(m)}:00`;
  const STATUS = on => (on ? 'ENABLED' : 'DISABLED');

  return {
    wake: {
      routine_type: 'WAKE',
      status: STATUS(wakeEnabled),
      wakeup_time: toTime(wakeHour, wakeMinute),
      recallType: 'minutes',
      recall: wakeAlarmOn ? wakeRetryMin : null,
      ac_power: autoACOn ? 'on':'off',
      target_ac_temperature: preferredTemp,
      ap_power: autoPurifierOn ? 'on':'off',
      light_power: autoLightingOn ? 'on':'off',
      curtain: !!autoCurtainOn
    },
    sleep: {
      routine_type: 'SLEEP',
      status: STATUS(sleepEnabled),
      wakeup_time: toTime(sleepHour, sleepMinute),
      recallType: 'minutes',
      recall: sleepAlarmOn ? sleepRetryMin : null,
      ac_power: autoACOn ? 'on':'off',
      target_ac_temperature: sleepTemp,
      ap_power: autoPurifierOn ? 'on':'off',
      light_power: autoLightingOn ? 'on':'off',
      curtain: !!autoCurtainOn
    }
  };
};