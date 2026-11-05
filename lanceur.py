"""Point d'entrée de AuditErgo.exe (PyInstaller) : identique à « python -m serveur ».

AuditErgo.exe [--port 8501] [--no-browser] [--version]
"""
from serveur.__main__ import main

if __name__ == "__main__":
    main()
