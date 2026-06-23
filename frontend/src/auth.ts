// Optional Firebase Auth. If VITE_FIREBASE_* env vars are present we use real
// email/password auth and attach the ID token to API calls. Otherwise (local dev
// with AUTH_DISABLED on the backend) we run token-less.
import { initializeApp, type FirebaseApp } from "firebase/app";
import {
  getAuth,
  signInWithEmailAndPassword,
  signOut as fbSignOut,
  onAuthStateChanged,
  type Auth,
  type User,
} from "firebase/auth";

const cfg = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
};

export const firebaseEnabled = Boolean(cfg.apiKey);

let app: FirebaseApp | null = null;
let auth: Auth | null = null;
if (firebaseEnabled) {
  app = initializeApp(cfg);
  auth = getAuth(app);
}

export async function getToken(): Promise<string | null> {
  if (!auth?.currentUser) return null;
  return auth.currentUser.getIdToken();
}

export function watchAuth(cb: (user: User | null) => void): () => void {
  if (!auth) {
    cb(null);
    return () => {};
  }
  return onAuthStateChanged(auth, cb);
}

export async function signIn(email: string, password: string): Promise<void> {
  if (!auth) throw new Error("Firebase auth not configured.");
  await signInWithEmailAndPassword(auth, email, password);
}

export async function signOut(): Promise<void> {
  if (auth) await fbSignOut(auth);
}
