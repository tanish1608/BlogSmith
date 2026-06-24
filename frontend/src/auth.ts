// Local mode: no auth. BlogSmith runs as a single local workspace, so there is
// no login and no token. These stubs keep the API client and App shell happy.

export const firebaseEnabled = false;

export async function getToken(): Promise<string | null> {
  return null;
}

export function watchAuth(cb: (user: unknown | null) => void): () => void {
  cb(null);
  return () => {};
}

export async function signIn(_email: string, _password: string): Promise<void> {
  // no-op — auth is disabled in local mode
}

export async function signOut(): Promise<void> {
  // no-op — auth is disabled in local mode
}
