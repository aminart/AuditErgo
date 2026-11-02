"""Tâches longues (analyse par l'IA, rédaction du rapport) exécutées en arrière-plan, avec leur progression.

Le modèle local traite un constat à la fois : une relecture peut durer plusieurs minutes. L'interface lance la
tâche, puis interroge régulièrement son état (`GET /api/taches/{id}`) pour afficher la progression.
"""
import threading
import traceback
import uuid
from dataclasses import dataclass, field


@dataclass
class Tache:
    id: str
    nom: str
    etat: str = "en_cours"  # en_cours, terminee, erreur
    fait: int = 0
    total: int = 0
    resultat: object = None
    erreur: str = ""
    detail: str = ""

    def progression(self, fait, total):
        self.fait, self.total = fait, total

    def vue(self):
        return {"id": self.id, "nom": self.nom, "etat": self.etat, "fait": self.fait, "total": self.total,
                "erreur": self.erreur, "resultat": self.resultat if self.etat == "terminee" else None}


@dataclass
class Taches:
    taches: dict = field(default_factory=dict)
    verrou: threading.Lock = field(default_factory=threading.Lock)

    def lancer(self, nom, fonction):
        """Exécute `fonction(tache)` dans un fil séparé ; sa valeur de retour devient `tache.resultat`."""
        tache = Tache(id=uuid.uuid4().hex, nom=nom)
        with self.verrou:
            self.taches[tache.id] = tache

        def executer():
            try:
                tache.resultat = fonction(tache)
                tache.etat = "terminee"
            except Exception as e:  # noqa: BLE001 : l'erreur est rendue à l'interface
                tache.erreur = str(e) or type(e).__name__
                tache.detail = traceback.format_exc()
                tache.etat = "erreur"

        threading.Thread(target=executer, daemon=True, name=f"tache-{nom}").start()
        return tache

    def lire(self, id_):
        return self.taches.get(id_)
