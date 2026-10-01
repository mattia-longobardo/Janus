import { DAY_NAMES, hasDay } from "@/lib/days";

export const REPEATS = [
  { value: 127, label: "Every day" },
  { value: 31, label: "Weekdays" },
  { value: 96, label: "Weekends" },
] as const;

export function zoneLabel(zone: string, at: Date = new Date()): string {
  try {
    const name = new Intl.DateTimeFormat("en-US", { timeZone: zone, timeZoneName: "longOffset" })
      .formatToParts(at)
      .find((part) => part.type === "timeZoneName")?.value;
    const offset = !name || name === "GMT" ? "+00:00" : name.replace("GMT", "");
    return `${zone} (UTC${offset})`;
  } catch {
    return zone;
  }
}

function localNow(zone: string, at: Date): { day: number; minutes: number } {
  const parts = new Intl.DateTimeFormat("en-US", { timeZone: zone, weekday: "short", hour: "2-digit", minute: "2-digit", hourCycle: "h23" }).formatToParts(at);
  const part = (type: string) => parts.find((p) => p.type === type)?.value ?? "";
  const day = (["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"] as const).indexOf(part("weekday") as "Mon");
  return { day, minutes: Number(part("hour")) * 60 + Number(part("minute")) };
}

export function nextRun(mask: number, start: string, zone: string, at: Date = new Date()): string {
  const [h, m] = start.split(":").map(Number);
  const startMinutes = h * 60 + m;
  const now = localNow(zone, at);
  for (let offset = 0; offset <= 7; offset += 1) {
    const day = (now.day + offset) % 7;
    if (!hasDay(mask, day)) continue;
    if (offset === 0 && startMinutes <= now.minutes) continue;
    const when = offset === 0 ? "today" : offset === 1 ? "tomorrow" : DAY_NAMES[day];
    return `${when} ${start}`;
  }
  return "never";
}
