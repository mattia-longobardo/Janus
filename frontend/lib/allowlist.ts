export function isAllowed(email: string | null | undefined, allowlist: string = process.env.JANUS_ALLOWED_EMAILS ?? ""): boolean {
  const allowed = allowlist
    .split(",")
    .map((entry) => entry.trim().toLowerCase())
    .filter(Boolean);
  if (allowed.length === 0) return false;
  return Boolean(email) && allowed.includes(String(email).toLowerCase());
}
