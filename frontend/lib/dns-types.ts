export interface DnsBucket {
  start: string;
  total: number;
  blocked: number;
}

export interface DnsDomainRow {
  domain: string;
  base: string;
  count: number;
  blocked: boolean;
  last_seen: string | null;
}

export interface DnsAnalysis {
  hours: number;
  bucket_seconds: number;
  totals: {
    total: number;
    sampled: number;
    truncated: boolean;
    blocked: number;
    blocked_pct: number;
    unique_domains: number;
  };
  timeline: DnsBucket[];
  domains: DnsDomainRow[];
  blocked_domains: { domain: string; count: number }[];
  base_domains: { domain: string; count: number }[];
  query_types: { type: string; count: number }[];
  statuses: { status: string; count: number; blocked: boolean }[];
  replies: { type: string; count: number }[];
}

export type DomainSortKey = "domain" | "base" | "count" | "last_seen";

export function sortDomains(rows: DnsDomainRow[], key: DomainSortKey, dir: "asc" | "desc"): DnsDomainRow[] {
  const sign = dir === "asc" ? 1 : -1;
  const compare: Record<DomainSortKey, (a: DnsDomainRow, b: DnsDomainRow) => number> = {
    domain: (a, b) => a.domain.localeCompare(b.domain),
    base: (a, b) => a.base.localeCompare(b.base) || a.domain.localeCompare(b.domain),
    count: (a, b) => a.count - b.count,
    last_seen: (a, b) => Date.parse(a.last_seen ?? "1970-01-01") - Date.parse(b.last_seen ?? "1970-01-01"),
  };
  return [...rows].sort((a, b) => sign * compare[key](a, b) || b.count - a.count);
}

export function filterDomains(rows: DnsDomainRow[], query: string, onlyBlocked: boolean): DnsDomainRow[] {
  const q = query.trim().toLowerCase();
  return rows.filter((r) => (!onlyBlocked || r.blocked) && (!q || r.domain.toLowerCase().includes(q)));
}

export function busiest(timeline: DnsBucket[]): DnsBucket | null {
  return timeline.reduce<DnsBucket | null>((best, b) => (b.total > 0 && (!best || b.total > best.total) ? b : best), null);
}
