import { useSyncExternalStore } from "react";

/** Modèle choisi au lancement parmi ceux de Studio Dock (« <id de connexion>|<modèle> »), pour cette session.
 * null : le modèle par défaut (choisi dans les Réglages). Envoyé avec chaque requête (en-tête X-StudioDock-Model). */
let current: string | null = null;
const listeners = new Set<() => void>();

export function pickedModel(): string | null {
  return current;
}

export function pickModel(value: string | null): void {
  current = value || null;
  listeners.forEach((listener) => listener());
}

export function usePickedModel(): [string | null, (value: string | null) => void] {
  const value = useSyncExternalStore(
    (listener) => {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    () => current,
  );
  return [value, pickModel];
}
