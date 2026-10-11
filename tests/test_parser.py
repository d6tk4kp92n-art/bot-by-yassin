from bot.parser import (
    Drop,
    lire_drops,
    lire_duree,
    lire_embed_dict,
    lire_embeds,
    lire_nombre,
    lire_objet,
    meme_compte,
    trouver_compte,
    zone_est_safe,
)
from tests.conftest import champ, embed_exemple


def test_embed_exemple_lu_correctement(embed):
    m = lire_embed_dict(embed, 123, 1000.0)
    assert m is not None
    assert m.compte == "yayaoui00"
    assert m.gold == 3851
    assert m.xp == 1442
    assert m.gems_total == 37807
    assert m.gold_total == 81508
    assert m.level == 31
    assert m.prestige == 3
    assert m.duree_s == 64
    assert m.difficulte == "Easy"
    assert m.zone == "Safe"
    assert m.est_safe is True
    assert m.drops == [
        Drop("Enhanced Metabolism", "Common", 1),
        Drop("Lucky", "Common", 1),
    ]


def test_unsafe_n_est_pas_safe():
    m = lire_embed_dict(embed_exemple(zone="Unsafe"), 1, 0)
    assert m is not None
    assert m.zone == "Unsafe"
    assert m.est_safe is False
    assert zone_est_safe("SAFE") is True
    assert zone_est_safe("  safe ") is True
    assert zone_est_safe("Not Safe") is False
    assert zone_est_safe("") is None
    assert zone_est_safe(None) is None


def test_nombres_avec_points_et_virgules():
    m = lire_embed_dict(embed_exemple(gold_drop="3.851", gems="1.037.807"), 1, 0)
    assert m is not None
    assert m.gold == 3851
    assert m.gems_total == 1037807
    assert lire_nombre("81,508") == 81508
    assert lire_nombre("abc") is None
    assert lire_nombre(None) is None


def test_champs_manquants_ne_plantent_pas():
    # Seulement le User
    m = lire_embed_dict({"fields": [champ("User:", "abslt98")]}, 5, 0)
    assert m is not None
    assert m.compte == "abslt98"
    assert m.gold is None and m.xp is None and m.zone is None and m.drops == []
    assert m.est_safe is None
    # Pas de User -> pas une mission
    assert lire_embed_dict({"fields": [champ("Drops:", "Gold: 5")]}, 5, 0) is None
    # Embed vide / cassé
    assert lire_embed_dict({}, 5, 0) is None
    assert lire_embed_dict({"fields": None}, 5, 0) is None
    assert lire_embed_dict({"fields": ["n'importe quoi", 42]}, 5, 0) is None
    assert lire_embed_dict({"fields": [{"name": None, "value": None}]}, 5, 0) is None
    # Valeurs non numériques
    m = lire_embed_dict(
        {"fields": [champ("User:", "x"), champ("Player Stats:", "Level: ???\nGems:")]}, 5, 0
    )
    assert m is not None and m.level is None and m.gems_total is None


def test_usernames_proches():
    assert not meme_compte("Bob", "Bob2")
    assert not meme_compte("Bob2", "Bob")
    assert meme_compte("bob", "BOB ")
    assert trouver_compte("Bob2", ["Bob"]) is None
    assert trouver_compte("bob", ["Bob", "Bob2"]) == "Bob"
    assert trouver_compte("Bob2", ["Bob", "Bob2"]) == "Bob2"
    assert trouver_compte(None, ["Bob"]) is None


def test_durees():
    assert lire_duree("01:04") == 64
    assert lire_duree("1:02:03") == 3723
    assert lire_duree("1m 4s") == 64
    assert lire_duree("45") == 45
    assert lire_duree("") is None
    assert lire_duree("aa:bb") is None


def test_objets_et_quantites():
    assert lire_objet("Lucky (Common)") == Drop("Lucky", "Common", 1)
    assert lire_objet("- Titan Core (Legendary) x3") == Drop("Titan Core", "Legendary", 3)
    assert lire_objet("x2 Blade (Rare)") == Drop("Blade", "Rare", 2)
    assert lire_objet("Gold: 3,851") is None
    gold, xp, gems, objets = lire_drops("```\nGold: 10\nXP: 20\nGems: 3\nA (Mythical)\n```")
    assert (gold, xp, gems) == (10, 20, 3)
    assert objets == [Drop("A", "Mythical", 1)]


def test_premier_embed_valide_utilise():
    m = lire_embeds([{"title": "autre"}, embed_exemple(user="abslt98")], 9, 0)
    assert m is not None and m.compte == "abslt98"
    assert lire_embeds([], 9, 0) is None


def test_bloc_code_avec_langage():
    e = {"fields": [{"name": "User:", "value": "```yaml\nabslt98\n```"}]}
    m = lire_embed_dict(e, 1, 0)
    assert m is not None and m.compte == "abslt98"
