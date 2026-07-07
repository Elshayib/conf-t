"use client";

import { initializeApp, getApps, type FirebaseApp } from "firebase/app";
import { getAuth, type Auth } from "firebase/auth";
import { getFirestore, type Firestore } from "firebase/firestore";

const firebaseConfig = {
  apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY!,
  authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN!,
  projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID!,
  storageBucket: process.env.NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET!,
  messagingSenderId: process.env.NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID!,
  appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID!,
};

let firebaseApp: FirebaseApp | undefined;
let firebaseAuth: Auth | undefined;
let firebaseDb: Firestore | undefined;

function getApp(): FirebaseApp {
  if (typeof window === "undefined") {
    throw new Error("Firebase can only be initialized in the browser");
  }

  if (!firebaseApp) {
    firebaseApp = getApps().length
      ? getApps()[0]!
      : initializeApp(firebaseConfig);
  }

  return firebaseApp;
}

export function getClientAuth(): Auth {
  if (!firebaseAuth) {
    firebaseAuth = getAuth(getApp());
  }
  return firebaseAuth;
}

export function getClientDb(): Firestore {
  if (!firebaseDb) {
    firebaseDb = getFirestore(getApp());
  }
  return firebaseDb;
}