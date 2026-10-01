export const DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

export function hasDay(mask: number, index: number): boolean {
  return (mask & (1 << index)) !== 0;
}

export function toggleDay(mask: number, index: number): number {
  return mask ^ (1 << index);
}

export function describeDays(mask: number): string {
  if (mask === 127) return "Every day";
  if (mask === 31) return "Weekdays";
  if (mask === 96) return "Weekends";
  return DAY_NAMES.filter((_, i) => hasDay(mask, i)).join(", ") || "Never";
}
