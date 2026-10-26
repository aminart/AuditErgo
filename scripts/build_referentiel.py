"""Construit le référentiel JSON à partir des CSV sources, des corrections et des règles de départage.

Usage : python3 scripts/build_referentiel.py  (depuis le dossier du dépôt)

Entrées  : referentiel/source/*.csv, referentiel/corrections.json, referentiel/regles_departage.json
Sorties  : referentiel/referentiel.json, referentiel/CHANGEMENTS.md
"""
import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REF = ROOT / "referentiel"
SRC = REF / "source"


def read(name):
    with open(SRC / name, encoding="utf-8-sig") as f:
        return list(csv.reader(f, delimiter=";"))


def clean(text):
    return re.sub(r"[  ‍]+", " ", text).strip()


def slug(text):
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def split_name(cell):
    """'Prompting\n(Bastien & Scapin)' -> ('Prompting', ['Bastien & Scapin'])"""
    lines = [clean(l) for l in cell.split("\n") if clean(l)]
    name = lines[0]
    sources = re.findall(r"\(([^)]+)\)", " ".join(lines[1:]))
    return name, sources


def questions(cell):
    out = []
    current = ""
    for line in cell.split("\n"):
        line = clean(line)
        if not line or line.lower().startswith(("etc", "example", "for more information", "http")):
            continue
        current = f"{current} {line}".strip()
        if current.endswith("?"):
            out.append(current)
            current = ""
    return out


def parse_grid():
    rows = read("criterias_Evaluation_template.csv")
    categories = []
    # Chaque catégorie occupe un bloc de 4 colonnes : [vide, critère, définition, questions]
    for col in range(1, len(rows[3]), 4):
        label = clean(rows[3][col]) if col < len(rows[3]) else ""
        if not label:
            continue
        cat = {
            "id": slug(label),
            "label": label.replace("_", " "),
            "definition": clean(rows[2][col]) if col < len(rows[2]) else "",
            "criteria": [],
        }
        for r in rows[4:]:
            if col >= len(r) or not clean(r[col]):
                continue
            name, sources = split_name(r[col])
            cat["criteria"].append({
                "id": f"{cat['id']}.{slug(name)}",
                "name": name,
                "sources": sources,
                "definition": clean(r[col + 1]) if col + 1 < len(r) else "",
                "checklist": questions(r[col + 2]) if col + 2 < len(r) else [],
            })
        categories.append(cat)
    return categories


def parse_frameworks():
    rows = read("Heuristic_Evaluation_template.csv")[1:]
    frameworks = {}
    current = None
    for r in rows:
        if len(r) < 5 or not clean(r[2]):
            continue
        if clean(r[0]):
            current = clean(r[0])
        frameworks.setdefault(current, []).append({
            "criterion": clean(r[2]),
            "details": clean(r[3]),
            "quality_component": clean(r[4]),
        })
    return [{"framework": k, "heuristics": v} for k, v in frameworks.items()]


