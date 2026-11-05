import { useState, type ReactNode } from "react";

export function cx(...classes: (string | number | false | null | undefined)[]) {
  return classes.filter(Boolean).join(" ");
}

/* --- Icônes (traits 1.75, 20 px) ------------------------------------------------------------------ */

const CHEMINS: Record<string, ReactNode> = {
  relecture: <><path d="M9 3h6l5 5v11a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h3" /><path d="M14 3v5h5" /><path d="m9 14 2 2 4-4" /></>,
  suggestion: <><circle cx="12" cy="12" r="8" /><circle cx="12" cy="12" r="4" /><circle cx="12" cy="12" r="0.5" /></>,
  rapport: <><path d="M4 20V10" /><path d="M10 20V4" /><path d="M16 20v-7" /><path d="M22 20H2" /></>,
  reglages: <><circle cx="12" cy="12" r="3" /><path d="M12 2v3M12 19v3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M2 12h3M19 12h3M4.9 19.1 7 17M17 7l2.1-2.1" /></>,
  telecharger: <><path d="M12 4v11" /><path d="m7 10 5 5 5-5" /><path d="M5 20h14" /></>,
  importer: <><path d="M12 15V4" /><path d="m7 9 5-5 5 5" /><path d="M5 20h14" /></>,
  ia: <><path d="M12 3v3M12 18v3M3 12h3M18 12h3" /><path d="m12 7 1.5 3.5L17 12l-3.5 1.5L12 17l-1.5-3.5L7 12l3.5-1.5Z" /></>,
  ok: <><circle cx="12" cy="12" r="9" /><path d="m8 12 3 3 5-6" /></>,
  alerte: <><path d="M12 3 2 20h20L12 3Z" /><path d="M12 10v4M12 17v.5" /></>,
  info: <><circle cx="12" cy="12" r="9" /><path d="M12 11v6M12 7.5v.5" /></>,
  croix: <><path d="M6 6l12 12M18 6 6 18" /></>,
  crayon: <><path d="M4 20h4L19 9l-4-4L4 16v4Z" /><path d="m13 7 4 4" /></>,
  check: <path d="m5 12 5 5 9-10" />,
  fleche: <path d="m9 6 6 6-6 6" />,
  imprimer: <><path d="M7 9V3h10v6" /><rect x="3" y="9" width="18" height="8" rx="2" /><path d="M7 14h10v7H7z" /></>,
  copier: <><rect x="8" y="8" width="12" height="12" rx="2" /><path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2" /></>,
  soleil: <><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" /></>,
  lune: <path d="M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5Z" />,
  cadenas: <><rect x="5" y="11" width="14" height="10" rx="2" /><path d="M8 11V8a4 4 0 0 1 8 0v3" /></>,
  globe: <><circle cx="12" cy="12" r="9" /><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18" /></>,
  html: <><path d="m8 8-4 4 4 4M16 8l4 4-4 4" /><path d="m14 5-4 14" /></>,
  word: <><path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9l-6-6Z" /><path d="m8 12 1.5 5L12 13l2.5 4L16 12" /></>,
  historique: <><path d="M3 12a9 9 0 1 0 3-6.7L3 8" /><path d="M3 3v5h5" /><path d="M12 7v5l3 2" /></>,
  recherche: <><circle cx="11" cy="11" r="6" /><path d="m20 20-4.5-4.5" /></>,
  rafraichir: <><path d="M20 11a8 8 0 1 0-2.3 5.7" /><path d="M20 4v7h-7" /></>,
  plus: <path d="M12 5v14M5 12h14" />,
  oeil: <><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z" /><circle cx="12" cy="12" r="3" /></>,
  oeil_barre: <><path d="M10.6 5.1A10.4 10.4 0 0 1 12 5c6.5 0 10 7 10 7a17 17 0 0 1-2.2 3.2M6.6 6.6A17 17 0 0 0 2 12s3.5 7 10 7a9.8 9.8 0 0 0 5.4-1.6" /><path d="M9.9 9.9a3 3 0 0 0 4.2 4.2" /><path d="m2 2 20 20" /></>,
  bouclier: <><path d="M12 3 4 6v6c0 4.5 3.4 8 8 9 4.6-1 8-4.5 8-9V6l-8-3Z" /><path d="m9 12 2 2 4-4" /></>,
  bouclier_alerte: <><path d="M12 3 4 6v6c0 4.5 3.4 8 8 9 4.6-1 8-4.5 8-9V6l-8-3Z" /><path d="M12 8v4M12 15.5v.5" /></>,
};

export function Icone({ nom, className = "size-5" }: { nom: keyof typeof CHEMINS | string; className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round"
      strokeLinejoin="round" className={cx("shrink-0", className)} aria-hidden="true">
      {CHEMINS[nom]}
    </svg>
  );
}

/* --- Éléments ------------------------------------------------------------------------------------- */

type Ton = "neutre" | "ok" | "alerte" | "danger" | "info" | "ia" | "marque";
const TONS: Record<Ton, string> = {
  neutre: "bg-surface-2 text-texte-2",
  ok: "bg-ok-doux text-ok",
  alerte: "bg-alerte-doux text-alerte",
  danger: "bg-danger-doux text-danger",
  info: "bg-info-doux text-info",
  ia: "bg-ia-doux text-ia",
  marque: "bg-marque-doux text-marque",
};

