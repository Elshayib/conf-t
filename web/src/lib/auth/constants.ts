export const AUTH_COOKIE = "conf_t_auth";

export function setAuthCookie(isAuthenticated: boolean): void {
  if (typeof document === "undefined") {
    return;
  }

  if (isAuthenticated) {
    document.cookie = `${AUTH_COOKIE}=1; path=/; max-age=604800; SameSite=Lax`;
    return;
  }

  document.cookie = `${AUTH_COOKIE}=; path=/; max-age=0; SameSite=Lax`;
}