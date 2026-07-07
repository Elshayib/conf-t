"use client";

import { useEffect, useState } from "react";
import { onAuthStateChanged, type User } from "firebase/auth";
import { getClientAuth } from "@/lib/firebase/config";
import { setAuthCookie } from "@/lib/auth/constants";

export function useAuth() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(getClientAuth(), (firebaseUser) => {
      setUser(firebaseUser);
      setAuthCookie(!!firebaseUser);
      setLoading(false);
    });

    return unsubscribe;
  }, []);

  return { user, loading };
}