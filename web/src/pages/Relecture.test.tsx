import { useState } from "react";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import PageRelecture from "./Relecture";
import type { EtatAudit } from "../types";
import { avisIA, config, constat, differe, etat, serveurFactice, tache } from "../test/fixtures";

let serveur: ReturnType<typeof serveurFactice>;
beforeEach(() => {
  serveur = serveurFactice();
  vi.stubGlobal("fetch", serveur.fetch);
});

/** L'écran tel que l'affiche l'application : l'état de l'audit est tenu au-dessus de lui. */
function Ecran({ initial }: { initial: EtatAudit }) {
  const [e, setE] = useState<EtatAudit | null>(initial);
  return <PageRelecture config={config} etat={e} setEtat={setE} allerRapport={() => undefined} ouvrir={() => undefined} allerHistorique={() => undefined} />;
}

const bouton = (nom: string) => screen.getByRole("button", { name: nom });
const pasDeBouton = (nom: string) => expect(screen.queryByRole("button", { name: nom })).not.toBeInTheDocument();

/** Réponse du serveur à une décision : son état fait foi, on le reconnaît à une anomalie qu'il est seul à donner. */
function reponseServeur(message: string, modifier: (e: EtatAudit) => EtatAudit = (e) => e): EtatAudit {
  const e = modifier(etat());
  const anomalie = { niveau: "avertissement" as const, code: "TEST", message, ligne: 2, constat: "C2", champ: null };
  return { ...e, constats: e.constats.map((c) => ({ ...c, anomalies: [anomalie] })), anomalies: [anomalie] };
}
const valide = (e: EtatAudit, champ: string): EtatAudit => ({
  ...e,
  constats: e.constats.map((c) => ({ ...c, completions: { ...c.completions, [champ]: { ...c.completions[champ], origine: "valide" } } })),
  a_valider: e.a_valider - 1,
});

/* --- Décisions affichées sans attendre le serveur ------------------------------------------------------ */

