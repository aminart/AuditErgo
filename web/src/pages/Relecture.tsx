import { useEffect, useMemo, useRef, useState } from "react";
import type { Dispatch, SetStateAction } from "react";
import { api } from "../api";
import { demanderNotification, dureeRestante, useSuiviTache } from "../suiviTache";
import { useLangue, useT } from "../i18n";
import type { Anomalie, Config, Constat, EtatAudit, ResumeAudit } from "../types";
import ChoixModele from "../components/ChoixModele";
import { Alerte, Badge, Bouton, Icone, Lien, Metrique, Onglets, Progression, Section, Spinner, cx } from "../components/ui";
import { ListeAudits } from "./Historique";
import { BarresHorizontales, PastilleGravite, couleurGravite } from "../components/graphiques";

const CHAMPS_VIDES = ["type", "categorie", "critere", "gravite", "recommandation"];
const TON_NIVEAU = { bloquant: "danger", avertissement: "alerte", info: "info" } as const;
const TON_VERDICT = { confirme: "ok", a_revoir: "alerte", incorrect: "danger", non_fourni: "neutre" } as const;
const TON_RECO = { bonne: "ok", a_ameliorer: "alerte", hors_sujet: "danger", non_fournie: "neutre" } as const;
type Decision = { ligne: number; champ: string; action: string; valeur?: string };

const pct = (x: number) => `${Math.round(x * 100)} %`;
/** Gravité affichée partout de la même façon : « 3 · Élevée » */
const texteGravite = (niveau: number | null | undefined, config: Config, brut: unknown) => {
  const g = config.referentiel.gravites.find((x) => x.niveau === niveau);
  return g ? `${g.niveau} · ${g.libelle}` : String(brut ?? "");
};
const estVide = (v: unknown) => v === null || v === undefined || String(v).trim() === "";

/* --- Dépôt du fichier ------------------------------------------------------------------------------ */

function Depot({ deposer, enCours }: { deposer: (f: File) => void; enCours: boolean }) {
  const t = useT();
  const lg = useLangue();
  const entree = useRef<HTMLInputElement>(null);
  const [survol, setSurvol] = useState(false);
  return (
    <div
      onDragOver={(e) => { e.preventDefault(); setSurvol(true); }}
      onDragLeave={() => setSurvol(false)}
      onDrop={(e) => { e.preventDefault(); setSurvol(false); const f = e.dataTransfer.files[0]; if (f) deposer(f); }}
      className={cx("grid min-h-72 place-items-center rounded-lg border-2 border-dashed p-8 text-center transition-colors",
        survol ? "border-accent bg-info-doux" : "border-bord bg-surface")}>
      {enCours ? (
        <div className="flex items-center gap-3 text-texte-2"><Spinner className="size-5" /> {t("rel.lecture")}</div>
      ) : (
        <div>
          <div className="mx-auto mb-4 grid size-14 place-items-center rounded-lg bg-marque-doux text-marque"><Icone nom="importer" className="size-7" /></div>
          <p className="text-lg font-semibold">{t("rel.deposer")}</p>
          <p className="my-2 text-sm text-texte-3">{t("rel.ou")}</p>
          <Bouton variante="primaire" onClick={() => entree.current?.click()}>{t("rel.parcourir")}</Bouton>
          <input ref={entree} type="file" accept=".xlsx" className="hidden" onChange={(e) => { const f = e.target.files?.[0]; if (f) deposer(f); e.target.value = ""; }} />
          <div className="mt-6 flex flex-wrap items-center justify-center gap-x-2 gap-y-1 text-xs text-texte-3">
            <span>{t("rel.pas_d_audit")}</span>
            <a href={api.templateUrl(lg)} download className="inline-flex items-center gap-1 font-medium text-accent underline underline-offset-2 hover:no-underline">
              <Icone nom="telecharger" className="size-3.5" />{t("rel.template")}
            </a>
          </div>
          <p className="mt-1 text-xs text-texte-3">{t("rel.exemple")}</p>
        </div>
      )}
    </div>
  );
}

/* --- Une cellule complétée, à valider ---------------------------------------------------------------- */

const LONGS = ["recommandation", "justification", "constat"];

