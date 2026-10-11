import pytest

from bot.database import Database
from bot.parser import lire_embed_dict
from tests.conftest import embed_exemple


@pytest.fixture
async def db(tmp_path):
    base = Database(tmp_path / "test.db")
    await base.connecter()
    yield base
    await base.fermer()


async def test_message_modifie_pas_compte_deux_fois(db):
    m = lire_embed_dict(embed_exemple(), 111, 1000)
    assert await db.ajouter_mission(m) is True
    # Le webhook modifie le message : même ID -> ignoré
    m2 = lire_embed_dict(embed_exemple(gold_drop="9,999"), 111, 1005)
    assert await db.ajouter_mission(m2) is False
    missions = await db.missions(avec_drops=True)
    assert len(missions) == 1
    assert missions[0].gold == 3851
    assert len(missions[0].drops) == 2
    assert len(await db.drops()) == 2


async def test_filtres_compte_et_periode(db):
    for i in range(5):
        await db.ajouter_mission(lire_embed_dict(embed_exemple(user="Bob"), i, 100 + i))
        await db.ajouter_mission(lire_embed_dict(embed_exemple(user="Bob2"), 100 + i, 100 + i))
    assert len(await db.missions(compte="bob")) == 5
    assert len(await db.missions(compte="Bob2")) == 5
    assert len(await db.missions(debut=102, fin=103)) == 4
    dernieres = await db.dernieres_missions("Bob", 2)
    assert [m.horodatage for m in dernieres] == [103, 104]
    assert (await db.derniere_mission_avant("Bob", 102)).horodatage == 101
    assert await db.comptes_vus() == ["Bob", "Bob2"]
    assert len(await db.drops(compte="Bob", raretes=["common"])) == 10
    assert await db.drops(raretes=[]) == []


async def test_reglages_survivent_au_redemarrage(tmp_path):
    chemin = tmp_path / "r.db"
    a = Database(chemin)
    await a.connecter()
    await a.ecrire_reglage("delai_absence_min", 7)
    await a.ecrire_reglage("comptes", ["x", "y"])
    await a.ecrire_reglage("_interne", 1)
    await a.fermer()
    b = Database(chemin)
    await b.connecter()
    r = await b.lire_reglages()
    assert r["delai_absence_min"] == 7 and r["comptes"] == ["x", "y"]
    await b.effacer_reglages()
    assert await b.lire_reglages() == {"_interne": 1}
    assert await b.version_schema() == 1
    await b.fermer()


async def test_objectifs_ia_osint_evenements(db):
    oid = await db.ajouter_objectif("a", "gems", 100, 10)
    assert len(await db.objectifs(actifs_seulement=True)) == 1
    await db.objectif_atteint(oid, 5)
    assert await db.objectifs(actifs_seulement=True) == []
    assert await db.supprimer_objectif(oid)

    await db.ajouter_message_ia(1, "user", "salut")
    await db.ajouter_message_ia(1, "assistant", "bonjour")
    await db.ajouter_message_ia(2, "user", "autre salon")
    assert await db.historique_ia(1, 10) == [
        {"role": "user", "content": "salut"},
        {"role": "assistant", "content": "bonjour"},
    ]
    await db.effacer_conversation_ia(1)
    assert await db.historique_ia(1, 10) == []

    await db.journaliser_osint(42, "domaine", "example.com", "ok")
    assert (await db.journal_osint())[0][:3] == (42, "domaine", "example.com")

    await db.ajouter_evenement("a", "zone", "test", 10)
    assert (await db.evenements("a"))[0].texte == "test"


async def test_purge(db):
    await db.ajouter_mission(lire_embed_dict(embed_exemple(), 1, 0))
    await db.ajouter_mission(lire_embed_dict(embed_exemple(), 2, 100 * 86400))
    supprimees = await db.purger(90, maintenant=100 * 86400)
    assert supprimees == 1
    assert await db.nombre_missions() == 1
    assert len(await db.drops()) == 2
