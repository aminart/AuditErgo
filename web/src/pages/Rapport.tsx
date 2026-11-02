import { useState } from "react";
import { api, attendre } from "../api";
import { useLangue, useT } from "../i18n";
import type { Config, EtatAudit, Rapport } from "../types";
import { Alerte, Bouton, Icone, Lien, Progression } from "../components/ui";
import RapportVue from "../components/RapportVue";

/** Page HTML autonome : le rapport et les styles de l'application, pour l'archiver ou l'envoyer. */
function exporterHtml(titre: string, nom: string) {
  const noeud = document.getElementById("rapport");
  if (!noeud) return;
  let css = "";
  for (const feuille of Array.from(document.styleSheets)) {
    try { css += Array.from(feuille.cssRules).map((r) => r.cssText).join("\n"); } catch { /* feuille inaccessible */ }
  }
  const page = `<!doctype html><html lang="${document.documentElement.lang}" data-theme="light"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>${titre.replace(/</g, "&lt;")}</title>
<style>${css}\n.no-print{display:none!important}body{padding:24px 12px}</style></head><body>${noeud.outerHTML}</body></html>`;
  const lien = document.createElement("a");
  lien.href = URL.createObjectURL(new Blob([page], { type: "text/html;charset=utf-8" }));
  lien.download = nom;
  lien.click();
  setTimeout(() => URL.revokeObjectURL(lien.href), 1000);
}

export default function PageRapport({ config, etat, rapport, setRapport, setEtat, allerRelecture }: {
  config: Config; etat: EtatAudit | null; rapport: Rapport | null; setRapport: (r: Rapport | null) => void;
  setEtat: (e: EtatAudit) => void; allerRelecture: () => void;
}) {
  const t = useT();
  const lg = useLangue();
  const [progression, setProgression] = useState<{ fait: number; total: number } | null>(null);
  const [erreur, setErreur] = useState("");

  if (!etat) {
    return (
      <div className="space-y-6">
        <header>
          <h1 className="text-2xl font-semibold tracking-tight">{t("r.titre")}</h1>
          <p className="mt-1 max-w-3xl text-sm text-texte-2">{t("r.intro")}</p>
        </header>
        <div className="carte grid min-h-64 place-items-center border-dashed p-8 text-center">
          <div>
            <Icone nom="rapport" className="mx-auto mb-3 size-8 text-texte-3" />
            <p className="text-sm text-texte-2">{t("r.sans_audit")}</p>
            <Bouton variante="primaire" className="mt-4" onClick={allerRelecture}>{t("r.aller_relecture")}</Bouton>
          </div>
        </div>
      </div>
    );
  }

  const generer = async (avecIA: boolean, forcer = false) => {
    setErreur(""); setProgression({ fait: 0, total: avecIA ? 2 : 0 });
    try {
      const tache = await api.genererRapport(etat.id, avecIA, forcer, lg);
      setRapport(await attendre(tache, (fait, total) => setProgression({ fait, total })));
      setEtat({ ...etat, rapport: true });
    } catch (e) { setErreur((e as Error).message); }
    setProgression(null);
  };

  const actuel = rapport && etat.rapport ? rapport : null;
  const perime = rapport && !etat.rapport;
  const stem = etat.nom.replace(/\.xlsx$/i, "");
  const iaDispo = config.ia.active;

  return (
    <div className="space-y-6">
      <div className="no-print space-y-4">
        <header className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">{t("r.titre")}</h1>
            <p className="mt-1 max-w-3xl text-sm text-texte-2">{t("r.intro")}</p>
          </div>
          {actuel && (
            <div className="flex flex-wrap gap-2">
              <Bouton icone="imprimer" onClick={() => window.print()}>{t("r.imprimer")}</Bouton>
              <Bouton icone="html" onClick={() => exporterHtml(`${actuel.libelles.titre} – ${stem}`, `${stem}_rapport.html`)}>{t("r.html")}</Bouton>
              <Lien variante="primaire" icone="word" href={api.rapportWordUrl(etat.id)} download={`${stem}_rapport.docx`}>{t("r.word")}</Lien>
            </div>
          )}
        </header>

        {erreur && <Alerte ton="danger">{erreur}</Alerte>}
        {!etat.ia && !actuel && <Alerte ton="info">{t("r.conseil")}</Alerte>}
        {etat.a_valider > 0 && <Alerte ton="ia">{t("r.a_valider", { n: etat.a_valider })}</Alerte>}
        {perime && <Alerte ton="alerte">{t("r.perime")}</Alerte>}

        {progression ? (
          <div className="carte p-5">
            <Progression fait={progression.fait} total={progression.total} libelle={t("r.progression", { f: progression.fait, n: progression.total || 2 })} />
          </div>
        ) : (
          <div className="flex flex-wrap items-center gap-3">
            <Bouton variante={actuel ? "secondaire" : "primaire"} icone={actuel ? "rafraichir" : "ia"} disabled={!iaDispo} onClick={() => generer(true, !!actuel)}>
              {actuel ? t("r.regenerer") : t("r.generer")}
            </Bouton>
            <Bouton variante="discret" onClick={() => generer(false)}>{t("r.generer_sans_ia")}</Bouton>
          </div>
        )}

        {actuel && (
          actuel.erreur ? <Alerte ton="alerte">{t("r.erreur", { e: actuel.erreur })}</Alerte>
            : actuel.ia ? <Alerte ton="ok">{t("r.ok")}</Alerte> : <Alerte ton="info">{t("r.sans_ia")}</Alerte>
        )}
      </div>

      {actuel && <RapportVue r={actuel} />}
    </div>
  );
}
