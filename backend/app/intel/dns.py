from collections import Counter
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

BLOCKED = {"GRAVITY", "REGEX", "DENYLIST", "GRAVITY_CNAME", "REGEX_CNAME", "DENYLIST_CNAME", "SPECIAL_DOMAIN",
           "EXTERNAL_BLOCKED_IP", "EXTERNAL_BLOCKED_NULL", "EXTERNAL_BLOCKED_NXRA", "EXTERNAL_BLOCKED_EDE15"}
SECOND_LEVEL = {"co", "com", "net", "org", "gov", "edu", "ac", "ne", "or", "go"}
TOP_DOMAINS = 200
TOP_BLOCKED = 50


def is_blocked(query: dict[str, Any]) -> bool:
    return query.get("status") in BLOCKED


def base_domain(domain: str) -> str:
    labels = [label for label in domain.lower().rstrip(".").split(".") if label]
    if len(labels) <= 2:
        return ".".join(labels)
    if len(labels[-1]) == 2 and labels[-2] in SECOND_LEVEL:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:])


def bucket_seconds(hours: int) -> int:
    return 600 if hours <= 6 else 3600


def _iso(ts: float, tz: ZoneInfo) -> str:
    return datetime.fromtimestamp(ts, tz).isoformat()


def analyze(queries: list[dict[str, Any]], total: int, since: int, until: int, hours: int, tz: ZoneInfo) -> dict[str, Any]:
    step = bucket_seconds(hours)
    first = since - since % step
    buckets = [{"start": _iso(start, tz), "total": 0, "blocked": 0} for start in range(first, until, step)]
    domains: Counter[str] = Counter()
    blocked_domains: Counter[str] = Counter()
    bases: Counter[str] = Counter()
    last_seen: dict[str, float] = {}
    types: Counter[str] = Counter()
    statuses: Counter[str] = Counter()
    replies: Counter[str] = Counter()
    blocked = 0
    for query in queries:
        domain = str(query.get("domain") or "")
        ts = float(query.get("time") or 0)
        hit = is_blocked(query)
        blocked += hit
        domains[domain] += 1
        bases[base_domain(domain)] += 1
        if hit:
            blocked_domains[domain] += 1
        last_seen[domain] = max(last_seen.get(domain, 0.0), ts)
        types[str(query.get("type") or "UNKNOWN")] += 1
        statuses[str(query.get("status") or "UNKNOWN")] += 1
        reply = query.get("reply")
        if isinstance(reply, dict) and reply.get("type"):
            replies[str(reply["type"])] += 1
        index = int((ts - first) // step)
        if 0 <= index < len(buckets):
            buckets[index]["total"] += 1
            buckets[index]["blocked"] += hit
    sampled = len(queries)
    return {
        "hours": hours,
        "bucket_seconds": step,
        "totals": {
            "total": total,
            "sampled": sampled,
            "truncated": total > sampled,
            "blocked": blocked,
            "blocked_pct": round(blocked * 100 / sampled, 1) if sampled else 0.0,
            "unique_domains": len(domains),
        },
        "timeline": buckets,
        "domains": [
            {"domain": d, "base": base_domain(d), "count": n, "blocked": blocked_domains[d] > 0,
             "last_seen": _iso(last_seen[d], tz) if last_seen[d] else None}
            for d, n in domains.most_common(TOP_DOMAINS)
        ],
        "blocked_domains": [{"domain": d, "count": n} for d, n in blocked_domains.most_common(TOP_BLOCKED)],
        "base_domains": [{"domain": d, "count": n} for d, n in bases.most_common(50)],
        "query_types": [{"type": t, "count": n} for t, n in types.most_common()],
        "statuses": [{"status": s, "count": n, "blocked": s in BLOCKED} for s, n in statuses.most_common()],
        "replies": [{"type": r, "count": n} for r, n in replies.most_common()],
    }
