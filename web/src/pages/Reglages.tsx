import { api } from "../api";
import { useLangue, useT } from "../i18n";
import type { Config } from "../types";
import ParametresConnexion from "../components/ParametresConnexion";
import { Bouton, Lien, Section } from "../components/ui";

export default function PageReglages({ config, recharger }: { config: Config; recharger: () => void }) {
  const t = useT();
  const lg = useLangue();
  const ref = config.referentiel;

  return (
    <div className="space-y-6">
      <header>
        <h1 className="nn-page-title">{t("nav.reglages")}</h1>
        <p className="mt-1 text-sm text-texte-2">{t("referentiel", { v: ref.version, n: ref.criteres.length, r: ref.nb_regles })}</p>
      </header>

      <ParametresConnexion enregistre={recharger} />

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
