import {
  createUserWithEmailAndPassword,
  signInWithEmailAndPassword,
  signInWithPopup,
  GoogleAuthProvider,
  signOut,
} from "firebase/auth";
import { getClientAuth } from "./config";

const googleProvider = new GoogleAuthProvider();

export async function signUpWithEmail(email: string, password: string) {
  return createUserWithEmailAndPassword(getClientAuth(), email, password);
}

export async function signInWithEmail(email: string, password: string) {
  return signInWithEmailAndPassword(getClientAuth(), email, password);
}

export async function signInWithGoogle() {
  return signInWithPopup(getClientAuth(), googleProvider);
}

export async function logOut() {
  return signOut(getClientAuth());
}