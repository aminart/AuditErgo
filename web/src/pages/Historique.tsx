import { useEffect, useState } from "react";
import { api } from "../api";
import { useLangue, useT } from "../i18n";
import type { Comparaison, Config, ProfilAudit, ResumeAudit } from "../types";
import { Alerte, Bouton, Icone, Spinner, cx } from "../components/ui";
import { PastilleGravite, couleurGravite } from "../components/graphiques";

const date = (iso: string, lg: string) => {
  try { return new Date(iso).toLocaleString(lg === "en" ? "en-GB" : "fr-FR", { dateStyle: "medium", timeStyle: "short" }); } catch { return iso; }
};

/** Répartition des gravités en une barre fine (sans légende : la page en donne une). */
function MiniGravites({ gravites }: { gravites: Record<string, number> }) {
  const total = Object.values(gravites).reduce((a, b) => a + b, 0);
  if (!total) return <div className="h-1.5 rounded-full bg-surface-2" />;
  return (
    <div className="flex h-1.5 gap-px overflow-hidden rounded-full">
      {["1", "2", "3", "4"].filter((g) => gravites[g]).map((g) => (
        <div key={g} style={{ width: `${(gravites[g] / total) * 100}%`, background: couleurGravite(Number(g)) }} />
      ))}
    </div>
  );
}

export function ListeAudits({ audits, ouvert, ouvrir, supprimer, selection, basculer }: {
  audits: ResumeAudit[]; ouvert?: string; ouvrir: (id: string) => void; supprimer?: (a: ResumeAudit) => void;
  selection?: string[]; basculer?: (id: string) => void;
}) {
  const t = useT();
  const lg = useLangue();
  return (
    <ul className="divide-y divide-bord overflow-hidden rounded-xl border border-bord bg-surface">
      {audits.map((a) => {
        const choisi = selection?.includes(a.id);
        return (
          <li key={a.id} className={cx("flex items-center gap-4 px-4 py-3", choisi && "bg-marque-doux/60")}>
            {basculer && (
              <input type="checkbox" checked={!!choisi} onChange={() => basculer(a.id)} aria-label={`${t("h.comparer")} : ${a.nom}`}
                disabled={!choisi && (selection?.length ?? 0) >= 2} className="size-4 accent-[var(--marque)]" />
            )}
            <button onClick={() => ouvrir(a.id)} className="min-w-0 flex-1 text-left">
              <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5">
                <span className="truncate font-medium">{a.produit || a.nom}</span>
                {a.id === ouvert && <span className="rounded-full bg-ok-doux px-2 py-0.5 text-[11px] font-medium text-ok">{t("h.ouvert")}</span>}
                {a.ia && <Icone nom="ia" className="size-3.5 text-ia" />}
                {a.rapport && <Icone nom="rapport" className="size-3.5 text-texte-3" />}
              </div>
              <div className="mt-0.5 truncate text-xs text-texte-3">
                {[a.produit ? a.nom : null, a.designer, a.date, t("h.modifie", { d: date(a.modifie, lg) })].filter(Boolean).join(" · ")}
              </div>
            </button>
            <div className="hidden w-40 shrink-0 sm:block">
              <div className="mb-1 text-right text-xs tabular-nums text-texte-2">{t("h.problemes", { n: a.nb_problemes })}</div>
              <MiniGravites gravites={a.gravites} />
            </div>
            {supprimer && (
              <button onClick={() => supprimer(a)} className="btn-discret p-1.5 hover:text-danger" title={t("h.supprimer")} aria-label={`${t("h.supprimer")} : ${a.nom}`}>
                <Icone nom="croix" className="size-4" />
              </button>
            )}
          </li>
        );
      })}
    </ul>
  );
}

/* --- Comparaison de deux audits --------------------------------------------------------------------- */

function Ecart({ avant, apres, moinsEstMieux = true }: { avant: number; apres: number; moinsEstMieux?: boolean }) {
  const t = useT();
  const d = apres - avant;
  if (d === 0) return <span className="text-xs text-texte-3">= {t("cmp.stable")}</span>;
  const mieux = moinsEstMieux ? d < 0 : d > 0;
  return (
    <span className={cx("inline-flex items-center gap-0.5 rounded-full px-2 py-0.5 text-xs font-semibold tabular-nums", mieux ? "bg-ok-doux text-ok" : "bg-danger-doux text-danger")}
      title={mieux ? t("cmp.mieux") : t("cmp.moins_bien")}>
      {d > 0 ? "▲" : "▼"} {d > 0 ? `+${d}` : d}
    </span>
  );
}

