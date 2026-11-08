import { useCallback, useEffect, useState } from "react";
import { api } from "./api";
import { LangueContext, traduire, type Cle } from "./i18n";
import type { Config, EtatAudit, Langue, Rapport } from "./types";
import { Alerte, Icone, Spinner, cx } from "./components/ui";
import PageRelecture from "./pages/Relecture";
import PageSuggestion from "./pages/Suggestion";
import PageRapport from "./pages/Rapport";
import PageReglages from "./pages/Reglages";
import PageHistorique from "./pages/Historique";
import logoApp from "./assets/auditergo.svg";

type Page = "relecture" | "suggestion" | "rapport" | "historique" | "reglages";
const PAGES: { id: Page; cle: Cle; icone: string }[] = [
  { id: "relecture", cle: "nav.relecture", icone: "relecture" },
  { id: "suggestion", cle: "nav.suggestion", icone: "suggestion" },
  { id: "rapport", cle: "nav.rapport", icone: "rapport" },
  { id: "historique", cle: "nav.historique", icone: "historique" },
  { id: "reglages", cle: "nav.reglages", icone: "reglages" },
];

function lire(cle: string) {
  try { return localStorage.getItem(cle); } catch { return null; }
}
function ecrire(cle: string, valeur: string) {
  try { localStorage.setItem(cle, valeur); } catch { /* stockage indisponible */ }
}

function pageDepuisAdresse(): Page {
  const p = window.location.hash.replace("#", "") as Page;
  return PAGES.some((x) => x.id === p) ? p : "relecture";
}

