import { useState } from "react";
import { api, attendre } from "../api";
import { useLangue, useT } from "../i18n";
import type { Config, Suggestion } from "../types";
import { Alerte, Bouton, Icone, Spinner, cx } from "../components/ui";
import SuggestionDetail from "../components/SuggestionDetail";

interface Entree { constat: string; ecran: string; s: Suggestion }

export default function PageSuggestion({ config }: { config: Config }) {
  const t = useT();
  const lg = useLangue();
  const ref = config.referentiel;
  const [f, setF] = useState({ constat: "", ecran: "", critere: "", recommandation: "", gravite: "", produit: "", cible: "", plateforme: "", forcer: false });
  const [enCours, setEnCours] = useState(false);
  const [erreur, setErreur] = useState("");
  const [historique, setHistorique] = useState<Entree[]>([]);
  const [choisi, setChoisi] = useState(0);
  const iaDispo = config.ia.active;
  const maj = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) =>
    setF({ ...f, [k]: e.target.type === "checkbox" ? (e.target as HTMLInputElement).checked : e.target.value });

  const proposer = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!f.constat.trim()) { setErreur(t("s.vide")); return; }
    setErreur("");
    setEnCours(true);
    try {
      const tache = await api.suggerer({
        constat: f.constat, ecran: f.ecran, critere: f.critere, recommandation: f.recommandation,
        gravite: f.gravite ? Number(f.gravite) : null, forcer: f.forcer, langue: lg,
        contexte: { produit: f.produit, cible: f.cible, plateforme: f.plateforme },
      });
      const r = await attendre(tache);
      setHistorique([{ constat: r.constat, ecran: r.ecran, s: r.suggestion }, ...historique]);
      setChoisi(0);
    } catch (err) {
      setErreur((err as Error).message);
    }
    setEnCours(false);
  };

  const actuel = historique[choisi];
  const option = (k: "facultatif") => <span className="font-normal text-texte-3"> · {t(`s.${k}`)}</span>;

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">{t("s.titre")}</h1>
        <p className="mt-1 max-w-3xl text-sm text-texte-2">{t("s.intro")}</p>
      </header>
      {!iaDispo && <Alerte ton="alerte">{t("ia.indisponible")}</Alerte>}

      <div className="grid grid-cols-1 items-start gap-6 xl:grid-cols-[minmax(0,26rem)_minmax(0,1fr)]">
        <form onSubmit={proposer} className="carte space-y-4 p-5 xl:sticky xl:top-6">
          <div>
            <label className="etiquette" htmlFor="constat">{t("s.constat")} <span className="text-danger">*</span></label>
            <textarea id="constat" className="champ min-h-28" placeholder={t("s.constat_ex")} value={f.constat} onChange={maj("constat")} />
          </div>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-1">
            <div>
              <label className="etiquette" htmlFor="ecran">{t("s.ecran")}{option("facultatif")}</label>
              <input id="ecran" className="champ" placeholder={t("s.ecran_ex")} value={f.ecran} onChange={maj("ecran")} />
            </div>
            <div>
              <label className="etiquette" htmlFor="gravite">{t("s.gravite")}{option("facultatif")}</label>
              <select id="gravite" className="champ" value={f.gravite} onChange={maj("gravite")}>
                <option value="">{t("s.non_renseignee")}</option>
                {ref.gravites.map((g) => <option key={g.niveau} value={g.niveau}>{g.niveau} – {g.libelle}</option>)}
              </select>
            </div>
          </div>
          <div>
            <label className="etiquette" htmlFor="critere">{t("s.critere")}{option("facultatif")}</label>
            <select id="critere" className="champ" value={f.critere} onChange={maj("critere")}>
              <option value="">{t("s.aucun")}</option>
              {ref.categories.map((cat) => (
                <optgroup key={cat.code} label={cat.libelle}>
                  {ref.criteres.filter((c) => c.categorie === cat.code).map((c) => <option key={c.code} value={c.code}>{c.libelle}</option>)}
                </optgroup>
              ))}
            </select>
          </div>
          <div>
            <label className="etiquette" htmlFor="reco">{t("s.reco")}{option("facultatif")}</label>
            <textarea id="reco" className="champ min-h-16" value={f.recommandation} onChange={maj("recommandation")} />
          </div>
          <details className="rounded-lg border border-bord px-3 py-2">
            <summary className="cursor-pointer text-sm font-medium">{t("s.contexte")}<span className="font-normal text-texte-3"> · {t("s.contexte_aide")}</span></summary>
            <div className="mt-3 space-y-3">
              {(["produit", "cible", "plateforme"] as const).map((k) => (
                <div key={k}>
                  <label className="etiquette text-xs" htmlFor={k}>{t(`s.${k}`)}</label>
                  <input id={k} className="champ" value={f[k]} onChange={maj(k)} />
                </div>
              ))}
            </div>
          </details>
          <label className="flex items-start gap-2 text-sm text-texte-2">
            <input type="checkbox" className="mt-0.5 accent-[var(--marque)]" checked={f.forcer} onChange={maj("forcer")} />
            {t("s.forcer")}
          </label>
          {erreur && <Alerte ton="danger">{erreur}</Alerte>}
          <Bouton variante="primaire" type="submit" className="w-full" disabled={!iaDispo || enCours}>
            {enCours ? <><Spinner /> {t("s.attente")}</> : <><Icone nom="ia" className="size-4" /> {t("s.proposer")}</>}
          </Bouton>
        </form>

        <div className="space-y-4">
          {actuel ? (
            <article className="carte p-6">
              <p className="mb-4 rounded-lg bg-surface-2 px-3 py-2 text-sm text-texte-2">
                {actuel.ecran && <span className="font-medium text-texte">{actuel.ecran} · </span>}{actuel.constat}
              </p>
              {actuel.s.erreur ? <Alerte ton="danger">{actuel.s.erreur}</Alerte> : <SuggestionDetail s={actuel.s} />}
            </article>
          ) : (
            <div className="carte grid min-h-64 place-items-center border-dashed p-6 text-center text-sm text-texte-3">
              <div><Icone nom="suggestion" className="mx-auto mb-2 size-8" />{t("s.vide_resultat")}</div>
            </div>
          )}
          {historique.length > 1 && (
            <div className="carte p-4">
              <h2 className="mb-2 text-sm font-semibold">{t("s.historique")}</h2>
              <ul className="divide-y divide-bord">
                {historique.map((h, i) => (
                  <li key={i}>
                    <button onClick={() => setChoisi(i)} className={cx("flex w-full items-center gap-3 px-2 py-2 text-left text-sm hover:bg-surface-2", i === choisi && "font-medium")}>
                      <span className="w-16 shrink-0 font-mono text-xs text-texte-2">{h.s.code}</span>
                      <span className="min-w-0 truncate" title={h.constat}>{h.ecran && `${h.ecran} · `}{h.constat}</span>
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