export function Badge({ ton = "neutre", children, icone, titre }: { ton?: Ton; children: ReactNode; icone?: string; titre?: string }) {
  return (
    <span title={titre} className={cx("inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium whitespace-nowrap", TONS[ton])}>
      {icone && <Icone nom={icone} className="size-3.5" />}
      {children}
    </span>
  );
}

export function Alerte({ ton = "info", titre, children, action }: { ton?: Ton; titre?: ReactNode; children?: ReactNode; action?: ReactNode }) {
  const icone = ton === "ok" ? "ok" : ton === "danger" || ton === "alerte" ? "alerte" : ton === "ia" ? "ia" : "info";
  return (
    <div role={ton === "danger" ? "alert" : "status"} className={cx("flex items-start gap-3 rounded-lg px-4 py-3 text-sm", TONS[ton])}>
      <Icone nom={icone} className="mt-0.5 size-5" />
      <div className="min-w-0 flex-1">
        {titre && <div className="font-semibold">{titre}</div>}
        {children && <div className={cx(!!titre && "mt-0.5", "text-texte-2 [&_strong]:text-texte")}>{children}</div>}
      </div>
      {action}
    </div>
  );
}

export function Metrique({ libelle, valeur, detail, aide }: { libelle: string; valeur: ReactNode; detail?: ReactNode; aide?: string }) {
  return (
    <div className="carte px-4 py-3.5" title={aide}>
      <div className="text-xs font-medium text-texte-2">{libelle}</div>
      <div className="mt-1 text-2xl font-semibold tabular-nums tracking-tight">{valeur}</div>
      {detail && <div className="mt-0.5 text-xs text-texte-3">{detail}</div>}
    </div>
  );
}

export function Progression({ fait, total, libelle }: { fait: number; total: number; libelle: string }) {
  const part = total ? Math.min(1, fait / total) : 0;
  return (
    <div className="space-y-2" aria-live="polite">
      <div className="flex justify-between text-sm text-texte-2">
        <span>{libelle}</span>
        {total > 0 && <span className="tabular-nums">{Math.round(part * 100)} %</span>}
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-surface-2" role="progressbar" aria-valuenow={Math.round(part * 100)} aria-valuemin={0} aria-valuemax={100}>
        <div className={cx("h-full rounded-full bg-ia transition-all duration-500", !total && "w-1/3 animate-pulse")} style={total ? { width: `${part * 100}%` } : undefined} />
      </div>
    </div>
  );
}

export function Spinner({ className = "size-4" }: { className?: string }) {
  return <span className={cx("inline-block animate-spin rounded-full border-2 border-current border-r-transparent", className)} aria-hidden="true" />;
}

export function Onglets<T extends string>({ onglets, actif, choisir }: { onglets: { id: T; libelle: string; compte?: number }[]; actif: T; choisir: (id: T) => void }) {
  return (
    <div role="tablist" className="flex gap-1 overflow-x-auto border-b border-bord">
      {onglets.map((o) => (
        <button key={o.id} role="tab" aria-selected={o.id === actif} onClick={() => choisir(o.id)}
          className={cx("-mb-px flex items-center gap-2 border-b-2 px-3.5 py-2.5 text-sm font-medium whitespace-nowrap transition-colors",
            o.id === actif ? "border-marque text-marque" : "border-transparent text-texte-2 hover:text-texte")}>
          {o.libelle}
          {o.compte !== undefined && <span className="rounded-full bg-surface-3 px-1.5 text-xs tabular-nums text-texte-2">{o.compte}</span>}
        </button>
      ))}
    </div>
  );
}

// Noms de classes écrits en entier : Tailwind ne repère pas les noms construits dynamiquement
const VARIANTES = { primaire: "btn-primaire", secondaire: "btn-secondaire", ia: "btn-ia", discret: "btn-discret" } as const;

export function Bouton({ variante = "secondaire", icone, children, className, ...props }:
  { variante?: "primaire" | "secondaire" | "ia" | "discret"; icone?: string; children?: ReactNode } & React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button className={cx(VARIANTES[variante], className)} {...props}>
      {icone && <Icone nom={icone} className="size-4" />}
      {children}
    </button>
  );
}

export function Lien({ variante = "secondaire", icone, children, className, ...props }:
  { variante?: "primaire" | "secondaire" | "ia" | "discret"; icone?: string; children?: ReactNode } & React.AnchorHTMLAttributes<HTMLAnchorElement>) {
  return (
    <a className={cx(VARIANTES[variante], className)} {...props}>
      {icone && <Icone nom={icone} className="size-4" />}
      {children}
    </a>
  );
}

export function Copier({ texte, libelle, copie }: { texte: string; libelle: string; copie: string }) {
  const [fait, setFait] = useState(false);
  return (
    <button className="btn-discret text-xs" onClick={async () => {
      try { await navigator.clipboard.writeText(texte); } catch { /* presse-papiers indisponible */ }
      setFait(true);
      setTimeout(() => setFait(false), 1500);
    }}>
      <Icone nom={fait ? "check" : "copier"} className="size-3.5" />
      {fait ? copie : libelle}
    </button>
  );
}

export function Section({ titre, intro, children, action }: { titre: ReactNode; intro?: ReactNode; children: ReactNode; action?: ReactNode }) {
  return (
    <section className="carte p-5">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold">{titre}</h2>
          {intro && <p className="mt-1 max-w-3xl text-sm text-texte-2">{intro}</p>}
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}
