import { useEffect, useRef, useState } from "react";
import { attendre } from "./api";
import type { Tache } from "./types";

type Progression = { fait: number; total: number };

/**
 * Suit une tâche longue d'un audit (analyse par l'IA, rédaction du rapport) et affiche sa progression.
 * La tâche continue sur le serveur quand on change d'écran ou qu'on recharge la page : `enCours` (signalée par
 * l'état de l'audit) permet de reprendre son suivi au retour.
 */
export function useSuiviTache<T>(nom: string, enCours: { id: string; nom: string } | null | undefined,
  fin: (resultat: T) => void, echec: (e: Error) => void) {
  const [progression, setProgression] = useState<Progression | null>(null);
  const suivie = useRef<string | null>(null);
  const rappels = useRef({ fin, echec });
  rappels.current = { fin, echec };

  const suivre = async (tache: Tache<T>) => {
    if (suivie.current === tache.id) return; // déjà suivie par cet écran
    suivie.current = tache.id;
    setProgression({ fait: tache.fait, total: tache.total });
    try {
      const resultat = await attendre(tache, (fait, total) => { if (suivie.current === tache.id) setProgression({ fait, total }); });
      rappels.current.fin(resultat);
    } catch (e) {
      rappels.current.echec(e as Error);
    }
    if (suivie.current === tache.id) { suivie.current = null; setProgression(null); }
  };

  useEffect(() => {
    if (enCours?.nom === nom) suivre({ id: enCours.id, nom, etat: "en_cours", fait: 0, total: 0, erreur: "", resultat: null });
  }, [enCours?.id]); // eslint-disable-line

  return { progression, setProgression, suivre };
}
