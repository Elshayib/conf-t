/** UTC helpers mirroring conf_t/engine.py _utc_now_iso / _parse_iso_datetime */

export function utcNowIso(): string {
  const d = new Date();
  d.setMilliseconds(0);
  return d.toISOString().slice(0, 19) + "+00:00";
}

export function utcNow(): Date {
  const d = new Date();
  d.setMilliseconds(0);
  return d;
}

export function parseIsoDatetime(value: string): Date {
  return new Date(value.replace("Z", "+00:00"));
}

export function addDays(date: Date, days: number): Date {
  const result = new Date(date.getTime());
  result.setUTCDate(result.getUTCDate() + days);
  result.setMilliseconds(0);
  return result;
}