function CelluleCompletee({ champ, libelle, c, decider, occupe, config }: {
  champ: string; libelle: string; c: Constat; decider: (d: Decision[]) => void; occupe: boolean; config: Config;
}) {
  const t = useT();
  const comp = c.completions[champ];
  const [edition, setEdition] = useState(false);
  const [texte, setTexte] = useState(String(comp.valeur ?? ""));
  const valide = comp.origine === "valide";
  const action = "grid size-7 place-items-center rounded-md text-texte-2 hover:bg-surface disabled:opacity-40";
  return (
    <div className={cx("rounded-md border px-3 py-2", LONGS.includes(champ) && "sm:col-span-2",
      valide ? "border-bord bg-surface" : "border-ia/25 bg-ia-doux")}>
      <div className="flex items-center justify-between gap-2">
        <div className="flex min-w-0 items-center gap-1.5">
          <span className="truncate text-xs font-semibold text-texte-2">{libelle}</span>
          {comp.adopte && <Badge ton="ia">{t("c.adopte")}</Badge>}
          {valide ? <Icone nom="check" className="size-3.5 text-ok" />
            : <span title={comp.origine === "ia" ? t("c.ia_propose") : t("c.auto")}><Icone nom="ia" className="size-3.5 text-ia" /></span>}
        </div>
        {!edition && (
          <div className="-mr-1.5 flex shrink-0">
            {!valide && <button disabled={occupe} title={t("c.valider")} aria-label={`${t("c.valider")} : ${libelle}`} onClick={() => decider([{ ligne: c.ligne, champ, action: "valider" }])} className={cx(action, "hover:text-ok")}><Icone nom="check" className="size-4" /></button>}
            <button disabled={occupe} title={t("c.modifier")} aria-label={`${t("c.modifier")} : ${libelle}`} onClick={() => setEdition(true)} className={action}><Icone nom="crayon" className="size-4" /></button>
            <button disabled={occupe} title={comp.adopte ? t("c.revenir") : t("c.refuser")} aria-label={`${comp.adopte ? t("c.revenir") : t("c.refuser")} : ${libelle}`} onClick={() => decider([{ ligne: c.ligne, champ, action: "refuser" }])} className={cx(action, "hover:text-danger")}><Icone nom={comp.adopte ? "rafraichir" : "croix"} className="size-4" /></button>
          </div>
        )}
      </div>
      {edition ? (
        <div className="mt-2 space-y-2">
          <textarea className="champ min-h-16" value={texte} onChange={(e) => setTexte(e.target.value)} autoFocus />
          <div className="flex justify-end gap-2">
            <Bouton onClick={() => { setEdition(false); setTexte(String(comp.valeur ?? "")); }}>{t("annuler")}</Bouton>
            <Bouton variante="primaire" disabled={occupe} onClick={() => { decider([{ ligne: c.ligne, champ, action: "modifier", valeur: texte }]); setEdition(false); }}>{t("enregistrer")}</Bouton>
          </div>
        </div>
      ) : (
        <p className="mt-0.5 text-sm whitespace-pre-wrap" title={valide && !comp.adopte ? undefined : comp.explication}>{champ === "gravite" ? texteGravite(c.gravite, config, comp.valeur) : String(comp.valeur)}</p>
      )}
    </div>
  );
}

/* --- Carte d'un constat ---------------------------------------------------------------------------- */

