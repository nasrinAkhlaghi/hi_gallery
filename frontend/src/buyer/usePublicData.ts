import { useEffect, useState } from "react";
import { apiRequest } from "../auth/api";

export function usePublicData<T>(path: string, load: (path: string) => Promise<T> = apiRequest) {
  const [attempt, setAttempt] = useState(0);
  const [state, setState] = useState<{ path: string; data: T | null; error: unknown; loading: boolean }>({ path, data: null, error: null, loading: true });
  useEffect(() => {
    let active = true;
    setState({ path, data: null, error: null, loading: true });
    load(path).then((data) => { if (active) setState({ path, data, error: null, loading: false }); })
      .catch((error: unknown) => { if (active) setState({ path, data: null, error, loading: false }); });
    return () => { active = false; };
  }, [path, load, attempt]);
  // Do not briefly render a previous product/shop while the route is changing.
  return { ...(state.path === path ? state : { data: null, error: null, loading: true }), retry: () => setAttempt((value) => value + 1) };
}
