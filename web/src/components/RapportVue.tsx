import { createContext, useContext } from "react";
import { formater } from "../i18n";
import type { Probleme, Rapport } from "../types";
import { BarreRepartition, BarresHorizontales, EchelleMaturite, PastilleGravite, couleurGravite } from "./graphiques";
import { cx } from "./ui";

export type Modifier = (chemin: string, valeur: string | number | string[]) => void;

/* --- Passages modifiables : texte lu à l'écran, zone de saisie en mode édition ------------------------ */

const Edition = createContext<{ actif: boolean; modifier: Modifier; aRediger: string }>({ actif: false, modifier: () => undefined, aRediger: "" });
const CHAMP_EDITION = "w-full resize-none rounded-md border border-dashed border-accent bg-info-doux/40 px-3 py-2 text-[15px] leading-relaxed text-texte focus:border-solid focus:outline-none focus:ring-2 focus:ring-accent/25";

function ajuster(el: HTMLTextAreaElement | null) {
  if (el) { el.style.height = "auto"; el.style.height = `${el.scrollHeight + 2}px`; }
}

/** Zone de saisie qui grandit avec son contenu ; enregistre en quittant le champ si le texte a changé. */
function Saisie({ valeur, enregistrer, lignes = false, libelle }: { valeur: string; enregistrer: (v: string) => void; lignes?: boolean; libelle?: string }) {
  return (
    <textarea ref={ajuster} key={valeur} defaultValue={valeur} aria-label={libelle}
      rows={lignes ? 3 : 1} className={CHAMP_EDITION} onInput={(e) => ajuster(e.currentTarget)}
      onBlur={(e) => { if (e.currentTarget.value.trim() !== valeur.trim()) enregistrer(e.currentTarget.value); }} />
  );
}

function ARediger() {
  const { aRediger } = useContext(Edition);
  return <span className="a-rediger">{aRediger}</span>;
}

/** Paragraphe du rapport ; vide, il est signalé « à rédiger ». */
function Texte({ chemin, texte, titre }: { chemin?: string; texte: string; titre?: string }) {
  const { actif, modifier } = useContext(Edition);
  return (
    <div className="bloc">
      {titre && <h4 className="mb-1 text-sm font-semibold text-texte">{titre}</h4>}
      {actif && chemin ? <Saisie valeur={texte} libelle={titre} lignes enregistrer={(v) => modifier(chemin, v)} />
        : texte ? <p className="leading-relaxed whitespace-pre-line">{texte}</p> : <p><ARediger /></p>}
    </div>
  );
}

/** Liste à puces ; en mode édition, un élément par ligne. */
function Liste({ chemin, elements }: { chemin?: string; elements: string[] }) {
  const { actif, modifier } = useContext(Edition);
  if (actif && chemin) return <Saisie valeur={elements.join("\n")} lignes enregistrer={(v) => modifier(chemin, v.split("\n"))} />;
  return elements.length ? <ul className="list-disc space-y-1 pl-5">{elements.map((e, i) => <li key={i}>{e}</li>)}</ul> : <p><ARediger /></p>;
}

/** Texte court (titre, cellule de tableau). */
function Court({ chemin, texte, vide }: { chemin: string; texte: string; vide?: boolean }) {
  const { actif, modifier } = useContext(Edition);
  if (actif) return <Saisie valeur={texte} enregistrer={(v) => modifier(chemin, v)} />;
  return <>{texte || (vide ? <ARediger /> : null)}</>;
}

/** Rapport de synthèse en HTML : même contenu que le rapport Word, lisible à l'écran et imprimable. En mode
 * édition, chaque passage rédigé se corrige sur place ; les exports reprennent les modifications. */
