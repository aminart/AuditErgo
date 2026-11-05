import { useT } from "../i18n";
import type { Suggestion } from "../types";
import { Alerte, Badge, Copier } from "./ui";
import { PastilleGravite } from "./graphiques";

const TON_CONFIANCE = { haute: "ok", moyenne: "alerte", faible: "danger" } as const;
const TON_VERDICT = { confirme: "ok", a_revoir: "alerte", incorrect: "danger", non_fourni: "neutre" } as const;
const TON_RECO = { bonne: "ok", a_ameliorer: "alerte", hors_sujet: "danger", non_fournie: "neutre" } as const;

function Bloc({ titre, children }: { titre: string; children: React.ReactNode }) {
  return (
    <div>
      <h4 className="mb-1.5 text-xs font-semibold tracking-wide text-texte-3 uppercase">{titre}</h4>
      {children}
    </div>
  );
}

function ACopier({ libelle, texte }: { libelle: string; texte: string }) {
  const t = useT();
  return (
    <div className="rounded-md border border-bord bg-surface-2">
      <div className="flex items-center justify-between border-b border-bord px-3 py-1">
        <span className="text-xs font-medium text-texte-2">{libelle}</span>
        <Copier texte={texte} libelle={t("copier")} copie={t("copie")} />
      </div>
      <p className="px-3 py-2 text-sm whitespace-pre-wrap">{texte}</p>
    </div>
  );
}

export default function SuggestionDetail({ s }: { s: Suggestion }) {
  const t = useT();
  return (
    <div className="space-y-5">
      <div>
        <div className="flex flex-wrap items-center gap-1.5">
          <Badge ton={TON_CONFIANCE[s.confiance as keyof typeof TON_CONFIANCE] ?? "neutre"}>{t("s.confiance", { n: s.confiance_libelle })}</Badge>
          {s.regle !== "aucune" && <Badge ton="info">{t("s.regle", { r: s.regle })}</Badge>}
          {s.depuis_cache && <Badge>{t("s.cache")}</Badge>}
        </div>
        <h3 className="mt-2 text-xl font-semibold tracking-tight">{s.critere.code} – {s.critere.nom_fr}</h3>
        <p className="text-sm text-texte-3">{s.critere.nom} · {s.categorie_libelle}</p>
        <p className="mt-3 text-sm leading-relaxed">{s.justification}</p>
        {s.question_checklist && (
          <p className="mt-2 border-l-2 border-accent pl-3 text-sm text-texte-2 italic">
            <span className="font-medium not-italic">{t("s.checklist")} : </span>{s.question_checklist}
          </p>
        )}
      </div>

      {s.critere_designer && (
        <Alerte ton={TON_VERDICT[s.verdict as keyof typeof TON_VERDICT] ?? "neutre"} titre={t("s.votre_choix", { c: s.critere_designer, v: s.verdict_libelle })}>
          {s.commentaire_verdict}
        </Alerte>
      )}

      {(s.question_a_se_poser || s.precisions_manquantes.length > 0) && (
        <Alerte ton="info">
          {s.question_a_se_poser && <p><strong>{t("s.a_se_demander")} :</strong> {s.question_a_se_poser}</p>}
          {s.precisions_manquantes.length > 0 && (
            <div className={s.question_a_se_poser ? "mt-2" : ""}>
              <strong>{t("s.preciser")} :</strong>
              <ul className="mt-1 list-disc pl-5">{s.precisions_manquantes.map((p) => <li key={p}>{p}</li>)}</ul>
            </div>
          )}
        </Alerte>
      )}

      <div className="grid gap-5 sm:grid-cols-2">
        <Bloc titre={t("s.secondaires")}>
          {s.secondaires.length ? (
            <ul className="space-y-1.5 text-sm">{s.secondaires.map((v) => <li key={v.code}><span className="font-medium">{v.libelle}</span> <span className="text-texte-2">— {v.justification}</span></li>)}</ul>
          ) : <p className="text-sm text-texte-3">{t("aucun")}</p>}
        </Bloc>
        <Bloc titre={t("s.ecartes")}>
          {s.alternatives.length ? (
            <ul className="space-y-1.5 text-sm">{s.alternatives.map((v) => <li key={v.code}><span className="font-medium">{v.libelle}</span> <span className="text-texte-2">— {v.pourquoi_pas}</span></li>)}</ul>
          ) : <p className="text-sm text-texte-3">{t("aucun")}</p>}
        </Bloc>
      </div>

      <Bloc titre={t("s.reco_titre")}>
        <div className="space-y-3">
          {s.reco_statut !== "non_fournie" && (
            <Alerte ton={TON_RECO[s.reco_statut as keyof typeof TON_RECO] ?? "neutre"} titre={t("s.votre_reco", { v: s.reco_statut_libelle })}>
              {s.reco_commentaire}
            </Alerte>
          )}
          {s.reco_amelioree && <ACopier libelle={t("s.reco_amelioree")} texte={s.reco_amelioree} />}
          {s.reco_proposee && s.reco_statut !== "bonne" && <ACopier libelle={s.reco_amelioree ? t("s.reco_autre") : t("s.reco_ia")} texte={s.reco_proposee} />}
          {s.type_reco_libelle && <p className="text-xs text-texte-2">{t("s.type_reco", { t: s.type_reco_libelle })}</p>}
          {s.reco_complementaires.length > 0 && (
            <div className="text-sm"><span className="font-medium">{t("s.pistes")}</span>
              <ul className="mt-1 list-disc pl-5 text-texte-2">{s.reco_complementaires.map((v) => <li key={v}>{v}</li>)}</ul>
            </div>
          )}
        </div>
      </Bloc>

      {s.gravite !== null && (
        <Bloc titre={t("s.gravite_titre")}>
          <PastilleGravite niveau={s.gravite} libelle={s.gravite_libelle} />
          <p className="mt-1.5 text-sm text-texte-2">{s.justification_gravite}</p>
        </Bloc>
      )}

      <Bloc titre={t("s.a_coller")}>
        <div className="space-y-2">
          <ACopier libelle={t("s.col_critere")} texte={s.ligne_excel} />
          {(!s.critere_designer || s.verdict === "confirme") && <ACopier libelle={t("s.col_justification")} texte={s.justification_critere} />}
        </div>
      </Bloc>

      <details className="rounded-md border border-bord px-3 py-2 text-sm">
        <summary className="cursor-pointer font-medium">{t("s.definition", { c: s.code })}</summary>
        <p className="mt-2 text-texte-2">{s.critere.definition}</p>
        <ul className="mt-2 list-disc space-y-0.5 pl-5 text-texte-2">{s.critere.checklist.map((q) => <li key={q}>{q}</li>)}</ul>
      </details>
    </div>
  );
}
