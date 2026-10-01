import { redirect } from "next/navigation";
import type { ReactNode } from "react";

import { auth } from "@/auth";
import { Shell } from "@/components/shell";
import { isAllowed } from "@/lib/allowlist";

export default async function AppLayout({ children }: { children: ReactNode }) {
  const session = await auth();
  if (!session?.user || !isAllowed(session.user.email)) redirect("/login?error=AccessDenied");
  return <Shell user={session.user.name ?? session.user.email ?? "signed in"}>{children}</Shell>;
}
