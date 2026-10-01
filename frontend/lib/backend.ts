export const BACKEND_URL = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

export function backendHeaders(incoming?: Headers): Headers {
  const headers = new Headers();
  headers.set("x-janus-internal-token", process.env.JANUS_INTERNAL_TOKEN ?? "");
  for (const name of ["content-type", "accept"]) {
    const value = incoming?.get(name);
    if (value) headers.set(name, value);
  }
  return headers;
}
