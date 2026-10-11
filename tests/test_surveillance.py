import pytest

from bot.calculs import Anomalie
from bot.config import defauts
from bot.database import Database
from bot.moteur_surveillance import MoteurSurveillance
from bot.parser import Drop, Mission
from bot.reglages import Reglages


def mission(
    compte: str, t: float, zone: str = "Safe", drops=None, mid: int | None = None
) -> Mission:
    return Mission(
        message_id=mid or int(t),
        compte=compte,
        horodatage=t,
        gold=100,
        zone=zone,
        drops=drops or [],
    )


@pytest.fixture
def reglages():
    r = defauts()
    r["comptes"] = ["abslt98", "yayaoui00"]
    r["delai_absence_min"] = 3
    return r


@pytest.fixture
def moteur(reglages):
    m = MoteurSurveillance(demarrage=0)
    m.configurer(reglages["comptes"])
    return m


def test_attend_x_minutes_au_demarrage(moteur, reglages):
    assert moteur.verifier(100, reglages) == []
    assert moteur.verifier(179, reglages) == []
    alertes = moteur.verifier(180, reglages)
    assert {a.compte for a in alertes} == {"abslt98", "yayaoui00"}
    assert all(a.type == "disparition" and a.ping for a in alertes)


def test_ping_une_seule_fois_puis_retour(moteur, reglages):
    moteur.mission_recue(mission("abslt98", 10), reglages, 10)
    moteur.mission_recue(mission("yayaoui00", 10), reglages, 10)
    assert moteur.verifier(189, reglages) == []
    alertes = moteur.verifier(190, reglages)
    assert len(alertes) == 2
    # Une seule fois !
    assert moteur.verifier(500, reglages) == []
    assert moteur.verifier(5000, reglages) == []
    # Retour signalé
    retour = moteur.mission_recue(mission("abslt98", 6000), reglages, 6000)
    assert [a.type for a in retour] == ["retour"]
    assert retour[0].ping is False  # par défaut, retour sans ping
    assert moteur.mission_recue(mission("abslt98", 6060), reglages, 6060) == []
    # Il peut de nouveau disparaître (et être signalé une nouvelle fois)
    assert [a.compte for a in moteur.verifier(6060 + 180, reglages)] == ["abslt98"]


def test_retour_avec_ping_et_sans_message(moteur, reglages):
    moteur.verifier(180, reglages)
    reglages["ping_retour"] = True
    assert moteur.mission_recue(mission("abslt98", 200), reglages, 200)[0].ping is True
    reglages["message_retour"] = False
    assert moteur.mission_recue(mission("yayaoui00", 200), reglages, 200) == []


def test_rien_en_pause(moteur, reglages):
    moteur.mettre_en_pause()
    assert moteur.verifier(10_000, reglages) == []
    m = mission("abslt98", 50, zone="Unsafe", drops=[Drop("X", "Exotic")])
    assert moteur.mission_recue(m, reglages, 50) == []
    # À la reprise, chaque compte a de nouveau X minutes
    moteur.reprendre(20_000)
    assert moteur.verifier(20_000 + 179, reglages) == []
    assert len(moteur.verifier(20_000 + 180, reglages)) == 2


def test_surveillance_desactivee(moteur, reglages):
    reglages["surveillance_active"] = False
    assert moteur.verifier(10_000, reglages) == []


def test_alerte_zone(moteur, reglages):
    assert moteur.mission_recue(mission("abslt98", 1), reglages, 1) == []
    a = moteur.mission_recue(mission("abslt98", 2, zone="Unsafe"), reglages, 2)
    assert [x.type for x in a] == ["zone_quitte"]
    assert moteur.mission_recue(mission("abslt98", 3, zone="Unsafe"), reglages, 3) == []
    a = moteur.mission_recue(mission("abslt98", 4, zone="SAFE"), reglages, 4)
    assert [x.type for x in a] == ["zone_retour"]


def test_drop_rare(moteur, reglages):
    reglages["rarete_min"] = "Legendary"
    assert moteur.mission_recue(mission("abslt98", 1, drops=[Drop("A", "Epic")]), reglages, 1) == []
    a = moteur.mission_recue(mission("abslt98", 2, drops=[Drop("B", "Mythical")]), reglages, 2)
    assert [x.type for x in a] == ["drop"] and "Mythic" in a[0].texte


def test_compte_non_surveille_et_usernames_proches(moteur, reglages):
    assert moteur.mission_recue(mission("abslt98x", 1, zone="Unsafe"), reglages, 1) == []
    assert moteur.etat("abslt98").derniere_vue is None


def test_anomalies_pas_repetees(moteur, reglages):
    an = [Anomalie("lent", "lent")]
    assert len(moteur.mission_recue(mission("abslt98", 1), reglages, 1, an)) == 1
    assert moteur.mission_recue(mission("abslt98", 2), reglages, 2, an) == []
    # L'anomalie disparaît puis revient bien plus tard -> nouvelle alerte
    moteur.mission_recue(mission("abslt98", 4000), reglages, 4000, [])
    assert len(moteur.mission_recue(mission("abslt98", 4001), reglages, 4001, an)) == 1


def test_configurer_ajout_retrait(moteur):
    moteur.configurer(["abslt98", "nouveau"])
    assert sorted(moteur.comptes) == ["abslt98", "nouveau"]


async def test_reglages_persistants(tmp_path):
    db = Database(tmp_path / "x.db")
    await db.connecter()
    r = Reglages(db)
    await r.charger()
    await r.definir("delai_absence_min", 9)
    assert await r.basculer("resume_auto") is False
    await r.definir("_dernier_resume", 5)
    r2 = Reglages(db)
    await r2.charger()
    assert r2["delai_absence_min"] == 9 and r2["resume_auto"] is False
    await r2.tout_remettre_par_defaut()
    assert r2["delai_absence_min"] == 3 and r2["_dernier_resume"] == 5
    # Une valeur de mauvais type en base est ignorée
    await db.ecrire_reglage("delai_absence_min", "abc")
    await r2.charger()
    assert r2["delai_absence_min"] == 3
    assert await r2.importer({"delai_absence_min": 4, "inconnu": 1, "_dernier_resume": 9}) == [
        "delai_absence_min"
    ]
    await db.fermer()


async def test_import_reglages_filtre_les_comptes(tmp_path):
    db = Database(tmp_path / "i.db")
    await db.connecter()
    r = Reglages(db)
    await r.charger()
    comptes = ["ok_1", "a", "pas valide!", "ok_1", *[f"compte{i}" for i in range(20)]]
    await r.importer({"comptes": comptes})
    assert r["comptes"][0] == "ok_1" and len(r["comptes"]) == 10
    await db.fermer()
