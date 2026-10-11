from bot.ui.format import barre, decouper_message, nombre, tronquer, ts


def test_formats_simples():
    assert nombre(37807) == "37 807"
    assert ts(1000.7) == "<t:1000:R>"
    assert ts(None) == "jamais"
    assert tronquer("abcdef", 4) == "abc…"
    assert barre(0.5, 4).startswith("▰▰▱▱")


def test_decoupage_court():
    assert decouper_message("salut") == ["salut"]
    assert decouper_message("   ") == []


def test_decoupage_respecte_la_limite_et_les_blocs_de_code():
    code = "```python\n" + "\n".join(f"print({i})  # ligne de code" for i in range(200)) + "\n```"
    texte = "Voici le code :\n" + code + "\nFin."
    morceaux = decouper_message(texte, 500)
    assert len(morceaux) > 1
    for m in morceaux:
        assert len(m) <= 500
        # Chaque morceau a un nombre pair de ``` (blocs bien fermés)
        assert m.count("```") % 2 == 0, m
    assert morceaux[1].startswith("```python")
    assert "print(199)" in "".join(morceaux)
    assert morceaux[-1].endswith("Fin.")


def test_decoupage_ligne_geante():
    morceaux = decouper_message("x" * 5000, 2000)
    assert all(len(m) <= 2000 for m in morceaux)
    assert "".join(morceaux) == "x" * 5000
