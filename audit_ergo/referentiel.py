"""Chargement du référentiel et recherche des critères à partir de ce que le designer a saisi."""
import json
import re
import unicodedata
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

CHEMIN_DEFAUT = Path(__file__).resolve().parent.parent / "referentiel" / "referentiel.json"
CODE_CRITERE = re.compile(r"\b([A-Z]{3}-\d{2})\b")
CODE_CATEGORIE = re.compile(r"^\s*([A-Z]{3})\b")


def normaliser(texte):
    """Minuscules, sans accents ni ponctuation : sert à comparer des libellés saisis à la main."""
    texte = unicodedata.normalize("NFKD", str(texte)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", texte.lower()).strip()


@dataclass
class Referentiel:
    data: dict

    @classmethod
    def charger(cls, chemin=CHEMIN_DEFAUT):
        return cls(json.loads(Path(chemin).read_text(encoding="utf-8")))

    @property
    def version(self):
        return self.data["version"]

    @cached_property
    def categories(self):
        return {c["code"]: c for c in self.data["grid"]}

    @cached_property
    def criteres(self):
        return {c["code"]: {**c, "categorie": cat["code"]} for cat in self.data["grid"] for c in cat["criteria"]}

    @cached_property
    def regles(self):
        return {r["id"]: r for r in self.data["regles_departage"]["regles"]}

    @cached_property
    def _alias_criteres(self):
        alias = {}
        for code, c in self.criteres.items():
            for nom in (code, c["name"], c["label_fr"], c["id_source"]):
                alias[normaliser(nom)] = code
        return alias

    @cached_property
    def _alias_categories(self):
        alias = {}
        for code, c in self.categories.items():
            for nom in (code, c["label"], c["label_fr"], c["id_source"]):
                alias[normaliser(nom)] = code
        return alias

    def trouver_critere(self, saisie):
        """Code du critère (ex. 'GUI-03') à partir de 'GUI-03 – Feedback…', 'Immediate Feedback', etc. None si inconnu."""
        if not saisie:
            return None
        m = CODE_CRITERE.search(str(saisie))
        if m:
            return m.group(1) if m.group(1) in self.criteres else None
        return self._alias_criteres.get(normaliser(saisie))

    def trouver_categorie(self, saisie):
        if not saisie:
            return None
        m = CODE_CATEGORIE.match(str(saisie))
        if m and m.group(1) in self.categories:
            return m.group(1)
        return self._alias_categories.get(normaliser(saisie))

    def codes_mentionnes(self, saisie):
        """Tous les codes de critères cités dans un texte libre (critères secondaires). Renvoie (connus, inconnus)."""
        trouves = CODE_CRITERE.findall(str(saisie or ""))
        return [c for c in trouves if c in self.criteres], [c for c in trouves if c not in self.criteres]
