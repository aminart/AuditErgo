import { useEffect, useRef, useState, type ReactNode } from "react";
import { api } from "../api";
import { useLangue, useT } from "../i18n";
import type { ChampParametre, FormulaireParametres, ParametresConnexion as Parametres, TestConnexion } from "../types";
import { Alerte, Icone, Spinner, cx } from "./ui";

/** Connexion au modèle : même fenêtre que l'écran Paramètres de SpecGen (champs, test, enregistrement). */

const ALERTE_EXPIRATION_JOURS = 30;

function Champ({ libelle, pour, aide, facultatif, children }: { libelle: string; pour?: string; aide?: ReactNode; facultatif?: string; children: ReactNode }) {
  const titre = (
    <>
      {libelle}
      {facultatif && <span className="font-normal text-ink-subtle"> ({facultatif})</span>}
    </>
  );
  return (
    <div className="flex flex-col gap-2">
      {pour ? <label htmlFor={pour} className="text-[15px] font-medium">{titre}</label> : <span className="text-[15px] font-medium">{titre}</span>}
      {children}
      {aide && <p className="text-[13px] text-ink-subtle">{aide}</p>}
    </div>
  );
}

function Saisie({ id, valeur, changer, type = "text", indication, desactive, invalide }:
  { id: string; valeur: string; changer: (v: string) => void; type?: string; indication?: string; desactive?: boolean; invalide?: boolean }) {
  return (
    <input
      id={id}
      type={type}
      value={valeur}
      placeholder={indication}
      disabled={desactive}
      aria-invalid={invalide || undefined}
      onChange={(e) => changer(e.target.value)}
      className={cx(
        "min-h-[44px] w-full min-w-0 rounded-lg border bg-surface px-3.5 text-[15px] text-ink placeholder:text-ink-subtle focus:outline-none focus:ring-[3px] focus:ring-accent-soft disabled:bg-surface-3 disabled:text-ink-muted",
        invalide ? "border-[1.5px] border-danger focus:border-danger" : "border-line-strong focus:border-accent",
      )}
    />
  );
}

/** Adresse qui désigne ce poste (localhost, 127.x, ::1) : rien ne sort du poste. */
function estLocale(adresse: string) {
  try {
    const hote = new URL(adresse).hostname.toLowerCase().replace(/^\[|\]$/g, "");
    return hote === "localhost" || hote.endsWith(".localhost") || hote.startsWith("127.") || hote === "::1";
  } catch {
    return null;
  }
}