export default function App() {
  const [langue, setLangue] = useState<Langue>((lire("langue") as Langue) || "fr");
  const [theme, setTheme] = useState<"clair" | "sombre">(
    (lire("theme") as "clair" | "sombre") || (window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "sombre" : "clair"));
  const [page, setPage] = useState<Page>(pageDepuisAdresse);
  const [config, setConfig] = useState<Config | null>(null);
  const [erreur, setErreur] = useState("");
  const [etat, setEtat] = useState<EtatAudit | null>(null);
  const [rapport, setRapport] = useState<Rapport | null>(null);
  const t = (cle: Cle, v?: Record<string, string | number>) => traduire(langue, cle, v);

  // Thème : appliqué sur <html> ; l'impression se fait toujours en clair
  useEffect(() => {
    document.documentElement.dataset.theme = theme === "sombre" ? "dark" : "light";
    const avant = () => (document.documentElement.dataset.theme = "light");
    const apres = () => (document.documentElement.dataset.theme = theme === "sombre" ? "dark" : "light");
    window.addEventListener("beforeprint", avant);
    window.addEventListener("afterprint", apres);
    return () => { window.removeEventListener("beforeprint", avant); window.removeEventListener("afterprint", apres); };
  }, [theme]);

  useEffect(() => { document.documentElement.lang = langue; document.title = t("app"); }, [langue]); // eslint-disable-line

  useEffect(() => {
    const ecouter = () => setPage(pageDepuisAdresse());
    window.addEventListener("hashchange", ecouter);
    return () => window.removeEventListener("hashchange", ecouter);
  }, []);

  const chargerConfig = useCallback(async (lg: Langue) => {
    try {
      const c = await api.config(lg);
      setConfig(c);
      if (!lire("langue") && c.langue_defaut !== lg) setLangue(c.langue_defaut);
      setErreur("");
    } catch (e) {
      setErreur((e as Error).message);
    }
  }, []);
  useEffect(() => { chargerConfig(langue); }, [langue, chargerConfig]);

  // L'audit ouvert est retrouvé après un rechargement de la page ou un redémarrage de l'application
  useEffect(() => {
    if (etat) ecrire("audit", etat.id);
  }, [etat?.id]); // eslint-disable-line
  useEffect(() => {
    const id = lire("audit");
    if (id) api.audit(id, langue).then(setEtat).catch(() => ecrire("audit", ""));
  }, []); // eslint-disable-line
  // Le rapport affiché est celui de l'audit ouvert
  useEffect(() => { setRapport(null); }, [etat?.id]);

  const ouvrir = async (id: string) => {
    try { setEtat(await api.audit(id, langue)); aller("relecture"); } catch (e) { setErreur((e as Error).message); }
  };
  const oublier = (id: string) => {
    if (etat?.id === id) { setEtat(null); ecrire("audit", ""); }
  };

  // Changer de langue relance les contrôles de l'audit (sans IA) dans la nouvelle langue
  useEffect(() => {
    if (etat && etat.langue !== langue) api.audit(etat.id, langue).then(setEtat).catch((e) => setErreur(e.message));
  }, [langue]); // eslint-disable-line

  const aller = (p: Page) => { window.location.hash = p; setPage(p); window.scrollTo(0, 0); };
  const changerLangue = (lg: Langue) => { setLangue(lg); ecrire("langue", lg); };
  const changerTheme = () => { const n = theme === "sombre" ? "clair" : "sombre"; setTheme(n); ecrire("theme", n); };

  return (
    <LangueContext.Provider value={langue}>
      <div className="min-h-screen">
        {/* En-tête commun de la suite (Night Navy 1.1.0) */}
        <header className="nn-appbar no-print sticky top-0 z-30">
          <a href="#relecture" className="nn-appbar-brand" onClick={(e) => { e.preventDefault(); aller("relecture"); }}>
            <img className="nn-appbar-icon" src={logoApp} alt="" />
            {t("app")}
          </a>
          <nav className="nn-appbar-nav" aria-label={t("app")}>
            {PAGES.filter((p) => p.id !== "reglages").map((p) => (
              <button key={p.id} type="button" onClick={() => aller(p.id)} aria-current={page === p.id ? "page" : undefined}
                className={cx("nn-appbar-tab gap-2", page === p.id && "is-active")}>
                {t(p.cle)}
                {p.id === "relecture" && etat && <span className="size-1.5 rounded-full bg-ok" aria-hidden="true" />}
                {p.id === "rapport" && etat && etat.rapport !== "aucun" && <span className="size-1.5 rounded-full bg-ok" aria-hidden="true" />}
              </button>
            ))}
          </nav>
          <div className="nn-appbar-tools">
            {config && (
              <button type="button" onClick={() => aller("reglages")}
                title={config.ia.active ? (config.ia.locale ? config.ia.modele : `${config.ia.modele} · ${config.ia.hote}`) : t("ia.titre")}
                className={cx("flex min-h-8 items-center gap-2 rounded-full px-3 text-[13px] font-medium",
                  config.ia.active ? "bg-success-soft text-success-text" : "bg-surface-3 text-texte-2")}>
                <span className={cx("size-2 rounded-full", config.ia.active ? "bg-ok" : "bg-texte-3")} aria-hidden="true" />
                <span className="hidden sm:inline">{config.ia.active ? t("ia.connecte") : t("ia.titre")}</span>
              </button>
            )}
            <div className="nn-segmented" role="group" aria-label={t("langue")}>
              {(["fr", "en"] as Langue[]).map((lg) => (
                <button key={lg} type="button" onClick={() => changerLangue(lg)} aria-pressed={langue === lg}>{lg.toUpperCase()}</button>
              ))}
            </div>
            <button type="button" onClick={changerTheme} className="nn-icon-btn" aria-label={t("theme")}
              title={theme === "sombre" ? t("theme.clair") : t("theme.sombre")}>
              <Icone nom={theme === "sombre" ? "soleil" : "lune"} className="size-[18px]" />
            </button>
            <button type="button" onClick={() => aller("reglages")} aria-label={t("nav.reglages")} title={t("nav.reglages")}
              aria-current={page === "reglages" ? "page" : undefined}
              className={cx("nn-icon-btn", page === "reglages" && "bg-accent-soft text-accent-ink")}>
              <Icone nom="reglages" className="size-[19px]" />
            </button>
          </div>
        </header>

        {/* Contenu */}
        <main className="min-w-0">
          <div className="print-plein mx-auto max-w-[1240px] px-4 py-6 sm:px-8 lg:py-10">
            {erreur && <div className="no-print mb-4"><Alerte ton="danger">{erreur}</Alerte></div>}
            {!config ? (
              !erreur && <div className="flex items-center gap-2 text-sm text-texte-2"><Spinner /> {t("chargement")}</div>
            ) : (
              <>
                {page === "relecture" && <PageRelecture config={config} etat={etat} setEtat={setEtat} allerRapport={() => aller("rapport")} ouvrir={ouvrir} allerHistorique={() => aller("historique")} />}
                {page === "suggestion" && <PageSuggestion config={config} />}
                {page === "rapport" && <PageRapport config={config} etat={etat} rapport={rapport} setRapport={setRapport} setEtat={setEtat} allerRelecture={() => aller("relecture")} />}
                {page === "historique" && <PageHistorique config={config} ouvert={etat?.id} ouvrir={ouvrir} oublier={oublier} />}
                {page === "reglages" && <PageReglages config={config} recharger={() => chargerConfig(langue)} />}
              </>
            )}
          </div>
        </main>
      </div>
    </LangueContext.Provider>
  );
}
