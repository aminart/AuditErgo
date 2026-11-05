import type { Comparaison, Config, EtatAudit, FormulaireParametres, Langue, ParametresConnexion, Rapport, ResumeAudit, Suggestion, Tache, TestConnexion } from "./types";

export class ErreurApi extends Error {}

async function requete<T>(url: string, options: RequestInit = {}): Promise<T> {
  let reponse: Response;
  try {
    reponse = await fetch(url, options);
  } catch {
    throw new ErreurApi("Le serveur de l'application ne répond pas. Relancez start.bat. / The application server is not answering.");
  }
  if (!reponse.ok) {
    let detail = reponse.statusText;
    try {
      const corps = await reponse.json();
      detail = typeof corps.detail === "string" ? corps.detail : JSON.stringify(corps.detail);
    } catch {
      /* corps non JSON */
    }
    throw new ErreurApi(detail);
  }
  return reponse.json() as Promise<T>;
}

const json = (corps: unknown): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(corps),
});

/** Attend la fin d'une tâche longue en interrogeant le serveur ; `progression(fait, total)` à chaque étape. */
export async function attendre<T>(tache: Tache<T>, progression?: (fait: number, total: number) => void): Promise<T> {
  let t = tache;
  while (t.etat === "en_cours") {
    progression?.(t.fait, t.total);
    await new Promise((r) => setTimeout(r, 700));
    t = await requete<Tache<T>>(`/api/taches/${t.id}`);
  }
  if (t.etat === "erreur") throw new ErreurApi(t.erreur);
  return t.resultat as T;
}

export const api = {
  config: (lg: Langue) => requete<Config>(`/api/config?langue=${lg}`),
  parametres: () => requete<ParametresConnexion>("/api/settings"),
  enregistrerParametres: (f: FormulaireParametres) =>
    requete<ParametresConnexion>("/api/settings", { ...json(f), method: "PUT" }),
  effacerParametres: () => requete<ParametresConnexion>("/api/settings", { method: "DELETE" }),
  importerCertificat: (fichier: File, lg: Langue) => {
    const corps = new FormData();
    corps.append("file", fichier);
    return requete<ParametresConnexion>(`/api/settings/certificate?langue=${lg}`, { method: "POST", body: corps });
  },
  testerParametres: (f: FormulaireParametres, lg: Langue) => requete<TestConnexion>(`/api/settings/test?langue=${lg}`, json(f)),
  viderCache: () => requete<{ cache: number | null }>("/api/cache", { method: "DELETE" }),
  templateUrl: (lg: Langue) => `/api/template?langue=${lg}`,

  suggerer: (demande: Record<string, unknown>) =>
    requete<Tache<{ suggestion: Suggestion; constat: string; ecran: string }>>("/api/suggestion", json(demande)),

  deposer: (fichier: File, lg: Langue) => {
    const corps = new FormData();
    corps.append("fichier", fichier);
    corps.append("langue", lg);
    return requete<EtatAudit>("/api/audits", { method: "POST", body: corps });
  },
  audit: (id: string, lg: Langue) => requete<EtatAudit>(`/api/audits/${id}?langue=${lg}`),
  supprimer: (id: string) => requete<{ ok: boolean }>(`/api/audits/${id}`, { method: "DELETE" }),
  lister: () => requete<{ audits: ResumeAudit[]; persistant: boolean }>("/api/audits"),
  comparer: (a: string, b: string, lg: Langue) => requete<Comparaison>(`/api/comparaison?a=${a}&b=${b}&langue=${lg}`),
  analyserIA: (id: string, remplir: boolean, forcer: boolean, lg: Langue) =>
    requete<Tache<EtatAudit>>(`/api/audits/${id}/ia`, json({ remplir, forcer, langue: lg })),
  decider: (id: string, decisions: { ligne: number; champ: string; action: string; valeur?: string }[], lg: Langue) =>
    requete<EtatAudit>(`/api/audits/${id}/decisions`, json({ decisions, langue: lg })),
  fichierUrl: (id: string) => `/api/audits/${id}/fichier`,

  genererRapport: (id: string, ia: boolean, forcer: boolean, lg: Langue) =>
    requete<Tache<Rapport>>(`/api/audits/${id}/rapport`, json({ ia, forcer, langue: lg })),
  rapport: (id: string) => requete<Rapport>(`/api/audits/${id}/rapport`),
  modifierRapport: (id: string, chemin: string, valeur: string | number | string[]) =>
    requete<Rapport>(`/api/audits/${id}/rapport`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ chemin, valeur }) }),
  rapportWordUrl: (id: string) => `/api/audits/${id}/rapport.docx`,
};
