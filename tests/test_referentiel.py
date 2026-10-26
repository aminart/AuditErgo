def test_trouve_critere_par_code_libelle_ou_nom(ref):
    assert ref.trouver_critere("GUI-03 – Feedback immédiat (Immediate Feedback)") == "GUI-03"
    assert ref.trouver_critere("gui-03") == "GUI-03"
    assert ref.trouver_critere("Immediate Feedback") == "GUI-03"
    assert ref.trouver_critere("feedback IMMÉDIAT") == "GUI-03"
    assert ref.trouver_critere("Contrôle utilisateur et liberté") == "CTL-02"
    assert ref.trouver_critere("XYZ-99") is None
    assert ref.trouver_critere("") is None


def test_trouve_categorie(ref):
    assert ref.trouver_categorie("GUI – Guidage") == "GUI"
    assert ref.trouver_categorie("Gestion des erreurs") == "ERR"
    assert ref.trouver_categorie("Errors_Management") == "ERR"
    assert ref.trouver_categorie("Inconnue") is None


def test_codes_mentionnes(ref):
    assert ref.codes_mentionnes("ERR-01 ; WKL-05, XYZ-99") == (["ERR-01", "WKL-05"], ["XYZ-99"])
    assert ref.codes_mentionnes(None) == ([], [])


def test_referentiel_coherent(ref):
    assert len(ref.criteres) == 24
    for regle in ref.regles.values():
        assert all(cas["critere"] in ref.criteres for cas in regle["cas"])
