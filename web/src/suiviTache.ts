import { useEffect, useRef, useState } from "react";
import { attendre } from "./api";
import type { Tache } from "./types";
import logo from "./assets/auditergo.svg";

type Progression = { fait: number; total: number; restant: number | null };

/** Demande, au lancement d'une tâche longue (geste de l'utilisateur), le droit d'afficher une notification. */
export function demanderNotification() {
  try {
    if ("Notification" in window && Notification.permission === "default") void Notification.requestPermission();
  } catch { /* navigateur sans notifications */ }
}

/** Fin d'une tâche pendant qu'on fait autre chose : titre de l'onglet et notification du système. */
function prevenir(message: string) {
  if (!document.hidden || document.title.startsWith("✓")) return; // déjà prévenu (suivi repris par un autre écran)
  const titre = document.title;
  document.title = `✓ ${message}`;
  const retour = () => { if (!document.hidden) { document.title = titre; document.removeEventListener("visibilitychange", retour); } };
  document.addEventListener("visibilitychange", retour);
  try {
    if ("Notification" in window && Notification.permission === "granted") new Notification("AuditErgo", { body: message, icon: logo, tag: message });
  } catch { /* notification refusée */ }
}

/** Temps restant estimé (secondes) d'après le rythme observé depuis le début du suivi ; null avant 1 étape. */
function estimer(debut: { t: number; fait: number }, fait: number, total: number) {
  const faits = fait - debut.fait;
  if (faits < 1 || !total || fait >= total) return null;
  return ((Date.now() - debut.t) / 1000 / faits) * (total - fait);
}

/**
 * Suit une tâche longue d'un audit (analyse par l'IA, rédaction du rapport) et affiche sa progression, avec
 * une estimation du temps restant. La tâche continue sur le serveur quand on change d'écran ou qu'on recharge
 * la page : `enCours` (signalée par l'état de l'audit) permet de reprendre son suivi au retour. `messageFin`
 * prévient quand elle se termine pendant qu'on est sur un autre onglet ou une autre application.
 */
export function useSuiviTache<T>(nom: string, enCours: { id: string; nom: string } | null | undefined,
  fin: (resultat: T) => void, echec: (e: Error) => void, messageFin?: string) {
  const [progression, setProgression] = useState<Progression | null>(null);
  const suivie = useRef<string | null>(null);
  const rappels = useRef({ fin, echec, messageFin });
  rappels.current = { fin, echec, messageFin };

  const suivre = async (tache: Tache<T>) => {
    if (suivie.current === tache.id) return; // déjà suivie par cet écran
    suivie.current = tache.id;
    let debut: { t: number; fait: number } | null = null;
    const noter = (fait: number, total: number) => {
      if (suivie.current !== tache.id) return;
      if (!debut || (total && debut.fait > fait)) debut = { t: Date.now(), fait };
      setProgression({ fait, total, restant: estimer(debut, fait, total) });
    };
    noter(tache.fait, tache.total);
    try {
      const resultat = await attendre(tache, noter);
      rappels.current.fin(resultat);
      if (rappels.current.messageFin) prevenir(rappels.current.messageFin);
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

/** « environ 4 min » / « moins d'une minute » */
export function dureeRestante(secondes: number | null, lg: "fr" | "en") {
  if (secondes === null) return "";
  const min = Math.round(secondes / 60);
  if (min < 1) return lg === "en" ? "less than a minute left" : "moins d'une minute restante";
  return lg === "en" ? `about ${min} min left` : `environ ${min} min restante${min > 1 ? "s" : ""}`;
}