describe("Décisions sur les propositions", () => {
  it("valider une proposition change l'écran avant la réponse du serveur, qui fait foi ensuite", async () => {
    const reponse = differe<{ corps: unknown }>();
    serveur.route("POST", /\/api\/audits\/a1\/decisions$/, () => reponse.promesse);
    render(<Ecran initial={etat()} />);
    expect(bouton("Tout valider (2)")).toBeInTheDocument();

    await userEvent.click(bouton("Valider : Critère"));

    // Tout de suite : la cellule est validée, le compteur suit, la requête est partie
    pasDeBouton("Valider : Critère");
    expect(bouton("Valider : Gravité")).toBeEnabled();
    expect(bouton("Tout valider (1)")).toBeInTheDocument();
    expect(serveur.vers("POST", "/api/audits/a1/decisions")[0].corps).toEqual({
      decisions: [{ ligne: 2, champ: "critere", action: "valider" }], langue: "fr",
    });

    // Puis : l'état recalculé par le serveur remplace l'état affiché
    await act(async () => reponse.resoudre({ corps: reponseServeur("Recalculé par le serveur", (e) => valide(e, "critere")) }));
    expect(screen.getAllByText("Recalculé par le serveur").length).toBeGreaterThan(0);
    pasDeBouton("Valider : Critère");
  });

  it("refuser une proposition la retire tout de suite", async () => {
    serveur.route("POST", /\/api\/audits\/a1\/decisions$/, () => new Promise(() => undefined)); // le serveur ne répond pas
    render(<Ecran initial={etat()} />);
    expect(screen.getByText("3 · Élevée")).toBeInTheDocument();

    await userEvent.click(bouton("Refuser : Gravité"));

    expect(screen.queryByText("3 · Élevée")).not.toBeInTheDocument();
    pasDeBouton("Valider : Gravité");
    expect(bouton("Tout valider (1)")).toBeInTheDocument();
  });

  it("modifier une proposition affiche tout de suite la valeur saisie, validée", async () => {
    serveur.route("POST", /\/api\/audits\/a1\/decisions$/, () => new Promise(() => undefined));
    render(<Ecran initial={etat()} />);

    await userEvent.click(bouton("Modifier : Critère"));
    const saisie = screen.getByRole("textbox", { name: "" });
    await userEvent.clear(saisie);
    await userEvent.type(saisie, "1.2 Groupement");
    await userEvent.click(bouton("Enregistrer"));

    expect(screen.getByText("1.2 Groupement")).toBeInTheDocument();
    pasDeBouton("Valider : Critère");
    expect(serveur.vers("POST", "/api/audits/a1/decisions")[0].corps).toEqual({
      decisions: [{ ligne: 2, champ: "critere", action: "modifier", valeur: "1.2 Groupement" }], langue: "fr",
    });
  });

  it("modifier la gravité proposée change tout de suite le niveau affiché", async () => {
    serveur.route("POST", /\/api\/audits\/a1\/decisions$/, () => new Promise(() => undefined));
    render(<Ecran initial={etat()} />);

    await userEvent.click(bouton("Modifier : Gravité"));
    const saisie = screen.getByRole("textbox", { name: "" });
    await userEvent.clear(saisie);
    await userEvent.type(saisie, "1");
    await userEvent.click(bouton("Enregistrer"));

    expect(screen.getByText("1 · Mineure")).toBeInTheDocument();
    expect(screen.queryByText("3 · Élevée")).not.toBeInTheDocument();
  });

  it("« Tout valider » valide toutes les propositions de l'audit en une requête", async () => {
    serveur.route("POST", /\/api\/audits\/a1\/decisions$/, () => new Promise(() => undefined));
    render(<Ecran initial={etat({ constats: [constat(2), constat(3)] })} />);

    await userEvent.click(bouton("Tout valider (4)"));

    expect(screen.queryAllByRole("button", { name: /^Valider : / })).toHaveLength(0);
    pasDeBouton("Tout valider (4)");
    const [requete] = serveur.vers("POST", "/api/audits/a1/decisions");
    expect((requete.corps as { decisions: unknown[] }).decisions).toHaveLength(4);
  });

  it("des décisions rapprochées partent l'une après l'autre, et seule la dernière réponse remplace l'écran", async () => {
    const reponses = [differe<{ corps: unknown }>(), differe<{ corps: unknown }>()];
    let n = 0;
    serveur.route("POST", /\/api\/audits\/a1\/decisions$/, () => reponses[n++].promesse);
    render(<Ecran initial={etat()} />);

    await userEvent.click(bouton("Valider : Critère"));
    await userEvent.click(bouton("Refuser : Gravité"));

    // Les deux décisions sont à l'écran ; la seconde requête attend la première
    pasDeBouton("Valider : Critère");
    expect(screen.queryByText("3 · Élevée")).not.toBeInTheDocument();
    expect(serveur.vers("POST", "/api/audits/a1/decisions")).toHaveLength(1);

    // Réponse à la première : elle ignore encore le refus, l'écran ne revient donc pas en arrière
    await act(async () => reponses[0].resoudre({ corps: reponseServeur("Après la première", (e) => valide(e, "critere")) }));
    expect(screen.queryByText("Après la première")).not.toBeInTheDocument();
    expect(screen.queryByText("3 · Élevée")).not.toBeInTheDocument();
    await waitFor(() => expect(serveur.vers("POST", "/api/audits/a1/decisions")).toHaveLength(2));
    expect(serveur.vers("POST", "/api/audits/a1/decisions")[1].corps).toEqual({
      decisions: [{ ligne: 2, champ: "gravite", action: "refuser" }], langue: "fr",
    });

    // Réponse à la seconde : c'est elle qui fait foi
    await act(async () => reponses[1].resoudre({
      corps: reponseServeur("Après la seconde", (e) => {
        const v = valide(e, "critere");
        return { ...v, a_valider: 0, constats: v.constats.map((c) => { const { gravite: _, ...reste } = c.completions; return { ...c, gravite: null, completions: reste }; }) };
      }),
    }));
    expect(screen.getAllByText("Après la seconde").length).toBeGreaterThan(0);
    expect(screen.queryByText("3 · Élevée")).not.toBeInTheDocument();
  });

  it("si le serveur refuse une décision, l'erreur s'affiche et l'audit est rechargé tel qu'il est sur le serveur", async () => {
    serveur.route("POST", /\/api\/audits\/a1\/decisions$/, () => ({ statut: 409, corps: { detail: "Une analyse est en cours sur cet audit." } }));
    serveur.route("GET", /^\/api\/audits\/a1$/, () => ({ corps: etat() }));
    render(<Ecran initial={etat()} />);

    await userEvent.click(bouton("Valider : Critère"));

    expect(await screen.findByText("Une analyse est en cours sur cet audit.")).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "Valider : Critère" })).toBeInTheDocument(); // décision annulée à l'écran
    expect(serveur.vers("GET", "/api/audits/a1")).toHaveLength(1);
  });

  it("prendre l'avis de l'IA attend le serveur, qui calcule la valeur, et bloque les autres décisions en attendant", async () => {
    const reponse = differe<{ corps: unknown }>();
    serveur.route("POST", /\/api\/audits\/a1\/decisions$/, () => reponse.promesse);
    const avecEcart = constat(2, { ia: avisIA, ecarts_ia: { critere: true, recommandation: false, gravite: false } });
    render(<Ecran initial={etat({ constats: [avecEcart], ia: { analyses: 1, erreurs: 0, depuis_cache: 0, criteres_a_revoir: 1, recos_a_ameliorer: 0 } })} />);

    await userEvent.click(bouton("Prendre l'avis de l'IA"));

    // Rien n'est appliqué à l'écran, les boutons sont bloqués le temps de la réponse
    expect(bouton("Valider : Critère")).toBeDisabled();
    expect(bouton("Prendre l'avis de l'IA")).toBeDisabled();
    expect(serveur.vers("POST", "/api/audits/a1/decisions")[0].corps).toEqual({
      decisions: [{ ligne: 2, champ: "critere", action: "adopter" }], langue: "fr",
    });

    await act(async () => reponse.resoudre({
      corps: etat({
        ia: { analyses: 1, erreurs: 0, depuis_cache: 0, criteres_a_revoir: 0, recos_a_ameliorer: 0 },
        constats: [{ ...avecEcart, ecarts_ia: null, completions: { ...avecEcart.completions, critere: { valeur: "1.2 Groupement", origine: "valide", explication: "", adopte: true } } }],
      }),
    }));
    expect(screen.getByText("Avis IA adopté")).toBeInTheDocument();
    expect(screen.getByText("1.2 Groupement")).toBeInTheDocument();
    expect(bouton("Revenir à votre saisie : Critère")).toBeEnabled();
    pasDeBouton("Prendre l'avis de l'IA");
  });

  it("une réponse arrivée après l'ouverture d'un autre audit ne l'écrase pas", async () => {
    const reponse = differe<{ corps: unknown }>();
    serveur.route("POST", /\/api\/audits\/a1\/decisions$/, () => reponse.promesse);
    serveur.route("POST", /^\/api\/audits$/, () => ({ corps: etat({ id: "a2", nom: "Autre audit" }) }));
    const { container } = render(<Ecran initial={etat()} />);

    await userEvent.click(bouton("Valider : Critère"));
    // « Importer un autre audit » pendant que la décision est en route
    const entree = container.querySelectorAll<HTMLInputElement>("input[type=file]")[1];
    await userEvent.upload(entree, new File(["x"], "autre.xlsx"));
    expect(await screen.findByRole("heading", { name: "Autre audit" })).toBeInTheDocument();

    await act(async () => reponse.resoudre({ corps: reponseServeur("Réponse pour le premier audit") }));
    expect(screen.getByRole("heading", { name: "Autre audit" })).toBeInTheDocument();
    expect(screen.queryByText("Réponse pour le premier audit")).not.toBeInTheDocument();
  });
});

