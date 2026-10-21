"""Convertit les deux CSV sources en un référentiel JSON exploitable par l'application.

Usage : python3 scripts/build_referentiel.py  (depuis le dossier audit-ergo/)
"""
import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "referentiel" / "source"
OUT = ROOT / "referentiel" / "referentiel.json"


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


def build_grid():
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


def build_frameworks():
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


if __name__ == "__main__":
    data = {"grid": build_grid(), "frameworks": build_frameworks()}
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    n = sum(len(c["criteria"]) for c in data["grid"])
    h = sum(len(f["heuristics"]) for f in data["frameworks"])
    print(f"{len(data['grid'])} catégories, {n} critères, {h} heuristiques -> {OUT}")