class Builder:
    def __init__(self, corrections):
        self.corr = corrections
        self.errors = []
        self.journal = []

    def fix(self, text):
        for old, new in self.corr.get("corrections_texte", []):
            text = text.replace(old, new)
        return text

    def criterion(self, raw, cat_code):
        c = self.corr["criteres"].get(raw["id"])
        if c is None:
            self.errors.append(f"Critère sans correction (code manquant) : {raw['id']}")
            return None
        code = c["code"]
        if not code.startswith(cat_code + "-"):
            self.errors.append(f"{code} n'appartient pas à la catégorie {cat_code}")

        original = [self.fix(q) for q in raw["checklist"]]
        retirees = [{**r, "q": self.fix(r["q"])} for r in c.get("retirees", [])]
        removed = {r["q"] for r in retirees}
        for q in removed - set(original):
            self.errors.append(f"{code} : question retirée introuvable dans la source : {q}")

        if "checklist" in c:
            items = c["checklist"]
        else:
            items = [{"q": q, "statut": "source"} for q in original if q not in removed]

        checklist = []
        for i, item in enumerate(items, 1):
            q = self.fix(item["q"])
            if item["statut"] == "source" and q not in original:
                self.errors.append(f"{code} : question marquée 'source' absente de la source : {q}")
            checklist.append({"id": f"{code}-Q{i:02d}", "q": q, "statut": item["statut"],
                              **({"origine": item["origine"]} if "origine" in item else {})})

        kept = {i["q"] for i in checklist}
        for q in original:
            if q not in kept and q not in removed:
                self.errors.append(f"{code} : question d'origine perdue sans justification : {q}")

        for r in retirees:
            self.journal.append({"type": "question_deplacee" if r.get("vers") else "question_retiree",
                                 "critere": code, "question": r["q"], "vers": r.get("vers"),
                                 "raison": r["raison"]})
        for item in checklist:
            if item["statut"] == "proposee":
                self.journal.append({"type": "question_proposee", "critere": code, "question": item["q"]})
        if "definition" in c:
            self.journal.append({"type": "definition_modifiee", "critere": code,
                                 "avant": raw["definition"], "apres": c["definition"]})
        name = c.get("name", self.fix(raw["name"]))
        if name != raw["name"]:
            self.journal.append({"type": "nom_modifie", "critere": code, "avant": raw["name"], "apres": name})
        if c.get("note"):
            self.journal.append({"type": "note", "critere": code, "texte": c["note"]})

        return {
            "code": code,
            "id_source": raw["id"],
            "name": name,
            "label_fr": c["label_fr"],
            "sources": raw["sources"],
            "definition": self.fix(c.get("definition", raw["definition"])),
            "statut_definition": c.get("statut_definition", "source"),
            "checklist": checklist,
            **({"note": c["note"]} if c.get("note") else {}),
        }

    def grid(self, raw_grid):
        out = []
        for raw in raw_grid:
            cc = self.corr["categories"][raw["id"]]
            cat = {
                "code": cc["code"],
                "id_source": raw["id"],
                "label": cc["label"],
                "label_fr": cc["label_fr"],
                "definition": self.fix(cc.get("definition", raw["definition"])),
                "statut_definition": cc.get("statut_definition", "source"),
                "criteria": [x for x in (self.criterion(c, cc["code"]) for c in raw["criteria"]) if x],
            }
            if "definition" in cc:
                self.journal.append({"type": "definition_modifiee", "critere": cc["code"],
                                     "avant": raw["definition"], "apres": cc["definition"]})
            out.append(cat)
        codes = [c["code"] for cat in out for c in cat["criteria"]]
        dupes = {c for c in codes if codes.count(c) > 1}
        if dupes:
            self.errors.append(f"Codes en double : {sorted(dupes)}")
        # Une question déplacée doit exister dans le critère d'origine
        origin_q = {}
        for raw in raw_grid:
            for c in raw["criteria"]:
                code = self.corr["criteres"].get(c["id"], {}).get("code")
                origin_q[code] = {self.fix(q) for q in c["checklist"]}
        for cat in out:
            for c in cat["criteria"]:
                for item in c["checklist"]:
                    if item["statut"] == "deplacee" and item["q"] not in origin_q.get(item.get("origine"), set()):
                        self.errors.append(f"{c['code']} : question déplacée absente de {item.get('origine')} : {item['q']}")
        return out

    def frameworks(self, raw_frameworks):
        for fx in self.corr.get("frameworks", []):
            fw = next((f for f in raw_frameworks if f["framework"] == fx["framework"]), None)
            h = fw and next((h for h in fw["heuristics"] if h["criterion"] == fx["criterion"]), None)
            if not h:
                self.errors.append(f"Heuristique introuvable : {fx['framework']} / {fx['criterion']}")
                continue
            if "details" in fx:
                self.journal.append({"type": "heuristique_modifiee", "critere": f"{fx['framework']} / {fx['criterion']}",
                                     "avant": h["details"], "apres": fx["details"], "raison": fx["raison"]})
                h["details"] = fx["details"]
            if "new_criterion" in fx:
                self.journal.append({"type": "heuristique_modifiee", "critere": fx["framework"],
                                     "avant": h["criterion"], "apres": fx["new_criterion"], "raison": fx["raison"]})
                h["criterion"] = fx["new_criterion"]
            h["statut"] = "modifiee"
        return raw_frameworks