function CarteConstat({ c, config, decider, occupe }: { c: Constat; config: Config; decider: (d: Decision[]) => void; occupe: boolean }) {
  const t = useT();
  const champs = config.referentiel.champs;
  const v = c.valeurs;
  const ia = c.ia;
  const completes = Object.keys(c.completions).sort((a, b) => Number(LONGS.includes(a)) - Number(LONGS.includes(b)));
  const aValider = completes.filter((k) => c.completions[k].origine !== "valide");
  const gravites = config.referentiel.gravites;
  const pointFort = /point fort|strength/i.test(String(v.type ?? ""));
  const pire = c.anomalies.find((a) => a.niveau === "bloquant") ?? c.anomalies.find((a) => a.niveau === "avertissement");
  const [ouvert, setOuvert] = useState(false);
  const saisis = ["critere", "gravite", "recommandation"].filter((k) => !estVide(v[k]) && !c.completions[k]);
  const ecarts = c.ecarts_ia && ia && !ia.erreur ? (["critere", "recommandation", "gravite"] as const).filter((k) => c.ecarts_ia![k]) : [];

  return (
    <article className={cx("carte overflow-hidden", pire?.niveau === "bloquant" && "border-l-4 border-l-danger")}>
      <div className="p-4 sm:p-5">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5 text-xs text-texte-2">
          <span className="font-mono font-semibold text-texte">{c.ref}</span>
          {v.ecran && <span className="font-medium">{String(v.ecran)}</span>}
          <span className="text-texte-3">{t("c.ligne", { n: c.ligne })}</span>
          {pointFort && <Badge ton="ok">{t("c.point_fort")}</Badge>}
          {c.gravite && !c.completions.gravite && <PastilleGravite niveau={c.gravite} libelle={gravites.find((g) => g.niveau === c.gravite)?.libelle ?? ""} />}
          <span className="ml-auto flex gap-1.5">
            {aValider.length > 0 && <Badge ton="ia" icone="ia">{t("c.a_valider", { n: aValider.length })}</Badge>}
            {c.anomalies.filter((a) => a.niveau !== "info").length > 0 && (
              <Badge ton={TON_NIVEAU[pire!.niveau]} icone="alerte">{c.anomalies.filter((a) => a.niveau !== "info").length}</Badge>
            )}
          </span>
        </div>
        <p className="mt-2 text-[15px] leading-relaxed">{String(v.constat ?? "")}</p>

        {saisis.length > 0 && (
          <dl className="mt-3 grid gap-x-4 gap-y-1.5 text-sm sm:grid-cols-[10rem_1fr]">
            {saisis.map((k) => (
              <div key={k} className="contents">
                <dt className="text-texte-3">{champs[k]}</dt>
                <dd>{k === "gravite" ? texteGravite(c.gravite, config, v[k]) : String(v[k])}</dd>
              </div>
            ))}
          </dl>
        )}

        {completes.length > 0 && (
          <div className="mt-4 grid gap-2 sm:grid-cols-2">
            {completes.map((k) => <CelluleCompletee key={`${k}-${String(c.completions[k].valeur)}`} champ={k} libelle={champs[k] ?? k} c={c} decider={decider} occupe={occupe} config={config} />)}
            {aValider.length > 1 && (
              <div className="flex justify-end sm:col-span-2">
                <button disabled={occupe} className="btn-discret text-xs text-ok" onClick={() => decider(aValider.map((k) => ({ ligne: c.ligne, champ: k, action: "valider" })))}>
                  <Icone nom="check" className="size-3.5" /> {t("c.tout_valider", { n: aValider.length })}
                </button>
              </div>
            )}
          </div>
        )}

        {ecarts.length > 0 && ia && (
          <div className="mt-4 space-y-2 rounded-md border border-alerte/40 bg-alerte-doux/40 px-3 py-2.5">
            <div className="flex items-center gap-1.5 text-xs font-semibold text-texte-2"><Icone nom="ia" className="size-3.5 text-ia" />{t("c.ecarts")}</div>
            {ecarts.map((k) => {
              const proposition = k === "critere" ? ia.critere.libelle : k === "recommandation" ? ia.reco_a_retenir : `${ia.gravite} · ${ia.gravite_libelle}`;
              const pourquoi = k === "critere" ? ia.commentaire_verdict || ia.justification : k === "recommandation" ? ia.reco_commentaire : ia.justification_gravite;
              return (
                <div key={k} className="flex flex-wrap items-start justify-between gap-x-4 gap-y-1.5 text-sm">
                  <div className="min-w-0 flex-1 basis-80">
                    <span className="text-texte-3">{champs[k]} · {t("c.ia_propose_court")} </span>
                    <span className="font-medium">{proposition}</span>
                    {pourquoi && <p className="text-texte-2">{pourquoi}</p>}
                  </div>
                  <Bouton variante="discret" className="shrink-0 text-xs" disabled={occupe} onClick={() => decider([{ ligne: c.ligne, champ: k, action: "adopter" }])}>
                    <Icone nom="check" className="size-3.5" />{t("c.adopter")}
                  </Bouton>
                </div>
              );
            })}
          </div>
        )}

        {c.anomalies.length > 0 && (
          <ul className="mt-3 space-y-1">
            {c.anomalies.map((a, i) => (
              <li key={i} className="flex items-start gap-2 text-sm">
                <span className="mt-1.5 size-2 shrink-0 rounded-full" style={{ background: `var(--${TON_NIVEAU[a.niveau]})` }} aria-hidden="true" />
                <span><span className="font-medium">{t(`niveau.${a.niveau}`)}</span>{a.champ && <span className="text-texte-3"> · {champs[a.champ] ?? a.champ}</span>} — <span className="text-texte-2">{a.message}</span></span>
              </li>
            ))}
          </ul>
        )}
      </div>

      {ia && (
        <div className="border-t border-bord bg-surface-2/60">
          <button onClick={() => setOuvert(!ouvert)} className="flex w-full flex-wrap items-center gap-2 px-4 py-2.5 text-left text-sm sm:px-5" aria-expanded={ouvert}>
            <Icone nom="fleche" className={cx("size-4 text-texte-3 transition-transform", ouvert && "rotate-90")} />
            <span className="font-medium">{t("c.avis")}</span>
            {ia.erreur ? <Badge ton="danger">{t("ia.erreurs", { n: 1 })}</Badge> : (
              <>
                <Badge ton="marque">{ia.critere.code}</Badge>
                {ia.verdict !== "non_fourni" && (ia.verdict === "confirme" || c.ecarts_ia?.critere) && <Badge ton={TON_VERDICT[ia.verdict as keyof typeof TON_VERDICT]}>{t("c.verdict")} : {ia.verdict_libelle}</Badge>}
                {ia.reco_statut !== "non_fournie" && (!["a_ameliorer", "hors_sujet"].includes(ia.reco_statut) || c.ecarts_ia?.recommandation) && <Badge ton={TON_RECO[ia.reco_statut as keyof typeof TON_RECO]}>{t("c.reco")} : {ia.reco_statut_libelle}</Badge>}
              </>
            )}
          </button>
          {ouvert && (
            <div className="space-y-3 px-4 pb-4 text-sm sm:px-5">
              {ia.erreur ? <Alerte ton="danger">{t("c.erreur_ia", { e: ia.erreur })}</Alerte> : (
                <>
                  <div>
                    <div className="text-xs font-semibold text-texte-3 uppercase">{t("c.critere_ia")} · {ia.confiance_libelle}</div>
                    <p className="mt-0.5 font-medium">{ia.critere.libelle}</p>
                    <p className="text-texte-2">{ia.commentaire_verdict || ia.justification}</p>
                  </div>
                  {ia.reco_a_retenir && (
                    <div>
                      <div className="text-xs font-semibold text-texte-3 uppercase">{t("c.reco_ia")}</div>
                      <p className="mt-0.5">{ia.reco_a_retenir}</p>
                      {ia.reco_commentaire && <p className="text-texte-2">{ia.reco_commentaire}</p>}
                    </div>
                  )}
                  {ia.gravite && (
                    <div>
                      <div className="text-xs font-semibold text-texte-3 uppercase">{t("c.gravite_ia")}</div>
                      <div className="mt-1"><PastilleGravite niveau={ia.gravite} libelle={ia.gravite_libelle} /></div>
                      <p className="mt-0.5 text-texte-2">{ia.justification_gravite}</p>
                    </div>
                  )}
                </>
              )}
            </div>
          )}
        </div>
      )}
    </article>
  );
}

