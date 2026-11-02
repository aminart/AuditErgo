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
      <div className="min-h-screen lg:grid lg:grid-cols-[16rem_1fr]">
        {/* Barre latérale */}
        <aside className="no-print border-b border-bord bg-surface lg:sticky lg:top-0 lg:h-screen lg:border-r lg:border-b-0">
          <div className="flex h-full flex-col gap-4 p-4">
            <div className="flex items-center gap-3 px-1">
              <div className="grid size-9 place-items-center rounded-lg bg-marque text-white dark:text-[#0f1a2e]">
                <Icone nom="recherche" className="size-5" />
              </div>
              <div className="min-w-0">
                <div className="text-sm leading-tight font-semibold">{t("app")}</div>
                <div className="truncate text-xs text-texte-3">{config ? `v${config.referentiel.version}` : ""}</div>
              </div>
            </div>
            <nav className="flex gap-1 overflow-x-auto lg:flex-col">
              {PAGES.map((p) => (
                <button key={p.id} onClick={() => aller(p.id)} aria-current={page === p.id ? "page" : undefined}
                  className={cx("flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium whitespace-nowrap transition-colors",
                    page === p.id ? "bg-marque-doux text-marque" : "text-texte-2 hover:bg-surface-2 hover:text-texte")}>
                  <Icone nom={p.icone} className="size-[18px]" />
                  {t(p.cle)}
                  {p.id === "relecture" && etat && <span className="ml-auto size-1.5 rounded-full bg-ok" aria-hidden="true" />}
                  {p.id === "rapport" && etat && etat.rapport !== "aucun" && <span className="ml-auto size-1.5 rounded-full bg-ok" aria-hidden="true" />}
                </button>
              ))}
            </nav>
            <div className="mt-auto hidden space-y-3 lg:block">
              {config && (
                <button onClick={() => aller("reglages")} className="w-full rounded-lg border border-bord px-3 py-2.5 text-left text-xs hover:bg-surface-2">
                  <div className="flex items-center gap-1.5 font-medium text-texte">
                    <span className={cx("size-2 rounded-full", config.ia.active ? "bg-ok" : "bg-texte-3")} aria-hidden="true" />
                    {config.ia.active ? config.ia.modele : t("ia.titre")}
                  </div>
                  <div className="mt-0.5 flex items-center gap-1 text-texte-3">
                    <Icone nom={config.ia.locale ? "cadenas" : "globe"} className="size-3" />
                    {config.ia.active ? (config.ia.locale ? t("ia.local").split(":")[0] : config.ia.hote) : t("ia.desactivee").split(":")[0]}
                  </div>
                </button>
              )}
              <div className="flex items-center gap-2">
                <div className="flex flex-1 rounded-lg border border-bord p-0.5" role="group" aria-label={t("langue")}>
                  {(["fr", "en"] as Langue[]).map((lg) => (
                    <button key={lg} onClick={() => changerLangue(lg)} aria-pressed={langue === lg}
                      className={cx("flex-1 rounded-md py-1 text-xs font-semibold uppercase", langue === lg ? "bg-surface-2 text-texte" : "text-texte-3 hover:text-texte")}>
                      {lg}
                    </button>
                  ))}
                </div>
                <button onClick={changerTheme} className="btn-discret rounded-lg border border-bord p-1.5" aria-label={t("theme")}
                  title={theme === "sombre" ? t("theme.clair") : t("theme.sombre")}>
                  <Icone nom={theme === "sombre" ? "soleil" : "lune"} className="size-4" />
                </button>
              </div>
            </div>
          </div>
        </aside>

        {/* Contenu */}
        <main className="min-w-0">
          <div className="no-print flex items-center justify-end gap-2 border-b border-bord bg-surface px-4 py-2 lg:hidden">
            {(["fr", "en"] as Langue[]).map((lg) => (
              <button key={lg} onClick={() => changerLangue(lg)} aria-pressed={langue === lg}
                className={cx("rounded-md px-2 py-1 text-xs font-semibold uppercase", langue === lg ? "bg-surface-2" : "text-texte-3")}>{lg}</button>
            ))}
            <button onClick={changerTheme} className="btn-discret p-1.5" aria-label={t("theme")}><Icone nom={theme === "sombre" ? "soleil" : "lune"} className="size-4" /></button>
          </div>
          <div className="print-plein mx-auto max-w-6xl px-4 py-6 sm:px-6 lg:px-10 lg:py-8">
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
