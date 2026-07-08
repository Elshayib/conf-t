import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { AUTH_COOKIE } from "@/lib/auth/constants";

const PROTECTED_PREFIXES = [
  "/dashboard",
  "/practice",
  "/review",
  "/stats",
  "/settings",
  "/lessons/create",
  "/onboarding",
] as const;

function isProtectedPath(pathname: string): boolean {
  return PROTECTED_PREFIXES.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`)
  );
}

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  if (!isProtectedPath(pathname)) {
    return NextResponse.next();
  }

  const hasAuthCookie = request.cookies.get(AUTH_COOKIE)?.value === "1";

  if (!hasAuthCookie) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("redirect", pathname);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    "/dashboard/:path*",
    "/practice/:path*",
    "/review/:path*",
    "/stats/:path*",
    "/settings/:path*",
    "/lessons/create/:path*",
    "/onboarding/:path*",
  ],
};