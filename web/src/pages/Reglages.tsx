import { useState } from "react";
import { api } from "../api";
import { useLangue, useT } from "../i18n";
import type { Config } from "../types";
import { Alerte, Bouton, Icone, Lien, Section, Spinner } from "../components/ui";

export default function PageReglages({ config, recharger }: { config: Config; recharger: () => void }) {
  const t = useT();
  const lg = useLangue();
  const [test, setTest] = useState<{ statut: string; message: string; detail?: string } | null>(null);
  const [enCours, setEnCours] = useState(false);
  const ia = config.ia;
  const ref = config.referentiel;

  const tester = async () => {
    setEnCours(true);
    try { setTest(await api.testerConnexion(lg)); } catch (e) { setTest({ statut: "erreur", message: (e as Error).message }); }
    setEnCours(false);
  };

  const lignes: [string, string][] = [
    [t("ia.modele"), ia.modele],
    [t("ia.adresse"), ia.adresse],
    [t("ia.cle"), ia.cle ? t("ia.cle_oui") : t("ia.cle_non")],
    [t("ia.ca"), ia.ca_bundle || t("ia.ca_non")],
  ];

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">{t("nav.reglages")}</h1>
        <p className="mt-1 text-sm text-texte-2">{t("referentiel", { v: ref.version, n: ref.criteres.length, r: ref.nb_regles })}</p>
      </header>

      <Section titre={t("ia.titre")} intro={t("ia.reglage")}>
        {!ia.active ? <Alerte ton="info">{t("ia.desactivee")}</Alerte> : (
          <div className="space-y-4">
            <dl className="grid gap-x-6 gap-y-2 text-sm sm:grid-cols-[10rem_1fr]">
              {lignes.map(([k, v]) => (
                <div key={k} className="contents">
                  <dt className="text-texte-2">{k}</dt>
                  <dd className="font-mono text-[13px] break-all">{v}</dd>
                </div>
              ))}
            </dl>
            <Alerte ton={ia.locale ? "ok" : "alerte"}>
              <span className="inline-flex items-center gap-1.5">
                <Icone nom={ia.locale ? "cadenas" : "globe"} className="size-4" />
                {ia.locale ? t("ia.local") : t("ia.distant", { h: ia.hote })}
              </span>
            </Alerte>
            <div className="flex flex-wrap items-center gap-3">
              <Bouton onClick={tester} disabled={enCours}>{enCours ? <><Spinner /> {t("ia.test_en_cours")}</> : t("ia.tester")}</Bouton>
            </div>
            {test && (
              <Alerte ton={test.statut === "ok" ? "ok" : test.statut === "absent" ? "alerte" : "danger"}>
                {test.message}
                {test.detail && <code className="mt-1 block text-xs break-all">{test.detail}</code>}
              </Alerte>
            )}
          </div>
        )}
      </Section>

      <Section titre={t("cache.titre")}>
        <div className="flex flex-wrap items-center justify-between gap-3 text-sm text-texte-2">
          <span>{config.cache === null ? t("cache.desactive") : t("cache.n", { n: config.cache })}</span>
          {!!config.cache && <Bouton onClick={async () => { await api.viderCache(); recharger(); }}>{t("cache.vider")}</Bouton>}
        </div>
      </Section>

      <Section titre={t("template")}>
        <Lien href={api.templateUrl(lg)} icone="telecharger">{t("template")}</Lien>
      </Section>
    </div>
  );
}