function VueComparaison({ c, config, inverser, fermer }: { c: Comparaison; config: Config; inverser: () => void; fermer: () => void }) {
  const t = useT();
  const { a, b } = c;
  const lignes: [string, (p: ProfilAudit) => number, boolean][] = [
    [t("cmp.problemes"), (p) => p.nb_problemes, true],
    [t("cmp.graves"), (p) => p.graves, true],
    [t("cmp.ecrans"), (p) => p.ecrans.length, true],
    [t("cmp.forts"), (p) => p.nb_points_forts, false],
    [t("cmp.maturite"), (p) => p.maturite_indicative, false],
  ];
  const maxGravite = Math.max(1, ...["1", "2", "3", "4"].flatMap((g) => [a.gravites[g] ?? 0, b.gravites[g] ?? 0]));
  const maxCat = Math.max(1, ...c.categories.flatMap((k) => [a.par_categorie[k.code] ?? 0, b.par_categorie[k.code] ?? 0]));
  const nouveaux = b.ecrans.filter((e) => !a.ecrans.includes(e));
  const resolus = a.ecrans.filter((e) => !b.ecrans.includes(e));
  const Entete = ({ p, cle }: { p: ProfilAudit; cle: "cmp.avant" | "cmp.apres" }) => (
    <div className="min-w-0">
      <div className="text-xs font-semibold tracking-wide text-texte-3 uppercase">{t(cle)}</div>
      <div className="truncate font-semibold">{p.produit || p.nom}</div>
      <div className="truncate text-xs text-texte-3">{[p.nom, p.date].filter(Boolean).join(" · ")}</div>
    </div>
  );
  const Barre = ({ v, max, couleur, attenue }: { v: number; max: number; couleur: string; attenue?: boolean }) => (
    <div className="flex h-4 items-center gap-1.5">
      <div className="h-full rounded-r" style={{ width: `${(v / max) * 100}%`, minWidth: v ? 4 : 0, background: couleur, opacity: attenue ? 0.4 : 1 }} />
      <span className="text-xs tabular-nums text-texte-2">{v}</span>
    </div>
  );

  return (
    <section className="carte space-y-6 p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-base font-semibold">{t("cmp.titre")}</h2>
        <div className="flex gap-2">
          <Bouton variante="discret" icone="rafraichir" onClick={inverser}>{t("cmp.inverser")}</Bouton>
          <Bouton variante="discret" icone="croix" onClick={fermer}>{t("cmp.fermer")}</Bouton>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-bord text-left align-bottom">
              <th className="pb-3" />
              <th className="pb-3 font-normal"><Entete p={a} cle="cmp.avant" /></th>
              <th className="pb-3 font-normal"><Entete p={b} cle="cmp.apres" /></th>
              <th className="pb-3" />
            </tr>
          </thead>
          <tbody className="divide-y divide-bord">
            {lignes.map(([libelle, val, moins]) => (
              <tr key={libelle}>
                <td className="py-2.5 pr-4 text-texte-2">{libelle}</td>
                <td className="py-2.5 pr-4 text-lg font-semibold tabular-nums">{val(a)}</td>
                <td className="py-2.5 pr-4 text-lg font-semibold tabular-nums">{val(b)}</td>
                <td className="py-2.5 text-right"><Ecart avant={val(a)} apres={val(b)} moinsEstMieux={moins} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <div>
          <h3 className="mb-3 text-sm font-semibold">{t("cmp.gravite")}</h3>
          <div className="mb-2 flex gap-4 text-xs text-texte-2">
            <span className="flex items-center gap-1.5"><span className="size-2.5 rounded-sm bg-texte-3 opacity-40" />{t("cmp.avant")}</span>
            <span className="flex items-center gap-1.5"><span className="size-2.5 rounded-sm bg-texte-3" />{t("cmp.apres")}</span>
          </div>
          <div className="space-y-3">
            {config.referentiel.gravites.map((g) => (
              <div key={g.niveau} className="grid grid-cols-[8rem_1fr_auto] items-center gap-3">
                <PastilleGravite niveau={g.niveau} libelle={g.libelle} />
                <div className="space-y-0.5">
                  <Barre v={a.gravites[String(g.niveau)] ?? 0} max={maxGravite} couleur={couleurGravite(g.niveau)} attenue />
                  <Barre v={b.gravites[String(g.niveau)] ?? 0} max={maxGravite} couleur={couleurGravite(g.niveau)} />
                </div>
                <Ecart avant={a.gravites[String(g.niveau)] ?? 0} apres={b.gravites[String(g.niveau)] ?? 0} />
              </div>
            ))}
          </div>
        </div>
        <div>
          <h3 className="mb-3 text-sm font-semibold">{t("cmp.categories")}</h3>
          <div className="space-y-3">
            {c.categories.filter((k) => (a.par_categorie[k.code] ?? 0) + (b.par_categorie[k.code] ?? 0) > 0).map((k) => (
              <div key={k.code} className="grid grid-cols-[minmax(0,10rem)_1fr_auto] items-center gap-3">
                <span className="truncate text-xs text-texte-2" title={k.libelle}>{k.libelle}</span>
                <div className="space-y-0.5">
                  <Barre v={a.par_categorie[k.code] ?? 0} max={maxCat} couleur="var(--serie)" attenue />
                  <Barre v={b.par_categorie[k.code] ?? 0} max={maxCat} couleur="var(--serie)" />
                </div>
                <Ecart avant={a.par_categorie[k.code] ?? 0} apres={b.par_categorie[k.code] ?? 0} />
              </div>
            ))}
          </div>
        </div>
      </div>

      {(nouveaux.length > 0 || resolus.length > 0) && (
        <div className="grid gap-4 sm:grid-cols-2">
          {resolus.length > 0 && <Alerte ton="ok" titre={t("cmp.ecrans_resolus")}>{resolus.join(", ")}</Alerte>}
          {nouveaux.length > 0 && <Alerte ton="alerte" titre={t("cmp.ecrans_nouveaux")}>{nouveaux.join(", ")}</Alerte>}
        </div>
      )}
      <p className="text-xs text-texte-3">{t("cmp.note")}</p>
    </section>
  );
}

/* --- Page ------------------------------------------------------------------------------------------- */

export default function PageHistorique({ config, ouvert, ouvrir, oublier }: {
  config: Config; ouvert?: string; ouvrir: (id: string) => void; oublier: (id: string) => void;
}) {
  const t = useT();
  const lg = useLangue();
  const [audits, setAudits] = useState<ResumeAudit[] | null>(null);
  const [persistant, setPersistant] = useState(true);
  const [selection, setSelection] = useState<string[]>([]);
  const [comparaison, setComparaison] = useState<Comparaison | null>(null);
  const [erreur, setErreur] = useState("");

  const charger = () => api.lister().then((r) => { setAudits(r.audits); setPersistant(r.persistant); }).catch((e) => setErreur(e.message));
  useEffect(() => { charger(); }, []);

  const comparer = async (ids: string[]) => {
    setErreur("");
    try { setComparaison(await api.comparer(ids[0], ids[1], lg)); } catch (e) { setErreur((e as Error).message); }
  };
  // L'audit le plus ancien est « avant » par défaut
  const lancerComparaison = () => {
    const tries = [...selection].sort((x, y) => (audits!.find((a) => a.id === x)!.cree < audits!.find((a) => a.id === y)!.cree ? -1 : 1));
    setSelection(tries);
    comparer(tries);
  };

  const supprimer = async (a: ResumeAudit) => {
    if (!window.confirm(t("h.confirmer_suppression", { n: a.produit || a.nom }))) return;
    await api.supprimer(a.id);
    oublier(a.id);
    setSelection(selection.filter((x) => x !== a.id));
    if (comparaison && (comparaison.a.id === a.id || comparaison.b.id === a.id)) setComparaison(null);
    charger();
  };

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">{t("h.titre")}</h1>
        <p className="mt-1 max-w-3xl text-sm text-texte-2">{t("h.intro")}</p>
      </header>
      {!persistant && <Alerte ton="alerte">{t("h.temporaire")}</Alerte>}
      {erreur && <Alerte ton="danger">{erreur}</Alerte>}
      {comparaison && <VueComparaison c={comparaison} config={config} fermer={() => setComparaison(null)}
        inverser={() => { const ids = [comparaison.b.id, comparaison.a.id]; setSelection(ids); comparer(ids); }} />}

      {audits === null ? <div className="flex items-center gap-2 text-sm text-texte-2"><Spinner /> {t("chargement")}</div>
        : audits.length === 0 ? <div className="carte p-8 text-center text-sm text-texte-3">{t("h.vide")}</div> : (
          <div className="space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <span className="text-sm text-texte-2">{t("h.selection", { n: selection.length })}</span>
              <Bouton variante="primaire" icone="rapport" disabled={selection.length !== 2} onClick={lancerComparaison}>{t("h.comparer")}</Bouton>
            </div>
            <ListeAudits audits={audits} ouvert={ouvert} ouvrir={ouvrir} supprimer={supprimer} selection={selection}
              basculer={(id) => setSelection(selection.includes(id) ? selection.filter((x) => x !== id) : [...selection, id].slice(-2))} />
          </div>
        )}
    </div>
  );
}
