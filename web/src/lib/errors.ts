const OFFLINE_CODES = new Set([
  "unavailable",
  "failed-precondition",
  "network-request-failed",
]);

const OFFLINE_MESSAGES = [
  "network",
  "offline",
  "fetch failed",
  "failed to fetch",
  "internet",
];

export function isOfflineError(error: unknown): boolean {
  if (typeof navigator !== "undefined" && !navigator.onLine) {
    return true;
  }

  if (!error) {
    return false;
  }

  if (error instanceof TypeError && /fetch|network/i.test(error.message)) {
    return true;
  }

  if (typeof error === "object" && error !== null) {
    const code =
      "code" in error && typeof error.code === "string"
        ? error.code.toLowerCase()
        : "";

    if (OFFLINE_CODES.has(code) || code.includes("network")) {
      return true;
    }

    const message =
      "message" in error && typeof error.message === "string"
        ? error.message.toLowerCase()
        : "";

    if (OFFLINE_MESSAGES.some((fragment) => message.includes(fragment))) {
      return true;
    }
  }

  return false;
}

export function getFirebaseErrorMessage(error: unknown): string {
  if (isOfflineError(error)) {
    return "You appear to be offline. Check your connection and try again.";
  }

  if (
    error &&
    typeof error === "object" &&
    "code" in error &&
    typeof error.code === "string"
  ) {
    switch (error.code) {
      case "permission-denied":
        return "You do not have permission to access this data.";
      case "not-found":
        return "Requested data was not found.";
      case "unauthenticated":
        return "Your session expired. Please sign in again.";
      default:
        break;
    }
  }

  if (error instanceof Error && error.message) {
    return error.message;
  }

  return "Something went wrong. Please try again.";
}

export function getLessonLoadErrorMessage(error: unknown): string {
  if (isOfflineError(error)) {
    return "Could not load lessons while offline. Reconnect and retry.";
  }

  return "Failed to load lessons. Please refresh the page.";
}

export function getAuthErrorMessage(error: unknown): string {
  if (isOfflineError(error)) {
    return "Sign-in requires an internet connection.";
  }

  if (
    error &&
    typeof error === "object" &&
    "code" in error &&
    typeof error.code === "string"
  ) {
    switch (error.code) {
      case "auth/invalid-email":
        return "Invalid email address.";
      case "auth/user-disabled":
        return "This account has been disabled.";
      case "auth/user-not-found":
      case "auth/wrong-password":
      case "auth/invalid-credential":
        return "Invalid email or password.";
      case "auth/too-many-requests":
        return "Too many attempts. Try again later.";
      case "auth/popup-closed-by-user":
        return "Sign-in popup was closed.";
      case "auth/network-request-failed":
        return "Network error during sign-in. Check your connection.";
      case "auth/email-already-in-use":
        return "An account with this email already exists.";
      case "auth/weak-password":
        return "Password is too weak. Use at least 6 characters.";
      default:
        break;
    }
  }

  return "Authentication failed. Please try again.";
}