def changements_md(version, grid, journal):
    by_type = lambda t: [j for j in journal if j["type"] == t]
    n_prop = len(by_type("question_proposee"))
    lines = [
        f"# Modifications proposées du référentiel (version {version})",
        "",
        "> Fichier généré par `scripts/build_referentiel.py` : ne pas modifier à la main.",
        "> Pour accepter, modifier ou refuser une proposition, éditer `referentiel/corrections.json` puis relancer le script.",
        "",
        "Toutes les propositions ci-dessous sont **à valider** par les designers seniors. Les CSV d'origine (`referentiel/source/`) ne sont pas modifiés.",
        "",
        "## Synthèse",
        "",
        f"- **{sum(len(c['criteria']) for c in grid)} critères** répartis en {len(grid)} catégories, chacun avec un code stable (ex. `GUI-01`).",
        f"- **{n_prop} questions de checklist proposées**, pour les critères qui n'en avaient pas ou pas assez.",
        f"- **{len(by_type('question_deplacee'))} questions déplacées ou retirées** pour supprimer les doublons entre critères.",
        f"- **{len(by_type('definition_modifiee'))} définitions et {len(by_type('heuristique_modifiee'))} heuristiques corrigées**.",
        "",
        "## Codes des critères",
        "",
        "| Code | Critère | Nom français | Questions |",
        "|---|---|---|---|",
    ]
    for cat in grid:
        for c in cat["criteria"]:
            stats = {s: sum(1 for i in c["checklist"] if i["statut"] == s) for s in ("source", "deplacee", "proposee")}
            detail = f"{len(c['checklist'])} ({stats['source']} source, {stats['deplacee']} déplacées, {stats['proposee']} proposées)"
            lines.append(f"| `{c['code']}` | {c['name']} | {c['label_fr']} | {detail} |")
    lines += ["", "## Questions déplacées ou retirées", "", "| Critère | Question | Vers | Raison |", "|---|---|---|---|"]
    for j in by_type("question_deplacee") + by_type("question_retiree"):
        lines.append(f"| `{j['critere']}` | {j['question']} | {('`' + j['vers'] + '`') if j['vers'] else '–'} | {j['raison']} |")
    lines += ["", "## Questions proposées", ""]
    current = None
    for j in by_type("question_proposee"):
        if j["critere"] != current:
            current = j["critere"]
            lines += ["", f"**`{current}`**", ""]
        lines.append(f"- [ ] {j['question']}")
    lines += ["", "## Définitions et heuristiques corrigées", ""]
    for j in by_type("definition_modifiee") + by_type("heuristique_modifiee"):
        lines += [f"**{j['critere']}**" + (f" : {j['raison']}" if j.get("raison") else ""), "",
                  f"- Avant : {j['avant'] or '(vide)'}", f"- Après : {j['apres']}", ""]
    lines += ["## Noms corrigés", "", "| Code | Avant | Après |", "|---|---|---|"]
    for j in by_type("nom_modifie"):
        lines.append(f"| `{j['critere']}` | {j['avant']} | {j['apres']} |")
    lines += ["", "## Notes", ""]
    for j in by_type("note"):
        lines.append(f"- `{j['critere']}` : {j['texte']}")
    return "\n".join(lines) + "\n"


def main():
    corrections = json.loads((REF / "corrections.json").read_text(encoding="utf-8"))
    regles = json.loads((REF / "regles_departage.json").read_text(encoding="utf-8"))
    b = Builder(corrections)
    grid = b.grid(parse_grid())
    frameworks = b.frameworks(parse_frameworks())

    codes = {c["code"] for cat in grid for c in cat["criteria"]}
    for r in regles["regles"]:
        for cas in r["cas"]:
            if cas["critere"] not in codes:
                b.errors.append(f"Règle {r['id']} : critère inconnu {cas['critere']}")
    for j in b.journal:
        if j.get("vers") and j["vers"] not in codes:
            b.errors.append(f"{j['critere']} : destination inconnue {j['vers']}")

    if b.errors:
        print("Erreurs dans le référentiel :", *b.errors, sep="\n- ")
        sys.exit(1)

    data = {
        "version": corrections["version"],
        "grid": grid,
        "regles_departage": {k: v for k, v in regles.items() if not k.startswith("_")},
        "frameworks": frameworks,
        "journal_modifications": b.journal,
    }
    (REF / "referentiel.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (REF / "CHANGEMENTS.md").write_text(changements_md(data["version"], grid, b.journal), encoding="utf-8")
    n = sum(len(c["criteria"]) for c in grid)
    q = sum(len(c["checklist"]) for cat in grid for c in cat["criteria"])
    print(f"Version {data['version']} : {len(grid)} catégories, {n} critères, {q} questions, "
          f"{len(regles['regles'])} règles de départage, {len(b.journal)} modifications tracées")


if __name__ == "__main__":
    main()
