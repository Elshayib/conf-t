import { REVIEW_INTERVALS_DAYS } from "./types";
import { addDays, utcNow, utcNowIso } from "./time";

export { REVIEW_INTERVALS_DAYS };

/** Days offset for a review level (clamped to interval table). */
export function reviewIntervalDays(level: number): number {
  const clamped = Math.min(Math.max(level, 0), REVIEW_INTERVALS_DAYS.length - 1);
  return REVIEW_INTERVALS_DAYS[clamped];
}

/** ISO timestamp when a review at the given level becomes due. */
export function reviewDueAtIso(level: number): string {
  const days = reviewIntervalDays(level);
  const dueAt = days === 0 ? utcNow() : addDays(utcNow(), days);
  return dueAt.toISOString().slice(0, 19) + "+00:00";
}