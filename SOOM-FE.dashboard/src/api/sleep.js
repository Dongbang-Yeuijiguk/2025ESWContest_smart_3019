export const SLEEP_REPORT_ENDPOINT =
  process.env.REACT_APP_SLEEP_REPORT_ENDPOINT || '/api/v1/dashboard/sleep/report';

export async function fetchSleepReport(dateISO) {
  const date = dateISO || new Date().toISOString().slice(0,10); // YYYY-MM-DD
  const url = `${SLEEP_REPORT_ENDPOINT}/report/${encodeURIComponent(date)}`;
  const res = await fetch(url, {method: 'GET'});
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return await res.json();
}