/* --- Page --------------------------------------------------------------------------------------- */

type Onglet = "constats" | "anomalies" | "couverture" | "gravite";
type Filtre = "tous" | "bloquants" | "a_valider" | "avec_anomalie" | "a_revoir";
type Tri = "urgence" | "fichier";

/** Urgence d'un constat : anomalie bloquante, puis écart avec l'IA ou proposition à valider, puis avertissement */
function urgence(c: Constat) {
  if (c.anomalies.some((a) => a.niveau === "bloquant")) return 4;
  if (c.ecarts_ia && Object.values(c.ecarts_ia).some(Boolean)) return 3;
  if (Object.values(c.completions).some((x) => x.origine !== "valide")) return 2;
  if (c.anomalies.some((a) => a.niveau === "avertissement")) return 1;
  return 0;
}

const lireNiveau = (v: string | undefined) => { const n = Number(/^\s*(\d)\b/.exec(v ?? "")?.[1]); return n >= 1 && n <= 4 ? n : null; };

/** Décisions appliquées tout de suite à l'écran, avant la réponse du serveur (qui fait foi ensuite) */
function appliquer(etat: EtatAudit, decisions: Decision[]): EtatAudit {
  const constats = etat.constats.map((c) => {
    const miennes = decisions.filter((d) => d.ligne === c.ligne);
    if (!miennes.length) return c;
    const completions = { ...c.completions };
    const valeurs = { ...c.valeurs };
    let gravite = c.gravite;
    for (const d of miennes) {
      const comp = completions[d.champ];
      if (!comp || comp.adopte) continue; // adopter, revenir à la saisie : le serveur calcule la valeur
      if (d.action === "valider") completions[d.champ] = { ...comp, origine: "valide" };
      else if (d.action === "modifier") { completions[d.champ] = { ...comp, origine: "valide", valeur: d.valeur ?? "" }; valeurs[d.champ] = d.valeur ?? ""; }
      else if (d.action === "refuser") { delete completions[d.champ]; valeurs[d.champ] = null; }
      // Niveau affiché (« 3 · Élevée ») : suit la cellule, le serveur le relit ensuite (« 3 », « 3 – Élevée »…)
      if (d.champ === "gravite" && d.action !== "valider") gravite = d.action === "modifier" ? lireNiveau(d.valeur) : null;
    }
    return { ...c, completions, valeurs, gravite };
  });
  const a_valider = constats.reduce((n, c) => n + Object.values(c.completions).filter((x) => x.origine !== "valide").length, 0);
  return { ...etat, constats, a_valider };
}

