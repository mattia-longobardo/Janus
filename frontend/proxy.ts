import { NextResponse } from "next/server";

import { auth } from "@/auth";

export const proxy = auth((req) => {
  if (req.auth) return NextResponse.next();
  if (req.nextUrl.pathname.startsWith("/api/")) {
    return NextResponse.json({ detail: "not signed in" }, { status: 401 });
  }
  const login = new URL("/login", req.nextUrl.origin);
  login.searchParams.set("callbackUrl", `${req.nextUrl.pathname}${req.nextUrl.search}`);
  return NextResponse.redirect(login);
});

export const config = {
  matcher: ["/((?!api/auth|api/healthz|login|_next/static|_next/image|favicon.ico|icon.svg|robots.txt).*)"],
};
