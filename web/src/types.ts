export type Langue = "fr" | "en";

export interface Critere {
  code: string;
  libelle: string;
  nom: string;
  nom_fr: string;
  categorie: string;
  definition: string;
  checklist: string[];
}

export interface Referentiel {
  version: string;
  categories: { code: string; libelle: string; definition: string }[];
  criteres: Critere[];
  nb_regles: number;
  gravites: { niveau: number; libelle: string; definition: string }[];
  types_reco: { cle: string; libelle: string }[];
  champs: Record<string, string>;
}

export interface Config {
  langue_defaut: Langue;
  langues: Record<string, string>;
  referentiel: Referentiel;
  ia: { active: boolean; modele: string; adresse: string; cle: boolean; ca_bundle: string; locale: boolean; hote: string };
  cache: number | null;
}

/** Paramètres de connexion au modèle (écran Réglages, même fonctionnement que SpecGen). */
export type ChampParametre = "api_base" | "api_key" | "ca_bundle" | "model" | "timeout";

export interface TestConnexion {
  ok: boolean;
  /** Champ en cause : api_base, api_key, certificate, model ; disabled si l'IA est désactivée. */
  field: string | null;
  title: string;
  message: string;
  at: string;
  model?: string;
}

export interface ParametresConnexion {
  saved: boolean;
  active: boolean;
  env_fields: ChampParametre[];
  env_file: string | null;
  storage_dir: string;
  api_base: string;
  default_api_base: string;
  has_api_key: boolean;
  api_key_hint: string;
  certificate: { name: string; imported_at?: string; expires_at?: string } | null;
  model: string;
  timeout: number;
  last_test: TestConnexion | null;
}

export interface FormulaireParametres {
  api_base: string;
  /** null : garder la clé enregistrée. */
  api_key: string | null;
  model: string;
  timeout: number;
}

export interface Suggestion {
  erreur?: string;
  code: string;
  confiance: string;
  confiance_libelle: string;
  justification: string;
  regle: string;
  question_checklist: string;
  secondaires: { code: string; libelle: string; justification: string }[];
  alternatives: { code: string; libelle: string; pourquoi_pas: string }[];
  question_a_se_poser: string;
  precisions_manquantes: string[];
  verdict: string;
  verdict_libelle: string;
  commentaire_verdict: string;
  critere_designer: string | null;
  critere_designer_libelle: string;
  reco_proposee: string;
  type_reco: string | null;
  type_reco_libelle: string;
  reco_statut: string;
  reco_statut_libelle: string;
  reco_commentaire: string;
  reco_amelioree: string;
  reco_complementaires: string[];
  gravite: number | null;
  gravite_libelle: string;
  justification_gravite: string;
  depuis_cache: boolean;
  critere: Critere;
  categorie_libelle: string;
  ligne_excel: string;
  justification_critere: string;
  reco_a_retenir: string;
}

export interface Anomalie {
  niveau: "bloquant" | "avertissement" | "info";
  code: string;
  message: string;
  ligne: number | null;
  constat: string | null;
  champ: string | null;
}

export interface Completion {
  valeur: string | number | null;
  origine: "ia" | "auto" | "valide";
  explication: string;
}

export interface Constat {
  ligne: number;
  ref: string;
  valeurs: Record<string, string | number | null>;
  gravite: number | null;
  critere_code: string | null;
  completions: Record<string, Completion>;
  anomalies: Anomalie[];
  ia: Suggestion | null;
}

export interface Synthese {
  nb_constats: number;
  nb_problemes: number;
  nb_points_forts: number;
  gravites: Record<string, number>;
  par_critere: Record<string, number>;
  secondaires: Record<string, number>;
  non_couverts: string[];
  categories_non_couvertes: string[];
  conformes: number;
  sans_remarque: number;
  completude_recommandee: number;
  nb_bloquants: number;
  nb_avertissements: number;
  pret: boolean;
}

export interface EtatAudit {
  id: string;
  nom: string;
  nom_sortie: string;
  langue: Langue;
  audit: {
    onglet: string;
    ligne_entete: number;
    langue_fichier: string;
    colonnes_reconnues: string[];
    colonnes_ignorees: string[];
    colonnes_manquantes: string[];
    contexte: Record<string, string | number | null>;
  };
  constats: Constat[];
  anomalies: Anomalie[];
  synthese: Synthese;
  ia: null | { analyses: number; erreurs: number; depuis_cache: number; criteres_a_revoir: number; recos_a_ameliorer: number };
  nb_completions: number;
  a_valider: number;
  rapport: "aucun" | "a_jour" | "perime";
  cree: string;
  persistant: boolean;
}

export interface ResumeAudit {
  id: string;
  nom: string;
  produit: string | null;
  designer: string | null;
  date: string | null;
  plateforme: string | null;
  nb_constats: number;
  nb_problemes: number;
  nb_points_forts: number;
  gravites: Record<string, number>;
  nb_bloquants: number;
  maturite_indicative: number;
  ia: boolean;
  rapport: boolean;
  a_valider: number;
  cree: string;
  modifie: string;
}

export interface ProfilAudit extends ResumeAudit {
  ecrans: string[];
  graves: number;
  par_categorie: Record<string, number>;
  maturite: number | null;
}

export interface Comparaison {
  a: ProfilAudit;
  b: ProfilAudit;
  categories: { code: string; libelle: string }[];
}

export interface Probleme {
  cle: string;
  ref: string;
  ecran: string;
  constat: string;
  critere: string | null;
  critere_libelle: string;
  gravite: number | null;
  recommandation: string;
  type_reco: string;
}

export interface Theme {
  titre: string;
  description: string;
  pourquoi: string;
  consequences: string;
  problemes: string[];
  ecrans: string[];
  gravite_max: number | null;
  poids: number;
  recurrent: boolean;
  criteres: { code: string; libelle: string }[];
}

export interface Rapport {
  langue: Langue;
  ia: boolean;
  erreur: string;
  modele: string;
  modifie: boolean;
  libelles: Record<string, string>;
  maturites: { niveau: number; libelle: string; definition: string }[];
  gravites: { niveau: number; libelle: string; definition: string }[];
  faits: {
    contexte: Record<string, string | number>;
    problemes: Probleme[];
    points_forts: { ref: string; ecran: string; constat: string }[];
    gravites: Record<string, number>;
    ecrans: string[];
    graves: number;
    version_referentiel: string;
    maturite_indicative: number;
  };
  resume: string;
  maturite: number;
  maturite_justification: string;
  points_forts: string[];
  faiblesses: string[];
  recurrents: string[];
  impact: string;
  themes: Theme[];
  cas_isoles: number[];
  recommandations: {
    titre: string;
    objectif: string;
    importance: string;
    benefices: string;
    problemes_resolus: string;
    themes: number[];
    nb_problemes: number;
    impact: string;
    effort: string;
    pistes: string[];
  }[];
  quick_wins: { titre: string; description: string; valeur: string; problemes: string[] }[];
  quick_wins_candidats: boolean;
  suites: { titre: string; horizon: string; description: string }[];
  demarche: string[];
}

export interface Tache<T> {
  id: string;
  nom: string;
  etat: "en_cours" | "terminee" | "erreur";
  fait: number;
  total: number;
  erreur: string;
  resultat: T | null;
}
