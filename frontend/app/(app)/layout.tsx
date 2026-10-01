import { redirect } from "next/navigation";
import type { ReactNode } from "react";

import { auth } from "@/auth";
import { Shell } from "@/components/shell";

export default async function AppLayout({ children }: { children: ReactNode }) {
  const session = await auth();
  if (!session?.user) redirect("/login");
  return <Shell user={session.user.name ?? session.user.email ?? "signed in"}>{children}</Shell>;
}