export default function RapportVue({ r, edition = false, modifier = () => undefined }: { r: Rapport; edition?: boolean; modifier?: Modifier }) {
  const L = (cle: string, v?: Record<string, string | number>) => (v ? formater(r.libelles[cle] ?? cle, v) : r.libelles[cle] ?? cle);
  const f = r.faits;
  const ctx = f.contexte;
  const parCle = Object.fromEntries(f.problemes.map((p) => [p.cle, p])) as Record<string, Probleme>;
  const gLib = (g: number | null) => (g ? r.gravites.find((x) => x.niveau === g)?.libelle ?? "" : L("non_renseignee"));
  const impact = (k: string) => (k ? L(`impact.${k}`) : "—");
  const effort = (k: string) => (k ? L(`effort.${k}`) : "—");
  const nbConstats = f.problemes.length + f.points_forts.length;

  const Tableau = ({ entetes, lignes, classes }: { entetes: string[]; lignes: React.ReactNode[][]; classes?: string[] }) => (
    <div className="overflow-x-auto rounded-md border border-bord">
      <table className="w-full text-sm">
        <thead className="bg-primary text-left text-xs text-on-primary">
          <tr>{entetes.map((h, i) => <th key={i} className={cx("px-3 py-2 font-semibold", classes?.[i]?.split(" ").filter((c) => c === "text-right" || c === "text-center").join(" "))}>{h}</th>)}</tr>
        </thead>
        <tbody className="divide-y divide-bord">
          {lignes.map((l, i) => <tr key={i} className="align-top even:bg-surface-2/50">{l.map((c, j) => <td key={j} className={cx("px-3 py-2", classes?.[j])}>{c}</td>)}</tr>)}
        </tbody>
      </table>
    </div>
  );
  const Gravite = ({ g }: { g: number | null }) => <PastilleGravite niveau={g} libelle={gLib(g)} />;

  const infos: [string, string | number | undefined][] = [
    [L("produit"), ctx.produit], [L("version"), ctx.version_produit], [L("client"), ctx.client], [L("cible"), ctx.cible],
    [L("plateforme"), ctx.plateforme], [L("parcours"), ctx.parcours], [L("designer"), ctx.designer], [L("date"), ctx.date],
    [L("referentiel"), `v${f.version_referentiel}`],
  ];
  const niveauxGravite = ["1", "2", "3", "4", ...(f.gravites.aucune ? ["aucune"] : [])];
  const sommaire = [["s1", "1"], ["s2", "2"], ["s3", "3"], ["s4", "4"], ["annexes", ""]] as const;
  const recurrents = r.themes.filter((th) => th.recurrent);
  const tries = [...f.problemes].sort((a, b) => (b.gravite ?? 0) - (a.gravite ?? 0) || a.ecran.localeCompare(b.ecran));

  return (
    <Edition.Provider value={{ actif: edition, modifier, aRediger: L("a_rediger") }}>
    <article id="rapport" className="rapport carte mx-auto max-w-4xl space-y-12 px-6 py-10 text-[15px] text-texte sm:px-12 sm:py-14">
      {/* Page de titre */}
      <header className="border-b border-bord pb-10">
        <p className="text-sm font-semibold tracking-widest text-texte-3 uppercase">{L("sous_titre")}</p>
        <h1 className="mt-2 text-4xl font-bold tracking-tight text-marque">{L("titre")}</h1>
        {ctx.produit && <p className="mt-2 text-xl text-texte-2">{ctx.produit}</p>}
        <dl className="mt-8 grid gap-x-8 gap-y-2 text-sm sm:grid-cols-2">
          {infos.filter(([, v]) => v !== undefined && v !== "").map(([k, v]) => (
            <div key={k} className="flex gap-2"><dt className="font-semibold">{k} :</dt><dd className="text-texte-2">{v}</dd></div>
          ))}
        </dl>
        <p className="mt-6 text-xs text-texte-3 italic">{r.ia ? L("redaction_ia", { m: r.modele }) : L("redaction_sans_ia")}</p>
        {r.erreur && <p className="mt-1 text-xs text-danger italic">{L("erreur_ia", { e: r.erreur })}</p>}
        <nav className="no-print mt-8 flex flex-wrap gap-2 text-sm">
          {sommaire.map(([cle, n]) => <a key={cle} href={`#r-${cle}`} className="rounded-full border border-bord px-3 py-1 text-texte-2 hover:bg-surface-2 hover:text-texte">{n && `${n}. `}{L(cle)}</a>)}
        </nav>
      </header>

      {/* 1. Synthèse générale */}
      <section id="r-s1" className="space-y-8">
        <h2>1. {L("s1")}</h2>
        <div className="bloc rounded-lg border-l-4 border-marque bg-marque-doux px-5 py-4">
          <h3 className="mb-1">{L("en_bref")}</h3>
          <Texte chemin="resume" texte={r.resume} />
        </div>

        <div className="bloc space-y-3">
          <h3>{L("maturite")}</h3>
          <EchelleMaturite niveaux={r.maturites} actuel={r.maturite} indicatif={f.maturite_indicative} libelleIndicatif={r.langue === "en" ? "indicative" : "indicatif"} />
          {edition ? (
            <select className={cx(CHAMP_EDITION, "w-auto font-semibold")} value={r.maturite} aria-label={L("maturite")}
              onChange={(e) => modifier("maturite", Number(e.target.value))}>
              {r.maturites.map((m) => <option key={m.niveau} value={m.niveau}>{L("maturite_niveau", { n: m.niveau, l: m.libelle })}</option>)}
            </select>
          ) : <p className="font-semibold">{L("maturite_niveau", { n: r.maturite, l: r.maturites[r.maturite - 1]?.libelle ?? "" })}</p>}
          <Texte chemin="maturite_justification" texte={r.maturite_justification} />
        </div>

        <div className="bloc space-y-4">
          <h3>{L("chiffres")}</h3>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {[[L("nb_constats"), nbConstats], [L("nb_problemes"), f.problemes.length], [L("nb_points_forts"), f.points_forts.length], [L("nb_ecrans"), f.ecrans.length]].map(([k, v]) => (
              <div key={k} className="rounded-lg border border-bord px-4 py-3">
                <div className="text-3xl font-semibold tabular-nums">{v}</div>
                <div className="text-xs text-texte-2">{k}</div>
              </div>
            ))}
          </div>
          <div>
            <h4 className="mb-6 text-sm font-semibold">{L("par_gravite")}</h4>
            <BarreRepartition unite={L("nb_problemes").toLowerCase()} segments={niveauxGravite.map((g) => ({
              cle: g, libelle: g === "aucune" ? L("non_renseignee") : `${g} · ${gLib(Number(g))}`, valeur: f.gravites[g] ?? 0, couleur: couleurGravite(g === "aucune" ? null : Number(g)),
            }))} />
          </div>
        </div>

        <div className="grid gap-8 sm:grid-cols-2">
          <div className="bloc"><h3 className="mb-2">{L("forts")}</h3><Liste chemin="points_forts" elements={r.points_forts} /></div>
          <div className="bloc"><h3 className="mb-2">{L("faiblesses")}</h3><Liste chemin="faiblesses" elements={r.faiblesses} /></div>
        </div>
        <div className="bloc"><h3 className="mb-2">{L("recurrents")}</h3><Liste chemin="recurrents" elements={r.recurrents} /></div>
        <div className="bloc"><h3 className="mb-2">{L("impact")}</h3><Texte chemin="impact" texte={r.impact} /></div>
      </section>

      {/* 2. Problèmes UX principaux */}
      <section id="r-s2" className="saut-page space-y-8">
        <h2>2. {L("s2")}</h2>
        <p className="text-texte-2">{L("s2_intro", { n: f.problemes.length, t: r.themes.length })}</p>
        {r.themes.length > 0 && (
          <div className="bloc carte p-4">
            <BarresHorizontales largeurLibelle="16rem" barres={r.themes.map((th, i) => ({
              cle: String(i), libelle: th.titre, valeur: th.problemes.length, couleur: couleurGravite(th.gravite_max),
              detail: L("meta_theme", { n: th.problemes.length, e: th.ecrans.length, g: gLib(th.gravite_max), t: th.recurrent ? L("recurrent") : L("isole") }),
            }))} />
            <p className="mt-3 text-xs text-texte-3">{L("nb_problemes")} · {L("gravite_max")}</p>
          </div>
        )}
        {r.themes.length > 0 && (
          <Tableau entetes={[L("theme"), L("nb_problemes"), L("nb_ecrans"), L("gravite_max"), L("tendance")]}
            classes={["", "text-right tabular-nums", "text-right tabular-nums", "", ""]}
            lignes={r.themes.map((th) => [th.titre, th.problemes.length, th.ecrans.length, <Gravite g={th.gravite_max} />, th.recurrent ? L("recurrent") : L("isole")])} />
        )}

        {r.themes.map((th, i) => {
          const exemples = th.problemes.map((k) => parCle[k]).filter(Boolean).sort((a, b) => (b.gravite ?? 0) - (a.gravite ?? 0)).slice(0, 4);
          return (
            <div key={i} className="space-y-4 border-t border-bord pt-6">
              <div>
                {edition ? <div className="flex items-center gap-2"><h3 className="shrink-0">2.{i + 1}</h3><Court chemin={`themes.${i}.titre`} texte={th.titre} /></div>
                  : <h3>2.{i + 1} {th.titre}</h3>}
                <p className="mt-1 text-sm text-texte-2 italic">{L("meta_theme", { n: th.problemes.length, e: th.ecrans.length, g: gLib(th.gravite_max), t: th.recurrent ? L("recurrent") : L("isole") })}</p>
                {th.criteres.length > 0 && <p className="mt-1 text-sm"><span className="font-semibold">{L("criteres")} : </span>{th.criteres.slice(0, 5).map((c) => c.libelle).join(", ")}</p>}
              </div>
              <Texte chemin={`themes.${i}.description`} titre={L("observes")} texte={th.description} />
              <Texte chemin={`themes.${i}.pourquoi`} titre={L("pourquoi")} texte={th.pourquoi} />
              <Texte chemin={`themes.${i}.consequences`} titre={L("consequences")} texte={th.consequences} />
              <div className="bloc">
                <h4 className="mb-2 text-sm font-semibold">{L("representatifs")}</h4>
                <Tableau entetes={[L("ref"), L("ecran"), L("constat"), L("gravite")]} classes={["font-mono text-xs whitespace-nowrap", "", "", "whitespace-nowrap"]}
                  lignes={exemples.map((p) => [p.ref, p.ecran, p.constat, <Gravite g={p.gravite} />])} />
              </div>
            </div>
          );
        })}

        <div className="space-y-4 border-t border-bord pt-6">
          <h3>2.{r.themes.length + 1} {L("tendances")}</h3>
          <p className="text-sm text-texte-2 italic">{L("tendances_rec")}</p>
          <Liste elements={recurrents.length ? recurrents.map((th) => `${th.titre} — ${L("n_problemes", { n: th.problemes.length })}, ${L("n_ecrans", { n: th.ecrans.length })} (${th.ecrans.slice(0, 6).join(", ")}${th.ecrans.length > 6 ? "…" : ""})`) : [L("aucun_rec")]} />
          <p className="text-sm text-texte-2 italic">{L("tendances_iso")}</p>
          <Liste elements={r.cas_isoles.length ? r.cas_isoles.map((i) => {
            const th = r.themes[i];
            return `${th.titre} — ` + th.problemes.slice(0, 3).map((k) => parCle[k]).filter(Boolean).map((p) => `${p.ref} (${p.ecran || "—"}, ${gLib(p.gravite)}) : ${p.constat}`).join(" ; ");
          }) : [L("aucun_iso")]} />
        </div>
      </section>

      {/* 3. Recommandations */}
      <section id="r-s3" className="saut-page space-y-8">
        <h2>3. {L("s3")}</h2>
        <p className="text-texte-2">{L("s3_intro")}</p>
        {r.recommandations.length > 0 && (
          <Tableau entetes={[L("rang"), L("chantier"), L("impact_court"), L("effort"), L("themes_traites")]} classes={["text-center tabular-nums", "font-medium", "", "", "text-texte-2"]}
            lignes={r.recommandations.map((c, i) => [i + 1, c.titre, impact(c.impact), effort(c.effort), c.themes.map((k) => r.themes[k]?.titre).join(", ")])} />
        )}
        {r.recommandations.map((c, i) => (
          <div key={i} className="space-y-3 border-t border-bord pt-6">
            {edition ? <div className="flex items-center gap-2"><h3 className="shrink-0">3.{i + 1}</h3><Court chemin={`recommandations.${i}.titre`} texte={c.titre} /></div>
              : <h3>3.{i + 1} {c.titre}</h3>}
            <div className="flex flex-wrap gap-2 text-xs">
              <span className={cx("rounded-full px-2.5 py-1 font-medium", c.impact === "fort" ? "bg-danger-doux text-danger" : c.impact === "moyen" ? "bg-alerte-doux text-alerte" : "bg-ok-doux text-ok")}>{L("impact_court")} : {impact(c.impact)}</span>
              <span className="rounded-full bg-surface-2 px-2.5 py-1 font-medium text-texte-2">{L("effort")} : {effort(c.effort)}</span>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <Texte chemin={`recommandations.${i}.objectif`} titre={L("objectif")} texte={c.objectif} />
              <Texte chemin={`recommandations.${i}.importance`} titre={L("importance")} texte={c.importance} />
              <Texte chemin={`recommandations.${i}.benefices`} titre={L("benefices")} texte={c.benefices} />
              <Texte chemin={`recommandations.${i}.problemes_resolus`} titre={L("resout")} texte={c.problemes_resolus} />
            </div>
            {c.themes.length > 0 && <p className="text-sm"><span className="font-semibold">{L("themes_traites")} : </span>{c.themes.map((k) => r.themes[k]?.titre).join(", ")} ({L("n_problemes", { n: c.nb_problemes })})</p>}
            {c.pistes.length > 0 && <div className="bloc"><h4 className="mb-1 text-sm font-semibold">{L("pistes")}</h4><Liste elements={c.pistes} /></div>}
          </div>
        ))}
      </section>

      {/* 4. Prochaines étapes */}
      <section id="r-s4" className="saut-page space-y-8">
        <h2>4. {L("s4")}</h2>
        <div className="space-y-3">
          <h3>4.1 {L("qw")}</h3>
          <p className="text-texte-2">{L("qw_intro")}</p>
          {r.quick_wins_candidats && <p className="text-sm text-texte-3 italic">{L("qw_candidats")}</p>}
          {r.quick_wins.length ? (
            <Tableau entetes={[L("action"), L("valeur"), L("constats_lies")]} classes={["", "", "font-mono text-xs"]}
              lignes={r.quick_wins.map((q, i) => [
                edition ? <div className="space-y-1.5"><Court chemin={`quick_wins.${i}.titre`} texte={q.titre} /><Court chemin={`quick_wins.${i}.description`} texte={q.description} /></div>
                  : <><div className="font-medium">{q.titre}</div>{q.description && <div className="mt-0.5 text-texte-2">{q.description}</div>}</>,
                <Court chemin={`quick_wins.${i}.valeur`} texte={q.valeur} vide />,
                q.problemes.map((k) => parCle[k]).filter(Boolean).map((p) => p.ecran ? `${p.ref} (${p.ecran})` : p.ref).join(", "),
              ])} />
          ) : <Texte texte="" />}
        </div>
        <div className="space-y-3">
          <h3>4.2 {L("mlt")}</h3>
          {r.suites.length ? (
            <Tableau entetes={[L("horizon"), L("chantier"), L("objectif")]} classes={["whitespace-nowrap", "font-medium", ""]}
              lignes={r.suites.map((s, i) => [L(`horizon.${s.horizon}`), <Court chemin={`suites.${i}.titre`} texte={s.titre} />, <Court chemin={`suites.${i}.description`} texte={s.description} />])} />
          ) : <Texte texte="" />}
        </div>
        <div className="space-y-3">
          <h3>4.3 {L("demarche")}</h3>
          {edition ? <Liste chemin="demarche" elements={r.demarche} /> : <ol className="space-y-2">
            {r.demarche.map((e, i) => (
              <li key={i} className="flex gap-3">
                <span className="grid size-6 shrink-0 place-items-center rounded-full bg-marque-doux text-xs font-semibold text-marque">{i + 1}</span>
                <span>{e}</span>
              </li>
            ))}
          </ol>}
        </div>
      </section>

      {/* Annexes */}
      <section id="r-annexes" className="saut-page space-y-8">
        <h2>{L("annexes")}</h2>
        <div className="space-y-4">
          <h3>A. {L("methode")}</h3>
          <p>{L("methode_texte", { v: f.version_referentiel })}</p>
          <h4 className="text-sm font-semibold">{L("echelle_gravite")}</h4>
          <Tableau entetes={[L("gravite"), ""]} classes={["whitespace-nowrap", "text-texte-2"]} lignes={r.gravites.map((g) => [<Gravite g={g.niveau} />, g.definition])} />
          <h4 className="text-sm font-semibold">{L("echelle_maturite")}</h4>
          <Tableau entetes={[L("maturite"), ""]} classes={["whitespace-nowrap font-medium", "text-texte-2"]} lignes={r.maturites.map((m) => [`${m.niveau}. ${m.libelle}`, m.definition])} />
          <p className="text-xs text-texte-3 italic">{L("regle_maturite")}</p>
        </div>
        <div className="space-y-3">
          <h3>B. {L("liste")}</h3>
          <Tableau entetes={[L("ref"), L("ecran"), L("critere"), L("constat"), L("gravite")]} classes={["font-mono text-xs whitespace-nowrap", "", "font-mono text-xs whitespace-nowrap", "", "whitespace-nowrap"]}
            lignes={tries.map((p) => [p.ref, p.ecran, <span title={p.critere_libelle}>{p.critere ?? "—"}</span>, p.constat, <Gravite g={p.gravite} />])} />
        </div>
        {f.points_forts.length > 0 && (
          <div className="space-y-3">
            <h3>C. {L("points_forts_releves")}</h3>
            <Tableau entetes={[L("ref"), L("ecran"), L("constat")]} classes={["font-mono text-xs whitespace-nowrap", "", ""]}
              lignes={f.points_forts.map((p) => [p.ref, p.ecran, p.constat])} />
          </div>
        )}
      </section>
    </article>
    </Edition.Provider>
  );
}