export default function PageRelecture({ config, etat, setEtat, allerRapport, ouvrir, allerHistorique }: {
  config: Config; etat: EtatAudit | null; setEtat: Dispatch<SetStateAction<EtatAudit | null>>; allerRapport: () => void;
  ouvrir: (id: string) => void; allerHistorique: () => void;
}) {
  const t = useT();
  const lg = useLangue();
  const ref = config.referentiel;
  const [depot, setDepot] = useState(false);
  const [erreur, setErreur] = useState("");
  const [remplir, setRemplir] = useState(true);
  const [occupe, setOccupe] = useState(false);
  const [onglet, setOnglet] = useState<Onglet>("constats");
  const [filtre, setFiltre] = useState<Filtre>("tous");
  const [tri, setTri] = useState<Tri>("urgence");
  const liste = useRef<HTMLDivElement>(null);
  /** Montre les constats concernés par un chiffre ou le bandeau : onglet Constats, filtre, défilement */
  const montrer = (f: Filtre) => {
    setOnglet("constats"); setFiltre(f); setRecherche("");
    requestAnimationFrame(() => liste.current?.scrollIntoView({ behavior: "smooth", block: "start" }));
  };
  const [recherche, setRecherche] = useState("");
  const [niveaux, setNiveaux] = useState<string[]>(["bloquant", "avertissement", "info"]);
  // Analyse par l'IA : son suivi reprend au retour sur cet écran ou après un rechargement de la page
  const { progression: analyse, setProgression: setAnalyse, suivre } = useSuiviTache<EtatAudit>("ia", etat?.tache, setEtat, (e) => {
    setErreur(e.message);
    setEtat((p) => p && { ...p, tache: null });
  }, t("ia.terminee"));
  const tacheEnCours = !!etat?.tache;

  const deposer = async (f: File) => {
    setErreur(""); setDepot(true);
    try {
      setEtat(await api.deposer(f, lg));
      setOnglet("constats"); setFiltre("tous");
    } catch (e) { setErreur((e as Error).message); }
    setDepot(false);
  };

  // Nouvelle version du fichier (modifié dans Excel) : remplace la précédente dans le même audit
  const [version, setVersion] = useState("");
  useEffect(() => { setVersion(""); }, [etat?.id]);
  const nouvelleVersion = async (f: File) => {
    if (!etat) return;
    setErreur(""); setVersion(""); setDepot(true);
    try {
      const e = await api.nouvelleVersion(etat.id, f, lg);
      setEtat(e);
      const relancer = e.ia_avant && config.ia.active;
      setVersion([t(relancer ? "rel.version_ia" : "rel.version_ok"), e.rapport === "perime" ? t("rel.version_rapport") : ""].filter(Boolean).join(" "));
      setDepot(false);
      if (relancer) await lancerIA();
    } catch (e) { setErreur((e as Error).message); setDepot(false); }
  };

  const lancerIA = async (forcer = false) => {
    if (!etat) return;
    setErreur(""); setAnalyse({ fait: 0, total: 0, restant: null });
    demanderNotification();
    try {
      const tache = await api.analyserIA(etat.id, remplir, forcer, lg);
      setEtat((p) => p && { ...p, tache: { id: tache.id, nom: "ia" } });
      await suivre(tache);
    } catch (e) { setErreur((e as Error).message); setAnalyse(null); }
  };

  // Décisions : l'écran change tout de suite ; les requêtes partent l'une après l'autre, et la réponse de la
  // dernière remplace l'état affiché (anomalies, synthèse et fichier recalculés par le serveur)
  const file = useRef<Promise<unknown>>(Promise.resolve());
  const enAttente = useRef(0);
  const decider = (d: Decision[]) => {
    if (!etat || !d.length) return;
    const id = etat.id;
    const optimiste = d.every((x) => x.action !== "adopter");
    if (optimiste) setEtat((p) => p && p.id === id ? appliquer(p, d) : p);
    else setOccupe(true);
    enAttente.current += 1;
    file.current = file.current.then(async () => {
      try {
        const reponse = await api.decider(id, d, lg);
        if (enAttente.current === 1) setEtat((p) => p && p.id === id ? reponse : p);
      } catch (e) {
        setErreur((e as Error).message);
        api.audit(id, lg).then((r) => setEtat((p) => p && p.id === id ? r : p)).catch(() => undefined);
      } finally {
        enAttente.current -= 1;
        if (!optimiste) setOccupe(false);
      }
    });
  };

  // Urgence figée quand on change de filtre ou d'audit : une carte ne saute pas ailleurs pendant qu'on la traite
  const rangs = useMemo(() => new Map((etat?.constats ?? []).map((c) => [c.ligne, urgence(c)])),
    [etat?.id, tri, filtre, etat?.ia?.analyses, etat?.synthese.nb_constats]); // eslint-disable-line
  const constats = useMemo(() => {
    if (!etat) return [];
    const q = recherche.trim().toLowerCase();
    const garde = etat.constats.filter((c) => {
      if (estVide(c.valeurs.constat)) return false;
      if (q && !Object.values(c.valeurs).some((v) => String(v ?? "").toLowerCase().includes(q))) return false;
      if (filtre === "bloquants") return c.anomalies.some((a) => a.niveau === "bloquant");
      if (filtre === "a_valider") return Object.values(c.completions).some((x) => x.origine !== "valide");
      if (filtre === "avec_anomalie") return c.anomalies.some((a) => a.niveau !== "info");
      if (filtre === "a_revoir") return !!c.ecarts_ia && Object.values(c.ecarts_ia).some(Boolean);
      return true;
    });
    return tri === "urgence" ? garde.sort((a, b) => (rangs.get(b.ligne) ?? 0) - (rangs.get(a.ligne) ?? 0) || a.ligne - b.ligne) : garde;
  }, [etat, filtre, recherche, tri, rangs]);

  const [recents, setRecents] = useState<ResumeAudit[]>([]);
  useEffect(() => { if (!etat) api.lister().then((r) => setRecents(r.audits)).catch(() => undefined); }, [etat]);

  if (!etat) {
    return (
      <div className="space-y-6">
        <header>
          <h1 className="nn-page-title">{t("rel.titre")}</h1>
          <p className="mt-1 max-w-3xl text-sm text-texte-2">{t("rel.intro")}</p>
        </header>
        {erreur && <Alerte ton="danger">{erreur}</Alerte>}
        <Depot deposer={deposer} enCours={depot} />
        {recents.length > 0 && (
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold">{t("h.recents")}</h2>
              <button onClick={allerHistorique} className="btn-discret text-xs">{t("h.tout_voir")}<Icone nom="fleche" className="size-3.5" /></button>
            </div>
            <ListeAudits audits={recents.slice(0, 5)} ouvrir={ouvrir} />
          </div>
        )}
      </div>
    );
  }

  const s = etat.synthese;
  const n = s.nb_constats || 1;
  const ctx = etat.audit.contexte;
  const champsVides = CHAMPS_VIDES.filter((c) => etat.anomalies.some((a) => a.code === "CHAMP_VIDE" && a.champ === c));
  const nbAnalysables = etat.constats.filter((c) => !estVide(c.valeurs.constat)).length;
  const aValiderTous = etat.constats.flatMap((c) => Object.entries(c.completions).filter(([, x]) => x.origine !== "valide").map(([k]) => ({ ligne: c.ligne, champ: k, action: "valider" })));
  const anomaliesFiltrees = etat.anomalies.filter((a) => niveaux.includes(a.niveau));
  const libelleGravite = (g: string) => ref.gravites.find((x) => String(x.niveau) === g)?.libelle ?? g;

  return (
    <div className="space-y-6">
      {/* En-tête */}
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <h1 className="nn-page-title truncate">{etat.nom}</h1>
          <p className="mt-1 text-sm text-texte-2">
            {[ctx.produit, ctx.designer, ctx.plateforme, ctx.date].filter((x) => !estVide(x)).join(" · ") || t("rel.contexte_vide")}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <label className="btn-secondaire cursor-pointer" title={t("rel.version_aide")}>
            <Icone nom="rafraichir" className="size-4" />{t("rel.version")}
            <input type="file" accept=".xlsx" className="hidden" disabled={tacheEnCours || depot}
              onChange={(e) => { const f = e.target.files?.[0]; if (f) nouvelleVersion(f); e.target.value = ""; }} />
          </label>
          <label className="btn-secondaire cursor-pointer">
            <Icone nom="importer" className="size-4" />{t("rel.autre")}
            <input type="file" accept=".xlsx" className="hidden" onChange={(e) => { const f = e.target.files?.[0]; if (f) deposer(f); e.target.value = ""; }} />
          </label>
          <Lien variante="primaire" icone="telecharger" href={api.fichierUrl(etat.id)} download={etat.nom_sortie}>
            {etat.nb_completions ? t("rel.telecharger_complete") : t("rel.telecharger")}
          </Lien>
        </div>
      </header>

      {erreur && <Alerte ton="danger">{erreur}</Alerte>}
      {etat.tache?.nom === "rapport" && <Alerte ton="ia">{t("rel.rapport_en_cours")}</Alerte>}
      {version && <Alerte ton="ok">{version}</Alerte>}
      {depot && <Alerte ton="info"><span className="inline-flex items-center gap-2"><Spinner /> {t("rel.lecture")}</span></Alerte>}

      <Alerte ton={s.pret ? "ok" : "danger"} titre={s.pret ? t("rel.pret") : t("rel.bloquants", { n: s.nb_bloquants })}
        action={<span className="flex flex-wrap gap-1">
          {!s.pret && <Bouton variante="discret" className="text-xs" onClick={() => montrer("bloquants")}>{t("rel.voir_bloquants")}<Icone nom="fleche" className="size-3.5" /></Bouton>}
          {etat.a_valider > 0 && <Bouton variante="discret" className="text-xs" onClick={() => montrer("a_valider")}>{t("rel.voir_a_valider")}</Bouton>}
          {etat.a_valider > 0 && <Bouton variante="discret" className="text-xs" disabled={occupe || tacheEnCours} onClick={() => decider(aValiderTous)}><Icone nom="check" className="size-3.5" />{t("c.tout_valider_audit", { n: etat.a_valider })}</Bouton>}
        </span>}>
        {etat.a_valider > 0 && t("c.a_valider", { n: etat.a_valider })}
      </Alerte>

      {/* Chiffres */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        <Metrique libelle={t("rel.m.constats")} valeur={s.nb_constats} detail={t("rel.m.types", { p: s.nb_problemes, f: s.nb_points_forts })}
          onClick={() => montrer("tous")} actif={onglet === "constats" && filtre === "tous"} />
        <Metrique libelle={t("rel.m.conformes")} valeur={pct(s.conformes / n)} detail={s.nb_constats - s.conformes ? t("rel.m.voir", { n: s.nb_constats - s.conformes }) : undefined}
          onClick={() => montrer("bloquants")} actif={onglet === "constats" && filtre === "bloquants"} />
        <Metrique libelle={t("rel.m.sans_remarque")} valeur={pct(s.sans_remarque / n)} detail={s.nb_constats - s.sans_remarque ? t("rel.m.voir", { n: s.nb_constats - s.sans_remarque }) : undefined}
          onClick={() => montrer("avec_anomalie")} actif={onglet === "constats" && filtre === "avec_anomalie"} />
        <Metrique libelle={t("rel.m.facultatifs")} valeur={pct(s.completude_recommandee)} aide={t("rel.m.facultatifs_aide")} detail={t("rel.m.facultatifs_aide")} />
        <Metrique libelle={t("rel.m.cites")} valeur={`${ref.criteres.length - s.non_couverts.length} / ${ref.criteres.length}`} detail={t("rel.m.voir_couverture")}
          onClick={() => { setOnglet("couverture"); requestAnimationFrame(() => liste.current?.scrollIntoView({ behavior: "smooth", block: "start" })); }} actif={onglet === "couverture"} />
      </div>

      {/* IA */}
      <Section titre={<span className="inline-flex items-center gap-2"><Icone nom="ia" className="size-5 text-ia" />{t("ia.panneau")}</span>} intro={etat.ia ? undefined : t("ia.panneau_intro")}
        action={etat.ia ? <Bouton variante="primaire" icone="rapport" onClick={allerRapport}>{t("r.titre")}</Bouton> : undefined}>
        {analyse ? (
          <Progression fait={analyse.fait} total={analyse.total} libelle={analyse.total ? [t("ia.progression", { f: analyse.fait, n: analyse.total }), dureeRestante(analyse.restant, lg)].filter(Boolean).join(" · ") : t("ia.demarrage")} />
        ) : etat.ia ? (
          <div className="flex flex-wrap items-center justify-between gap-3 text-sm">
            <p className="text-texte-2">
              {t("ia.faite", { n: etat.ia.analyses, c: etat.ia.criteres_a_revoir, r: etat.ia.recos_a_ameliorer })}
              {etat.ia.erreurs > 0 && <> · <span className="text-danger">{t("ia.erreurs", { n: etat.ia.erreurs })}</span></>}
              {etat.ia.depuis_cache > 0 && <> · {t("ia.depuis_cache", { n: etat.ia.depuis_cache })}</>}
            </p>
            {etat.ia.depuis_cache > 0 && <><ChoixModele compact /><Bouton variante="discret" icone="rafraichir" disabled={tacheEnCours} onClick={() => lancerIA(true)}>{t("ia.refaire")}</Bouton></>}
          </div>
        ) : (
          <div className="space-y-3">
            {champsVides.length > 0 && <p className="text-sm">{t("ia.vides", { liste: champsVides.map((c) => (ref.champs[c] ?? c).toLowerCase()).join(", ") })}</p>}
            <ChoixModele compact />
            <div className="flex flex-wrap items-center gap-4">
              <Bouton variante="ia" icone="ia" disabled={!config.ia.active || tacheEnCours} onClick={() => lancerIA()}>{t("ia.lancer", { n: nbAnalysables })}</Bouton>
              <label className="flex items-center gap-2 text-sm text-texte-2" title={t("ia.remplir_aide")}>
                <input type="checkbox" className="accent-[var(--ia)]" checked={remplir} onChange={(e) => setRemplir(e.target.checked)} />
                {t("ia.remplir")}
              </label>
            </div>
            <p className="text-xs text-texte-3">{config.ia.active ? t("ia.duree") : t("ia.indisponible")}</p>
          </div>
        )}
      </Section>

      {/* Onglets */}
      <div ref={liste} className="scroll-mt-20">
        <Onglets<Onglet> actif={onglet} choisir={setOnglet} onglets={[
          { id: "constats", libelle: t("o.constats"), compte: nbAnalysables },
          { id: "anomalies", libelle: t("o.anomalies"), compte: etat.anomalies.length },
          { id: "couverture", libelle: t("o.couverture") },
          { id: "gravite", libelle: t("o.gravite") },
        ]} />
        <div className="pt-5">
          {onglet === "constats" && (
            <div className="space-y-4">
              <div className="flex flex-wrap items-center gap-3">
                <div className="relative min-w-60 flex-1">
                  <Icone nom="recherche" className="absolute top-1/2 left-3 size-4 -translate-y-1/2 text-texte-3" />
                  <input className="champ pl-9" placeholder={t("f.rechercher")} value={recherche} onChange={(e) => setRecherche(e.target.value)} aria-label={t("f.rechercher")} />
                </div>
                <div className="flex flex-wrap gap-1 rounded-md border border-bord bg-surface p-0.5">
                  {(["tous", ...(s.pret ? [] : ["bloquants"]), "a_valider", "avec_anomalie", ...(etat.ia ? ["a_revoir"] : [])] as Filtre[]).map((f) => (
                    <button key={f} onClick={() => setFiltre(f)} aria-pressed={filtre === f}
                      className={cx("rounded-md px-2.5 py-1 text-xs font-medium", filtre === f ? "bg-marque-doux text-marque" : "text-texte-2 hover:text-texte")}>
                      {t(`f.${f}`)}
                    </button>
                  ))}
                </div>
                <label className="flex items-center gap-2 text-xs text-texte-2">
                  {t("f.trier")}
                  <select className="champ w-auto py-1 text-xs" value={tri} onChange={(e) => setTri(e.target.value as Tri)}>
                    <option value="urgence">{t("f.tri_urgence")}</option>
                    <option value="fichier">{t("f.tri_fichier")}</option>
                  </select>
                </label>
              </div>
              {constats.length ? constats.map((c) => <CarteConstat key={c.ligne} c={c} config={config} decider={decider} occupe={occupe || tacheEnCours} />)
                : <p className="py-10 text-center text-sm text-texte-3">{t("f.aucun")}</p>}
            </div>
          )}

          {onglet === "anomalies" && (
            etat.anomalies.length === 0 ? <p className="text-sm text-texte-2">{t("a.aucune")}</p> : (
              <div className="space-y-3">
                <div className="flex flex-wrap gap-2">
                  {(["bloquant", "avertissement", "info"] as const).map((niv) => (
                    <button key={niv} aria-pressed={niveaux.includes(niv)} onClick={() => setNiveaux(niveaux.includes(niv) ? niveaux.filter((x) => x !== niv) : [...niveaux, niv])}
                      className={cx("rounded-full border px-3 py-1 text-xs font-medium", niveaux.includes(niv) ? "border-transparent bg-surface-2 text-texte" : "border-bord text-texte-3 line-through")}>
                      {t(`niveau.${niv}`)} · {etat.anomalies.filter((a) => a.niveau === niv).length}
                    </button>
                  ))}
                </div>
                <div className="carte overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-surface-2 text-left text-xs text-texte-2">
                      <tr>{["", t("c.ligne", { n: "" }).trim(), t("s.constat"), "", ""].map((h, i) => <th key={i} className="px-3 py-2 font-medium">{h}</th>)}</tr>
                    </thead>
                    <tbody className="divide-y divide-bord">
                      {anomaliesFiltrees.map((a: Anomalie, i) => (
                        <tr key={i} className="align-top">
                          <td className="px-3 py-2"><Badge ton={TON_NIVEAU[a.niveau]}>{t(`niveau.${a.niveau}`)}</Badge></td>
                          <td className="px-3 py-2 tabular-nums text-texte-2">{a.ligne ?? t("a.fichier")}</td>
                          <td className="px-3 py-2 font-mono text-xs">{a.constat}</td>
                          <td className="px-3 py-2 text-texte-2">{a.champ ? ref.champs[a.champ] ?? a.champ : ""}</td>
                          <td className="px-3 py-2">{a.message}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )
          )}

          {onglet === "couverture" && (
            <div className="space-y-5">
              <p className="max-w-3xl text-sm text-texte-2">{t("cv.intro")}</p>
              <div className="flex gap-4 text-xs text-texte-2">
                <span className="flex items-center gap-1.5"><span className="size-2.5 rounded-sm bg-[var(--serie)]" />{t("cv.principal")}</span>
                <span className="flex items-center gap-1.5"><span className="size-2.5 rounded-sm bg-[var(--serie)] opacity-35" />{t("cv.secondaire")}</span>
              </div>
              {ref.categories.map((cat) => (
                <div key={cat.code} className="carte p-4">
                  <h3 className="mb-3 text-sm font-semibold">{cat.libelle}</h3>
                  <BarresHorizontales largeurLibelle="18rem" barres={ref.criteres.filter((c) => c.categorie === cat.code).map((c) => ({
                    cle: c.code, libelle: `${c.code} – ${lg === "en" ? c.nom : c.nom_fr}`, valeur: s.par_critere[c.code] ?? 0,
                    secondaire: s.secondaires[c.code] ?? 0, detail: c.definition,
                    couleur: s.non_couverts.includes(c.code) ? "var(--g0)" : undefined,
                  }))} max={Math.max(1, ...ref.criteres.map((c) => (s.par_critere[c.code] ?? 0) + (s.secondaires[c.code] ?? 0)))} />
                </div>
              ))}
              {s.non_couverts.length > 0 && <Alerte ton="alerte" titre={t("cv.jamais", { n: s.non_couverts.length })}>{s.non_couverts.join(", ")}</Alerte>}
            </div>
          )}

          {onglet === "gravite" && (
            <div className="carte p-5">
              <h3 className="mb-4 text-sm font-semibold">{t("g.problemes")}</h3>
              <BarresHorizontales largeurLibelle="10rem" barres={Object.entries(s.gravites).map(([g, v]) => ({ cle: g, libelle: `${g} – ${libelleGravite(g)}`, valeur: v, couleur: couleurGravite(Number(g)), detail: ref.gravites.find((x) => String(x.niveau) === g)?.definition }))} />
            </div>
          )}
        </div>
      </div>

      <details className="text-xs text-texte-3">
        <summary className="cursor-pointer">{t("technique")}</summary>
        <pre className="mt-2 overflow-x-auto rounded-md bg-surface-2 p-3">{JSON.stringify(etat.audit, null, 2)}</pre>
      </details>
    </div>
  );
}