/* --- Suivi de l'analyse par l'IA, repris au retour sur l'écran -------------------------------------------- */

describe("Suivi de l'analyse par l'IA", () => {
  // Le suivi interroge le serveur toutes les 700 ms : le temps est avancé à la main
  beforeEach(() => { vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout", "Date"] }); });
  const attendre = (ms: number) => act(() => vi.advanceTimersByTimeAsync(ms));
  const analyseFaite = { analyses: 1, erreurs: 0, depuis_cache: 0, criteres_a_revoir: 0, recos_a_ameliorer: 0 };

  it("reprend la progression d'une analyse déjà lancée (retour sur l'écran, page rechargée) jusqu'à son résultat", async () => {
    const etapes = [tache("t1", { fait: 2, total: 5 }), tache("t1", { fait: 4, total: 5 }), tache<EtatAudit>("t1", { etat: "terminee", fait: 5, total: 5, resultat: etat({ ia: analyseFaite }) })];
    serveur.route("GET", /^\/api\/taches\/t1$/, () => ({ corps: etapes.shift() }));
    render(<Ecran initial={etat({ tache: { id: "t1", nom: "ia" } })} />);

    expect(screen.getByText("Démarrage de l'analyse…")).toBeInTheDocument();
    expect(bouton("Valider : Critère")).toBeDisabled(); // pas de décision pendant l'analyse

    await attendre(700);
    expect(screen.getByText("Analyse par le modèle : 2 / 5 · moins d'une minute restante")).toBeInTheDocument();
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "40");

    await attendre(700);
    expect(screen.getByText(/^Analyse par le modèle : 4 \/ 5/)).toBeInTheDocument();

    await attendre(700);
    expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();
    expect(screen.getByText(/^Analyse faite : 1 constat\(s\)/)).toBeInTheDocument();
    expect(bouton("Valider : Critère")).toBeEnabled();
    expect(serveur.vers("GET", "/api/taches/t1")).toHaveLength(3);
  });

  it("reprend le suivi quand on revient sur l'écran pendant l'analyse", async () => {
    serveur.route("GET", /^\/api\/taches\/t1$/, () => ({ corps: tache("t1", { fait: 1, total: 3 }) }));
    const premier = render(<Ecran initial={etat({ tache: { id: "t1", nom: "ia" } })} />);
    await attendre(700);
    expect(screen.getByText(/^Analyse par le modèle : 1 \/ 3/)).toBeInTheDocument();
    premier.unmount(); // autre écran ; l'analyse continue sur le serveur

    serveur.route("GET", /^\/api\/taches\/t1$/, () => ({ corps: tache<EtatAudit>("t1", { etat: "terminee", fait: 3, total: 3, resultat: etat({ ia: analyseFaite }) }) }));
    render(<Ecran initial={etat({ tache: { id: "t1", nom: "ia" } })} />);
    expect(screen.getByText("Démarrage de l'analyse…")).toBeInTheDocument();
    await attendre(700);
    expect(screen.getByText(/^Analyse faite/)).toBeInTheDocument();
  });

  it("suit l'analyse en cours d'un audit ouvert depuis cet écran", async () => {
    serveur.route("POST", /^\/api\/audits$/, () => ({ corps: etat({ id: "a2", nom: "Autre audit", tache: { id: "t3", nom: "ia" } }) }));
    serveur.route("GET", /^\/api\/taches\/t3$/, () => ({ corps: tache("t3", { fait: 1, total: 4 }) }));
    const { container } = render(<Ecran initial={etat()} />);
    expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();

    fireEvent.change(container.querySelectorAll<HTMLInputElement>("input[type=file]")[1], { target: { files: [new File(["x"], "autre.xlsx")] } });
    await attendre(0);
    expect(screen.getByRole("heading", { name: "Autre audit" })).toBeInTheDocument();
    expect(screen.getByRole("progressbar")).toBeInTheDocument();
    await attendre(700);
    expect(screen.getByText(/^Analyse par le modèle : 1 \/ 4/)).toBeInTheDocument();
  });

  it("lancer une analyse la suit une seule fois, même quand l'état de l'audit annonce la tâche", async () => {
    serveur.route("POST", /\/api\/audits\/a1\/ia$/, () => ({ corps: tache("t2", { fait: 0, total: 1 }) }));
    serveur.route("GET", /^\/api\/taches\/t2$/, () => ({ corps: tache("t2", { fait: 0, total: 1 }) }));
    render(<Ecran initial={etat()} />);

    fireEvent.click(bouton("Analyser 1 constat(s)"));
    await attendre(0);
    expect(serveur.vers("POST", "/api/audits/a1/ia")[0].corps).toEqual({ remplir: true, forcer: false, langue: "fr" });
    pasDeBouton("Analyser 1 constat(s)"); // la progression prend sa place
    expect(screen.getByRole("progressbar")).toBeInTheDocument();

    await attendre(700);
    expect(serveur.vers("GET", "/api/taches/t2")).toHaveLength(1);
    await attendre(700);
    expect(serveur.vers("GET", "/api/taches/t2")).toHaveLength(2);

    serveur.route("GET", /^\/api\/taches\/t2$/, () => ({ corps: tache<EtatAudit>("t2", { etat: "terminee", fait: 1, total: 1, resultat: etat({ ia: analyseFaite }) }) }));
    await attendre(700);
    expect(screen.getByText(/^Analyse faite/)).toBeInTheDocument();
    await attendre(2100);
    expect(serveur.vers("GET", "/api/taches/t2")).toHaveLength(3); // plus d'interrogation une fois finie
  });

  it("si l'analyse échoue, l'erreur s'affiche et l'audit redevient utilisable", async () => {
    serveur.route("GET", /^\/api\/taches\/t1$/, () => ({ corps: tache("t1", { etat: "erreur", erreur: "Le modèle ne répond pas." }) }));
    render(<Ecran initial={etat({ tache: { id: "t1", nom: "ia" } })} />);
    pasDeBouton("Analyser 1 constat(s)");

    await attendre(700);
    expect(within(screen.getByRole("alert")).getByText("Le modèle ne répond pas.")).toBeInTheDocument();
    expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();
    expect(bouton("Analyser 1 constat(s)")).toBeEnabled();
    expect(bouton("Valider : Critère")).toBeEnabled();
  });

  it("une rédaction du rapport en cours est signalée sans être suivie ici", async () => {
    render(<Ecran initial={etat({ tache: { id: "r1", nom: "rapport" } })} />);
    await attendre(1400);
    expect(screen.getByText(/rapport/i, { selector: "div" })).toBeInTheDocument();
    expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();
    expect(serveur.vers("GET", "/api/taches/r1")).toHaveLength(0);
    expect(bouton("Valider : Critère")).toBeDisabled();
  });
});
