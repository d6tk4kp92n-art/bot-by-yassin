import pytest

from bot.calculs import (
    date_atteinte,
    detecter_anomalies,
    est_rare,
    estimer,
    formater_duree,
    gains,
    normaliser_rarete,
    progression,
    rang_rarete,
    rythme,
    stats_compte,
    taux_par_heure,
    temps_actif,
)
from bot.parser import Drop, Mission


def missions_regulieres(debut: float, n: int, pas: float = 60, gold: int = 3000, **kw) -> list[Mission]:
    return [
        Mission(message_id=i, compte="a", horodatage=debut + i * pas, gold=gold, xp=1000,
                gems_total=1000 + i * 10, duree_s=60, **kw)
        for i in range(n)
    ]


def test_estimation_180000_gold_par_heure_avec_historique():
    # 1 mission par minute depuis 1 heure, 3000 gold chacune
    ms = missions_regulieres(-3600, 90)  # de -3600 à +1740
    r = rythme(ms, maintenant=1800)
    assert r is not None
    assert r.gold_h == pytest.approx(180_000, rel=0.01)
    assert r.missions_h == pytest.approx(60, rel=0.01)
    assert r.gems_h == pytest.approx(600, rel=0.02)
    e = estimer(r, 2)
    assert e.gold == pytest.approx(360_000, rel=0.01)


def test_estimation_180000_debut_de_farm():
    ms = missions_regulieres(0, 30)
    r = rythme(ms, maintenant=1800)
    assert r is not None
    assert r.gold_h == pytest.approx(180_000, rel=0.05)


def test_pas_d_estimation_avant_2_minutes():
    ms = missions_regulieres(0, 2)  # missions à 0 et 60 s
    assert rythme(ms, maintenant=100) is None
    assert rythme([], maintenant=100) is None
    assert taux_par_heure([(0, 5)], 119) is None
    assert taux_par_heure([(0, 5), (60, 5), (120, 5)], 120) is not None


def test_compte_deconnecte_rythme_baisse():
    # Plus aucune mission depuis 25 min : le rythme doit tomber
    ms = missions_regulieres(-3600, 65)  # dernière à +240
    r = rythme(ms, maintenant=1800)
    assert r is not None and r.gold_h < 180_000 / 3


def test_raretes():
    assert normaliser_rarete("mythical") == "Mythic"
    assert normaliser_rarete("RARE") == "Rare"
    assert normaliser_rarete("bidule") is None
    assert rang_rarete("Common") == 0
    assert est_rare("Legendary", "Legendary")
    assert est_rare("Mythical", "Legendary")
    assert not est_rare("Epic", "Legendary")
    assert not est_rare("Inconnu", "Common")


def test_gains_et_objets():
    ms = missions_regulieres(0, 5)
    ms[0].drops = [Drop("A", "Common"), Drop("B", "Mythical", 2)]
    g = gains(ms)
    assert g.missions == 5 and g.gold == 15000 and g.xp == 5000
    assert g.gems == 40
    assert g.objets["Common"] == 1 and g.objets["Mythic"] == 2
    assert g.duree_moyenne_s == 60


def test_temps_actif_et_disponibilite():
    # missions toutes les minutes pendant 10 min, puis pause de 20 min, puis 10 min
    ts = [i * 60 for i in range(11)] + [1800 + i * 60 for i in range(11)]
    assert temps_actif(ts, seuil_s=180) == pytest.approx(1200)
    ms = [Mission(message_id=i, compte="a", horodatage=t, gold=100) for i, t in enumerate(ts)]
    s = stats_compte("a", ms, debut=0, fin=2400, seuil_absence_s=180)
    assert s.disponibilite == pytest.approx(50.0)
    assert s.par_heure(s.gains.gold) == pytest.approx(2200 * 3)
    assert s.meilleure_heure is not None


def test_anomalie_mission_lente():
    ms = missions_regulieres(0, 10)
    ms[-1].duree_s = 200
    types = {a.type for a in detecter_anomalies(ms)}
    assert "lent" in types
    assert detecter_anomalies(missions_regulieres(0, 10)) == []


def test_anomalie_chute_de_gains():
    ms = missions_regulieres(0, 20)
    for m in ms[-5:]:
        m.gold = 500
    assert "chute" in {a.type for a in detecter_anomalies(ms)}


def test_anomalie_compte_bloque():
    ms = missions_regulieres(0, 6)
    for m in ms:
        m.gold_total = 50_000
        m.gems_total = 100
        m.level = 5
    assert "bloque" in {a.type for a in detecter_anomalies(ms)}


def test_objectifs():
    assert progression(50, 0, 100) == 0.5
    assert progression(150, 0, 100) == 1.0
    assert date_atteinte(50, 100, 25, 0) == pytest.approx(2 * 3600)
    assert date_atteinte(50, 100, 0, 0) is None
    assert date_atteinte(100, 100, 0, 7) == 7


def test_formater_duree():
    assert formater_duree(64) == "1 min 04 s"
    assert formater_duree(5) == "5 s"
    assert formater_duree(3723) == "1 h 02 min"
    assert formater_duree(None) == "—"


def test_formater_nombre():
    from bot.calculs import formater_nombre

    assert formater_nombre(37807) == "37 807"
    assert formater_nombre(12) == "12"
    assert formater_nombre(None) == "—"


def test_bornes_periode():
    from datetime import datetime

    from bot.calculs import bornes_periode
    from bot.config import FUSEAU

    midi = datetime(2026, 7, 1, 12, 0, tzinfo=FUSEAU).timestamp()
    debut, fin = bornes_periode("aujourdhui", midi, demarrage=0)
    assert fin - debut == 12 * 3600
    assert bornes_periode("session", 100, 40) == (40, 100)
    assert bornes_periode("7j", 10 * 86400, 0) == (3 * 86400, 10 * 86400)
    assert bornes_periode("tout", 100, 40, premiere=5) == (5, 100)


def test_records_battus():
    from bot.calculs import records_battus

    avant = [Mission(message_id=i, compte="a", horodatage=i * 60, gold=1000, duree_s=70) for i in range(10)]
    periode = [Mission(message_id=100 + i, compte="a", horodatage=86400 * 2 + i * 60, gold=1500, duree_s=60)
               for i in range(20)]
    records = records_battus("a", periode, avant)
    assert len(records) == 3
    assert records_battus("a", periode, []) == []
    assert records_battus("a", avant, periode) == []
