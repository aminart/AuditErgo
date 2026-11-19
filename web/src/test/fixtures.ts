import type { Completion, Config, Constat, EtatAudit, Suggestion, Tache } from "../types";

/** Référentiel réduit à ce qu'affiche l'écran Relecture. */
export const config: Config = {
  langue_defaut: "fr",
  langues: { fr: "Français", en: "English" },
  referentiel: {
    version: "test",
    categories: [{ code: "1", libelle: "Guidage", definition: "" }],
    criteres: [
      { code: "1.1", libelle: "1.1 Incitation", nom: "Prompting", nom_fr: "Incitation", categorie: "1", definition: "", checklist: [] },
      { code: "1.2", libelle: "1.2 Groupement", nom: "Grouping", nom_fr: "Groupement", categorie: "1", definition: "", checklist: [] },
    ],
    nb_regles: 0,
    gravites: [
      { niveau: 1, libelle: "Mineure", definition: "" },
      { niveau: 3, libelle: "Élevée", definition: "" },
    ],
    types_reco: [],
    champs: { ecran: "Écran", constat: "Constat", type: "Type", critere: "Critère", gravite: "Gravité", recommandation: "Recommandation" },
  },
  ia: { active: true, modele: "test", adresse: "", cle: false, ca_bundle: "", locale: true, hote: "" },
  cache: null,
};

const proposition = (valeur: string | number, autre: Partial<Completion> = {}): Completion =>
  ({ valeur, origine: "ia", explication: "Proposé par l'IA", ...autre });

export function constat(ligne: number, autre: Partial<Constat> = {}): Constat {
  return {
    ligne,
    ref: `C${ligne}`,
    valeurs: { ecran: "Accueil", constat: `Constat de la ligne ${ligne}`, type: "Problème", critere: null, gravite: null, recommandation: "Ajouter un libellé" },
    gravite: 3,
    critere_code: "1.1",
    completions: { critere: proposition("1.1 Incitation"), gravite: proposition(3) },
    anomalies: [],
    ia: null,
    ecarts_ia: null,
    ...autre,
  };
}

/** Avis de l'IA qui diverge de la saisie du designer sur le critère. */
export const avisIA = {
  code: "1.2", critere: config.referentiel.criteres[1], verdict: "a_revoir", verdict_libelle: "À revoir",
  commentaire_verdict: "Le problème porte sur le regroupement.", justification: "", reco_statut: "bonne", reco_statut_libelle: "Bonne",
  reco_a_retenir: "Ajouter un libellé", reco_commentaire: "", gravite: 3, gravite_libelle: "Élevée", justification_gravite: "",
  confiance_libelle: "Forte",
} as unknown as Suggestion;

export function etat(autre: Partial<EtatAudit> = {}): EtatAudit {
  const constats = autre.constats ?? [constat(2)];
  return {
    id: "a1",
    nom: "Audit de test",
    nom_sortie: "audit_complete.xlsx",
    langue: "fr",
    audit: { onglet: "Audit", ligne_entete: 1, langue_fichier: "fr", colonnes_reconnues: [], colonnes_ignorees: [], colonnes_manquantes: [], contexte: {} },
    constats,
    anomalies: [],
    synthese: {
      nb_constats: constats.length, nb_problemes: constats.length, nb_points_forts: 0, gravites: {}, par_critere: {}, secondaires: {},
      non_couverts: [], categories_non_couvertes: [], conformes: constats.length, sans_remarque: constats.length,
      completude_recommandee: 1, nb_bloquants: 0, nb_avertissements: 0, pret: true,
    },
    ia: null,
    nb_completions: 0,
    a_valider: constats.reduce((n, c) => n + Object.values(c.completions).filter((x) => x.origine !== "valide").length, 0),
    rapport: "aucun",
    cree: "2026-11-19T10:00:00",
    persistant: true,
    tache: null,
    ...autre,
  };
}

export const tache = <T>(id: string, autre: Partial<Tache<T>> = {}): Tache<T> =>
  ({ id, nom: "ia", etat: "en_cours", fait: 0, total: 0, erreur: "", resultat: null, ...autre });

/* --- Serveur factice : remplace fetch, note chaque requête, répond tout de suite ou quand le test le décide --- */

export type Requete = { methode: string; url: string; corps: unknown };
type Reponse = { statut?: number; corps: unknown };
type Gestionnaire = (r: Requete) => Reponse | Promise<Reponse>;

export function differe<T>() {
  let resoudre!: (v: T) => void;
  const promesse = new Promise<T>((r) => { resoudre = r; });
  return { promesse, resoudre };
}

export function serveurFactice() {
  const requetes: Requete[] = [];
  const routes: { methode: string; motif: RegExp; gerer: Gestionnaire }[] = [];
  const route = (methode: string, motif: RegExp, gerer: Gestionnaire) => { routes.unshift({ methode, motif, gerer }); };
  // Toujours appelées par l'écran, sans intérêt pour les tests
  route("GET", /^\/api\/settings\/models$/, () => ({ corps: { available: false, options: [], default: null, saved_default: null, studiodock_default: null } }));
  route("GET", /^\/api\/audits$/, () => ({ corps: { audits: [], persistant: true } }));

  const fetch = async (url: string, options: RequestInit = {}) => {
    const methode = options.method ?? "GET";
    const corps = typeof options.body === "string" ? JSON.parse(options.body) : options.body ?? null;
    const requete = { methode, url, corps };
    requetes.push(requete);
    const r = routes.find((x) => x.methode === methode && x.motif.test(url.split("?")[0]));
    if (!r) throw new Error(`Requête inattendue : ${methode} ${url}`);
    const { statut = 200, corps: reponse } = await r.gerer(requete);
    return { ok: statut < 400, status: statut, statusText: String(statut), json: async () => reponse };
  };

  return {
    fetch,
    route,
    requetes,
    /** Requêtes reçues pour une méthode et une adresse (sans les paramètres) */
    vers: (methode: string, chemin: string) => requetes.filter((r) => r.methode === methode && r.url.split("?")[0] === chemin),
  };
}
