import { auth } from "@/auth";
import { BACKEND_URL } from "@/lib/backend";
import { forward } from "@/lib/proxy";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

async function handle(req: Request, context: { params: Promise<{ path: string[] }> }): Promise<Response> {
  const session = await auth();
  const { path } = await context.params;
  const allowedOrigins = [new URL(req.url).origin, process.env.AUTH_URL].filter((value): value is string => Boolean(value));
  return forward(req, path, { signedIn: Boolean(session?.user), backend: BACKEND_URL, allowedOrigins });
}

export { handle as DELETE, handle as GET, handle as PATCH, handle as POST, handle as PUT };
