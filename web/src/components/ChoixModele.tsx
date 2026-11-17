import { useEffect, useState } from "react";
import { api } from "../api";
import { usePickedModel } from "../choixModele";
import { useT } from "../i18n";
import type { ChoixModeles } from "../types";

/** Modèles groupés par connexion de Studio Dock, pour un <select>. */
export function GroupesDeModeles({ choix }: { choix: ChoixModeles }) {
  const groupes = choix.options.reduce<Record<string, ChoixModeles["options"]>>((acc, o) => {
    (acc[o.connection] ??= []).push(o);
    return acc;
  }, {});
  return (
    <>
      {Object.entries(groupes).map(([connexion, modeles]) => (
        <optgroup key={connexion} label={connexion}>
          {modeles.map((o) => <option key={o.id} value={o.id}>{o.model}</option>)}
        </optgroup>
      ))}
    </>
  );
}

/** Modèle utilisé pour cette analyse, parmi ceux réglés dans Studio Dock. Masqué si Studio Dock n'offre pas de choix. */
export default function ChoixModele({ compact }: { compact?: boolean }) {
  const t = useT();
  const [choix, setChoix] = useState<ChoixModeles | null>(null);
  const [choisi, choisir] = usePickedModel();

  useEffect(() => {
    api.modeles().then(setChoix).catch(() => setChoix(null));
  }, []);

  if (!choix?.available || choix.options.length < 2) return null;
  const valeur = choisi && choix.options.some((o) => o.id === choisi) ? choisi : "";
  const defaut = choix.options.find((o) => o.id === choix.default);
  return (
    <div className={compact ? "flex flex-wrap items-center gap-2" : "space-y-1.5"}>
      <label htmlFor="choix-modele" className="text-sm font-medium">{t("modele.libelle")}</label>
      <select id="choix-modele" className={compact ? "champ w-auto min-w-[16rem]" : "champ"} value={valeur} title={t("modele.aide")}
        onChange={(e) => choisir(e.target.value || null)}>
        <option value="">{t("modele.defaut", { m: defaut ? `${defaut.model} · ${defaut.connection}` : "" })}</option>
        <GroupesDeModeles choix={choix} />
      </select>
      {!compact && <p className="text-xs text-texte-3">{t("modele.aide")}</p>}
    </div>
  );
}
