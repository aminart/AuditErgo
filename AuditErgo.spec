# Recette PyInstaller de AuditErgo.exe (workflow « Build Windows exe », ou : pyinstaller --noconfirm AuditErgo.spec).
# L'interface est livrée compilée (web/dist) : pas besoin de Node.js pour fabriquer l'exe.
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules

# Version : fichier VERSION (source unique), embarqué et affiché dans Propriétés > Détails sous Windows
# (cette ressource demande les modules Windows de PyInstaller).
VERSION = Path("VERSION").read_text(encoding="utf-8").strip()
try:
    from PyInstaller.utils.win32.versioninfo import (
        FixedFileInfo, StringFileInfo, StringStruct, StringTable, VarFileInfo, VarStruct, VSVersionInfo,
    )
except ImportError:  # hors Windows : pas de ressource de version, la fabrication continue
    version_info = None
else:
    _nombres = tuple(int(partie) for partie in VERSION.split("-")[0].split(".")) + (0,)
    version_info = VSVersionInfo(
        ffi=FixedFileInfo(filevers=_nombres[:4], prodvers=_nombres[:4]),
        kids=[
            StringFileInfo([StringTable("040C04B0", [
                StringStruct("ProductName", "AuditErgo"),
                StringStruct("FileDescription", "AuditErgo, audits ergonomiques assistés"),
                StringStruct("ProductVersion", VERSION),
                StringStruct("FileVersion", VERSION),
                StringStruct("OriginalFilename", "AuditErgo.exe"),
            ])]),
            VarFileInfo([VarStruct("Translation", [0x040C, 1200])]),
        ],
    )

datas = [
    ("VERSION", "."),
    ("web/dist", "web/dist"),
    ("template", "template"),
    ("referentiel/referentiel.json", "referentiel"),
]
binaries = []
hiddenimports = collect_submodules("uvicorn") + collect_submodules("audit_ergo") + collect_submodules("serveur")

# python-docx et openpyxl livrent des fichiers de données (modèles Word par défaut, etc.)
for paquet in ("docx", "openpyxl"):
    paquet_datas, paquet_binaries, paquet_hidden = collect_all(paquet)
    datas += paquet_datas
    binaries += paquet_binaries
    hiddenimports += paquet_hidden

a = Analysis(
    ["lanceur.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "matplotlib", "IPython", "pytest"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="AuditErgo",
    version=version_info,
    console=True,
    upx=False,
)
