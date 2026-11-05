"""Serveur de l'application : API FastAPI au-dessus de `audit_ergo`, et interface React compilée (`web/dist`).

Il n'écoute que sur ce poste (127.0.0.1) : aucun collègue du réseau ne peut ouvrir l'application ni les audits.
"""

# Identité de l'application (contrat du portail : route /health, options --port / --no-browser / --version)
APP_ID = "audit-ergo"
APP_NOM = "Audit ergonomique"
VERSION = "1.0.0"
PORT_DEFAUT = 8501
