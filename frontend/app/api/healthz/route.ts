import { BACKEND_URL } from "@/lib/backend";

export const dynamic = "force-dynamic";

export async function GET(): Promise<Response> {
  try {
    const upstream = await fetch(new URL("/api/health", BACKEND_URL), { cache: "no-store" });
    return Response.json({ status: upstream.ok ? "ok" : "degraded" }, { status: upstream.ok ? 200 : 503 });
  } catch {
    return Response.json({ status: "down" }, { status: 503 });
  }
}