export default function ParametresConnexion({ enregistre }: { enregistre: () => void }) {
  const t = useT();
  const lg = useLangue();
  const locale = lg === "en" ? "en-GB" : "fr-FR";
  const [enreg, setEnreg] = useState<Parametres | null>(null);
  const [adresse, setAdresse] = useState("");
  const [cle, setCle] = useState<string | null>(null); // null : garder la clé enregistrée
  const [voirCle, setVoirCle] = useState(false);
  const [modele, setModele] = useState("mistral-small");
  const [delai, setDelai] = useState("600");
  const [test, setTest] = useState<TestConnexion | null>(null);
  const [occupe, setOccupe] = useState<"test" | "enregistrer" | "certificat" | "effacer" | null>(null);
  const [message, setMessage] = useState<{ ton: "ok" | "danger" | "info"; texte: string } | null>(null);
  const fichierCertificat = useRef<HTMLInputElement>(null);

  const appliquer = (p: Parametres) => {
    setEnreg(p);
    setAdresse(p.api_base);
    setCle(p.has_api_key ? null : "");
    setModele(p.model);
    setDelai(String(p.timeout));
    setTest(p.last_test);
  };

  useEffect(() => {
    api.parametres().then(appliquer).catch((e: Error) => setMessage({ ton: "danger", texte: e.message }));
  }, []);

  if (!enreg) {
    return message ? <Alerte ton="danger">{message.texte}</Alerte> : <p className="flex items-center gap-2 text-sm text-ink-muted"><Spinner /> {t("param.chargement")}</p>;
  }

  const depuisEnv = (champ: ChampParametre) => enreg.env_fields.includes(champ);
  const formulaire: FormulaireParametres = { api_base: adresse, api_key: cle, model: modele, timeout: Number(delai) || 600 };
  const complet = Boolean(adresse.trim()) && Boolean(modele.trim());
  const modifie = adresse !== enreg.api_base || (cle !== null && (cle !== "" || enreg.has_api_key)) || modele !== enreg.model || Number(delai) !== enreg.timeout;
  const champEnEchec = test && !test.ok ? test.field : null;
  const aideEnv = t("param.env_champ");
  const date = (iso: string) => new Date(iso).toLocaleDateString(locale);
  const dateHeure = (iso: string) => new Date(iso).toLocaleString(locale, { dateStyle: "short", timeStyle: "short" });

  const expiration = (() => {
    const fin = enreg.certificate?.expires_at;
    if (!fin) return null;
    const jours = (new Date(fin).getTime() - Date.now()) / 86_400_000;
    if (jours < 0) return { texte: t("param.expire_depuis", { d: date(fin) }), ton: "erreur" as const };
    if (jours < ALERTE_EXPIRATION_JOURS) return { texte: t("param.expire_bientot", { d: date(fin) }), ton: "alerte" as const };
    return { texte: t("param.expire_le", { d: date(fin) }), ton: "discret" as const };
  })();
  const certificatEnErreur = champEnEchec === "certificate" || expiration?.ton === "erreur";
  const local = estLocale(adresse);

  const lancer = async (genre: NonNullable<typeof occupe>, action: () => Promise<void>) => {
    setOccupe(genre);
    setMessage(null);
    try {
      await action();
    } catch (e) {
      setMessage({ ton: "danger", texte: (e as Error).message });
    } finally {
      setOccupe(null);
    }
  };

  const importerCertificat = (fichier: File) =>
    lancer("certificat", async () => {
      setEnreg(await api.importerCertificat(fichier, lg));
      setTest(null);
    });

  const tester = () => lancer("test", async () => setTest(await api.testerParametres(formulaire, lg)));

  const enregistrer = () =>
    lancer("enregistrer", async () => {
      const p = await api.enregistrerParametres(formulaire);
      appliquer({ ...p, last_test: test ?? p.last_test });
      setMessage({ ton: "ok", texte: t("param.enregistres") });
      enregistre();
    });

  const effacer = () => {
    if (!window.confirm(t("param.effacer_confirmer"))) return;
    lancer("effacer", async () => {
      appliquer(await api.effacerParametres());
      setMessage({ ton: "info", texte: t("param.effaces") });
      enregistre();
    });
  };

  return (
    <div className="flex flex-col gap-4">
      {!enreg.active && <Alerte ton="info">{t("ia.desactivee")}</Alerte>}
      {enreg.active && !enreg.saved && <Alerte ton="info">{t("param.defaut", { a: enreg.default_api_base })}</Alerte>}
      {enreg.env_fields.length > 0 && (
        <Alerte ton="neutre">{t("param.env", { f: enreg.env_file ? ` (${enreg.env_file})` : "" })}</Alerte>
      )}

      <section className="rounded-xl border border-line bg-surface">
        <div className="px-6 pb-2 pt-7 sm:px-8">
          <h2 className="text-2xl font-bold leading-tight text-accent">{t("param.titre")}</h2>
          <p className="mt-2 text-sm leading-normal text-ink-muted">{t("param.intro")}</p>
        </div>

        <div className="flex flex-col gap-6 px-6 pb-7 pt-5 sm:px-8">
          {test?.ok && (
            <div role="status" className="flex items-center gap-3 rounded-lg border border-success-soft bg-success-soft px-4 py-3.5">
              <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-success text-surface">
                <Icone nom="check" className="size-[14px] [stroke-width:3]" />
              </span>
              <div>
                <p className="text-[15px] font-medium text-success-text">{test.title}</p>
                <p className="mt-0.5 text-[13px] text-success-text">{t("param.teste_le", { d: dateHeure(test.at), m: test.message })}</p>
              </div>
            </div>
          )}

          <Champ libelle={t("param.url")} pour="api-base" aide={depuisEnv("api_base") ? aideEnv : t("param.url_aide")}>
            <Saisie id="api-base" type="url" valeur={adresse} changer={setAdresse} indication={enreg.default_api_base}
              desactive={depuisEnv("api_base")} invalide={champEnEchec === "api_base"} />
            {local !== null && (
              <p className={cx("flex items-center gap-1.5 text-[13px]", local ? "text-success-text" : "text-warning-text")}>
                <Icone nom={local ? "cadenas" : "globe"} className="size-3.5" />
                {local ? t("ia.local") : t("ia.distant", { h: new URL(adresse).hostname })}
              </p>
            )}
          </Champ>

          {cle === null ? (
            <Champ libelle={t("param.cle")} aide={depuisEnv("api_key") ? aideEnv : t("param.cle_chiffree")}>
              <div className={cx("flex min-h-[48px] items-center gap-3 rounded-lg border bg-surface-2 pl-3.5 pr-2",
                champEnEchec === "api_key" ? "border-[1.5px] border-danger" : "border-line-strong")}>
                <Icone nom="cadenas" className="size-[18px] text-ink-muted" />
                <span className="flex-1 text-[15px] tracking-[0.08em] text-ink-body">•••• •••• •••• {enreg.api_key_hint}</span>
                {!depuisEnv("api_key") && (
                  <button type="button" onClick={() => setCle("")}
                    className="min-h-[36px] rounded-md border border-line-strong bg-surface px-3 text-[13px] font-medium text-ink hover:bg-surface-3">
                    {t("param.modifier")}
                  </button>
                )}
              </div>
            </Champ>
          ) : (
            <Champ libelle={t("param.cle")} pour="api-key" facultatif={t("param.facultatif")} aide={t("param.cle_aide")}>
              <div className="flex gap-2">
                <Saisie id="api-key" type={voirCle ? "text" : "password"} valeur={cle} changer={setCle}
                  indication={t("param.cle_saisie")} invalide={champEnEchec === "api_key"} />
                <button type="button" onClick={() => setVoirCle((v) => !v)} aria-label={voirCle ? t("param.masquer_cle") : t("param.afficher_cle")}
                  className="flex min-h-[44px] w-11 shrink-0 items-center justify-center rounded-lg border border-line-strong bg-surface text-ink-muted hover:bg-surface-3">
                  <Icone nom={voirCle ? "oeil_barre" : "oeil"} className="size-[18px]" />
                </button>
              </div>
              {enreg.has_api_key && (
                <button type="button" className="self-start text-[13px] font-medium text-accent underline" onClick={() => setCle(null)}>
                  {t("param.garder_cle")}
                </button>
              )}
            </Champ>
          )}

          <Champ libelle={t("param.certificat")} facultatif={enreg.certificate ? undefined : t("param.facultatif")}
            aide={depuisEnv("ca_bundle") ? aideEnv : enreg.certificate ? undefined : t("param.certificat_aide")}>
            {enreg.certificate ? (
              <div className={cx("flex items-center gap-3 rounded-lg bg-surface px-3.5 py-3",
                champEnEchec === "certificate" ? "border-[1.5px] border-danger" : "border border-line-strong")}>
                <Icone nom={certificatEnErreur ? "bouclier_alerte" : "bouclier"} className={cx("size-[22px]", certificatEnErreur ? "text-danger-text" : "text-accent")} />
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm font-medium">{enreg.certificate.name}</div>
                  <div className={cx("text-xs", certificatEnErreur ? "text-danger-text" : expiration?.ton === "alerte" ? "text-warning-text" : "text-ink-muted")}>
                    {champEnEchec === "certificate"
                      ? t("param.certificat_refuse")
                      : [enreg.certificate.imported_at && t("param.importe_le", { d: date(enreg.certificate.imported_at) }), expiration?.texte].filter(Boolean).join(" · ")}
                  </div>
                </div>
                {!depuisEnv("ca_bundle") && (
                  <button type="button" disabled={occupe === "certificat"} onClick={() => fichierCertificat.current?.click()}
                    className="min-h-[36px] rounded-md border border-line-strong bg-surface px-3 text-[13px] font-medium text-ink hover:bg-surface-3">
                    {occupe === "certificat" ? t("param.certificat_import") : t("param.remplacer")}
                  </button>
                )}
              </div>
            ) : (
              <button type="button" disabled={occupe === "certificat"} onClick={() => fichierCertificat.current?.click()}
                className={cx("flex min-h-[52px] items-center justify-center gap-2 rounded-lg border-[1.5px] border-dashed text-sm font-medium text-accent hover:border-accent hover:bg-accent-softer",
                  champEnEchec === "certificate" ? "border-danger" : "border-line-dashed")}>
                <Icone nom="plus" className="size-[18px]" />
                {occupe === "certificat" ? t("param.certificat_import") : t("param.certificat_choisir")}
              </button>
            )}
            <input ref={fichierCertificat} type="file" accept=".crt,.pem,.cer" className="hidden"
              onChange={(e) => {
                const fichier = e.target.files?.[0];
                if (fichier) importerCertificat(fichier);
                e.target.value = "";
              }} />
          </Champ>

          <details className="border-t border-line pt-4" open={champEnEchec === "model" || undefined}>
            <summary className="cursor-pointer text-sm font-medium text-ink-muted hover:text-ink">
              {t("param.avance", { m: modele || "mistral-small", d: delai })}
            </summary>
            <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Champ libelle={t("param.modele")} pour="model" aide={depuisEnv("model") ? aideEnv : t("param.modele_aide")}>
                <Saisie id="model" valeur={modele} changer={setModele} desactive={depuisEnv("model")} invalide={champEnEchec === "model"} />
              </Champ>
              <Champ libelle={t("param.delai")} pour="timeout" aide={depuisEnv("timeout") ? aideEnv : undefined}>
                <Saisie id="timeout" type="number" valeur={delai} changer={setDelai} desactive={depuisEnv("timeout")} />
              </Champ>
            </div>
          </details>

          {test && !test.ok && (
            <div role="alert" className="flex gap-3 rounded-lg border border-danger-soft bg-danger-soft p-4">
              <Icone nom="alerte" className="mt-0.5 size-5 text-danger-text" />
              <div>
                <p className="text-[15px] font-medium text-danger-text">{test.title}</p>
                <p className="mt-1 text-sm leading-normal text-ink-body">{test.message}</p>
              </div>
            </div>
          )}

          {message && <Alerte ton={message.ton}>{message.texte}</Alerte>}
        </div>

        <div className="flex flex-wrap items-center gap-3 rounded-b-xl border-t border-line bg-surface-2 px-6 py-5 sm:px-8">
          {enreg.saved && !modifie ? (
            <>
              <button type="button" onClick={effacer} disabled={occupe !== null} className="min-h-[44px] px-1 text-sm font-medium text-danger-text underline">
                {t("param.effacer")}
              </button>
              <span className="flex-[1_1_40px]" />
            </>
          ) : (
            <p className="flex-[1_1_200px] text-[13px] text-ink-subtle">
              {!complet ? t("param.incomplet") : test && !test.ok ? t("param.malgre_echec") : t("param.tester_avant")}
            </p>
          )}
          <button type="button" className="btn-secondaire min-h-[44px]" disabled={!complet || occupe !== null} onClick={tester}>
            {occupe === "test" ? <><Spinner /> {t("param.test_en_cours")}</> : test && !test.ok ? t("param.tester_encore") : t("param.tester")}
          </button>
          {enreg.saved && !modifie ? (
            <button type="button" className="btn-primaire min-h-[44px]" disabled>
              <Icone nom="check" className="size-4" /> {t("param.enregistre")}
            </button>
          ) : (
            <button type="button" className="btn-primaire min-h-[44px] px-5" disabled={!complet || occupe !== null} onClick={enregistrer}>
              {occupe === "enregistrer" ? t("param.enregistrement") : t("param.enregistrer")}
            </button>
          )}
        </div>
      </section>

      <div className="flex gap-3 rounded-[10px] border border-line bg-surface px-5 py-4">
        <Icone nom="info" className="mt-0.5 size-[18px] text-ink-muted" />
        <p className="text-[13px] leading-relaxed text-ink-muted">{t("param.stockage", { d: enreg.storage_dir })}</p>
      </div>
    </div>
  );
}
