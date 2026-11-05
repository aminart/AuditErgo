import { useState } from "react";
import { cx } from "./ui";

/** Couleur d'un niveau de gravité : rampe ordinale d'une seule teinte (validée en clair et en sombre). */
export const couleurGravite = (g: number | null | undefined) => (g && g >= 1 && g <= 4 ? `var(--g${g})` : "var(--g0)");

export function PastilleGravite({ niveau, libelle }: { niveau: number | null; libelle: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-xs font-medium whitespace-nowrap text-texte">
      <span className="size-2.5 rounded-sm" style={{ background: couleurGravite(niveau) }} aria-hidden="true" />
      {niveau ? `${niveau} · ` : ""}{libelle}
    </span>
  );
}

interface Segment { cle: string; libelle: string; valeur: number; couleur: string }

/** Répartition en une barre empilée, avec légende chiffrée (l'identité ne repose jamais sur la couleur seule). */
export function BarreRepartition({ segments, unite }: { segments: Segment[]; unite: string }) {
  const total = segments.reduce((s, x) => s + x.valeur, 0);
  const [survol, setSurvol] = useState<string | null>(null);
  if (!total) return null;
  return (
    <div>
      <div className="relative flex h-7 gap-0.5" onMouseLeave={() => setSurvol(null)}>
        {segments.filter((s) => s.valeur > 0).map((s) => (
          <div key={s.cle} onMouseEnter={() => setSurvol(s.cle)} onFocus={() => setSurvol(s.cle)} tabIndex={0}
            className={cx("h-full first:rounded-l last:rounded-r transition-opacity outline-none", survol && survol !== s.cle && "opacity-50")}
            style={{ width: `${(s.valeur / total) * 100}%`, background: s.couleur, minWidth: 6 }}
            aria-label={`${s.libelle} : ${s.valeur} ${unite}`} />
        ))}
        {survol && (() => {
          const s = segments.find((x) => x.cle === survol)!;
          return (
            <div className="pointer-events-none absolute -top-11 left-1/2 z-10 -translate-x-1/2 rounded-md border border-bord bg-surface px-2.5 py-1.5 text-xs whitespace-nowrap shadow-lg">
              <span className="font-semibold">{s.libelle}</span> · {s.valeur} {unite} ({Math.round((s.valeur / total) * 100)} %)
            </div>
          );
        })()}
      </div>
      <ul className="mt-3 flex flex-wrap gap-x-5 gap-y-1.5">
        {segments.map((s) => (
          <li key={s.cle} className="flex items-center gap-1.5 text-xs text-texte-2">
            <span className="size-2.5 rounded-sm" style={{ background: s.couleur }} aria-hidden="true" />
            {s.libelle}
            <span className="font-semibold tabular-nums text-texte">{s.valeur}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

interface Barre { cle: string; libelle: string; valeur: number; detail?: string; couleur?: string; secondaire?: number }

/** Barres horizontales d'une seule série, valeur écrite au bout de chaque barre. */
export function BarresHorizontales({ barres, max, largeurLibelle = "14rem", unite = "" }: { barres: Barre[]; max?: number; largeurLibelle?: string; unite?: string }) {
  const plafond = max ?? Math.max(1, ...barres.map((b) => b.valeur + (b.secondaire ?? 0)));
  const [survol, setSurvol] = useState<string | null>(null);
  return (
    <ul className="space-y-1.5">
      {barres.map((b) => (
        <li key={b.cle} className="group grid items-center gap-3 text-sm" style={{ gridTemplateColumns: `minmax(0, ${largeurLibelle}) 1fr` }}
          onMouseEnter={() => setSurvol(b.cle)} onMouseLeave={() => setSurvol(null)}>
          <span className="truncate text-texte-2" title={b.libelle}>{b.libelle}</span>
          <div className="relative flex h-5 items-center gap-0.5">
            {b.valeur > 0 && <div className="h-full rounded-r" style={{ width: `${(b.valeur / plafond) * 100}%`, background: b.couleur ?? "var(--serie)" }} />}
            {!!b.secondaire && <div className="h-full rounded-r opacity-35" style={{ width: `${(b.secondaire / plafond) * 100}%`, background: b.couleur ?? "var(--serie)" }} />}
            <span className="ml-1.5 text-xs font-semibold tabular-nums text-texte">{b.valeur}{unite}{b.secondaire ? ` + ${b.secondaire}` : ""}</span>
            {survol === b.cle && b.detail && (
              <div className="pointer-events-none absolute bottom-full left-0 z-10 mb-1 max-w-sm rounded-md border border-bord bg-surface px-2.5 py-1.5 text-xs shadow-lg">{b.detail}</div>
            )}
          </div>
        </li>
      ))}
    </ul>
  );
}

/** Échelle de maturité à 5 niveaux, le niveau atteint mis en avant. */
export function EchelleMaturite({ niveaux, actuel, indicatif, libelleIndicatif }: {
  niveaux: { niveau: number; libelle: string; definition: string }[]; actuel: number; indicatif?: number; libelleIndicatif?: string;
}) {
  return (
    <ol className="grid grid-cols-5 gap-1.5">
      {niveaux.map((n) => {
        const atteint = n.niveau === actuel;
        return (
          <li key={n.niveau} title={n.definition}
            className={cx("bloc rounded-md border px-2 py-2.5 text-center", atteint ? "border-primary bg-primary text-on-primary" : "border-bord bg-surface-2 text-texte-2")}>
            <div className="text-lg font-semibold tabular-nums">{n.niveau}</div>
            <div className="text-xs font-medium">{n.libelle}</div>
            {indicatif === n.niveau && !atteint && <div className="mt-1 text-[10px] uppercase tracking-wide opacity-75">{libelleIndicatif}</div>}
          </li>
        );
      })}
    </ol>
  );
}
