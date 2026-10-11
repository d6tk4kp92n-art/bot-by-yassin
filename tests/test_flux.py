"""Flux complet : webhook -> base -> alertes -> résumé / stats / objectifs / export."""

import time
from types import SimpleNamespace

from bot.cogs.stats import generer_csv
from bot.parser import lire_embed_dict
from bot.ui.limites import verifier_embed
from tests.conftest import OWNER_ID, SALON_WEBHOOK, embed_exemple


class FauxSalon:
    def __init__(self):
        self.id = SALON_WEBHOOK
        self.envois = []

    async def send(self, content=None, **kwargs):
        self.envois.append(SimpleNamespace(content=content, **kwargs))
        return SimpleNamespace(id=len(self.envois), channel=self)


def brancher_salon(bot):
    salon = FauxSalon()
    bot.salon_alertes = lambda: salon
    bot.salon_resumes = lambda: salon
    return salon


async def test_message_compte_une_seule_fois_meme_modifie(bot):
    cog = bot.get_cog("Surveillance")
    brancher_salon(bot)
    maintenant = time.time()
    assert await cog.traiter_message(1001, maintenant, [embed_exemple(user="YAYAOUI00")]) is True
    # Le webhook modifie le message : même ID, pas compté deux fois
    assert await cog.traiter_message(1001, maintenant, [embed_exemple(gold_drop="99")]) is False
    payload = SimpleNamespace(
        channel_id=SALON_WEBHOOK, message_id=1001, data={"embeds": [embed_exemple()]}
    )
    await cog.on_raw_message_edit(payload)
    missions = await bot.db.missions()
    assert len(missions) == 1
    assert missions[0].compte == "yayaoui00"  # orthographe configurée
    assert missions[0].gold == 3851
    # Un message d'un autre salon est ignoré
    autre = SimpleNamespace(channel_id=999, message_id=1002, data={"embeds": [embed_exemple()]})
    await cog.on_raw_message_edit(autre)
    assert await bot.db.nombre_missions() == 1


async def test_message_visible_dans_le_resume(bot):
    cog = bot.get_cog("Surveillance")
    brancher_salon(bot)
    await cog.traiter_message(2001, time.time() - 30, [embed_exemple(user="abslt98")])
    embed = await bot.get_cog("Resumes").construire()
    texte = " ".join([embed.description or ""] + [f"{c.name} {c.value}" for c in embed.fields])
    assert "abslt98" in texte and "3 851" in texte
    assert verifier_embed(embed) == []
    for format_ in ("detaille", "compact", "texte"):
        e = await bot.get_cog("Resumes").construire(format_)
        assert verifier_embed(e) == [], format_
        assert "abslt98" in str(e.to_dict())


async def test_compte_absent_un_seul_ping_puis_retour(bot):
    cog = bot.get_cog("Surveillance")
    salon = brancher_salon(bot)
    await cog.traiter_message(3001, time.time(), [embed_exemple(user="abslt98")])
    # On simule 4 minutes sans nouvelle mission pour les deux comptes
    for compte in ("abslt98", "yayaoui00"):
        etat = bot.moteur.etat(compte)
        etat.reference = time.time() - 240
        if etat.derniere_vue:
            etat.derniere_vue = time.time() - 240
    await cog.boucle()
    alertes = [e for e in salon.envois if e.embed.title and "disparu" in e.embed.title]
    assert len(alertes) == 2
    assert all(e.content == f"<@{OWNER_ID}>" for e in alertes)
    # Une seule fois
    await cog.boucle()
    await cog.boucle()
    assert len([e for e in salon.envois if "disparu" in (e.embed.title or "")]) == 2
    # Retour signalé
    await cog.traiter_message(3002, time.time(), [embed_exemple(user="abslt98")])
    assert any("de retour" in (e.embed.title or "") for e in salon.envois)
    # L'événement est enregistré pour les « changements récents »
    assert await bot.db.evenements("abslt98")


async def test_pause_coupe_les_alertes(bot):
    cog = bot.get_cog("Surveillance")
    salon = brancher_salon(bot)
    await cog.definir_pause(True)
    assert bot.reglages["surveillance_active"] is False
    for compte in ("abslt98", "yayaoui00"):
        bot.moteur.etat(compte).reference = time.time() - 10_000
    await cog.boucle()
    await cog.traiter_message(4001, time.time(), [embed_exemple(user="abslt98", zone="Unsafe")])
    assert salon.envois == []
    await cog.definir_pause(False)
    await cog.boucle()  # chaque compte a de nouveau X min : rien tout de suite
    assert salon.envois == []


async def test_zone_et_drop_rare_alertes(bot):
    cog = bot.get_cog("Surveillance")
    salon = brancher_salon(bot)
    await cog.traiter_message(5001, time.time(), [embed_exemple(user="abslt98")])
    await cog.traiter_message(5002, time.time(), [embed_exemple(user="abslt98", zone="Unsafe")])
    e = embed_exemple(user="abslt98", zone="Unsafe")
    e["fields"][3]["value"] = "```\nGold: 10\nXP: 5\nTitan Core (Mythical)\n```"
    await cog.traiter_message(5003, time.time(), [e])
    titres = [x.embed.title for x in salon.envois]
    assert any("quitté la zone Safe" in t for t in titres)
    assert any("Drop rare" in t for t in titres)


async def test_compte_non_surveille_enregistre_sans_alerte(bot):
    cog = bot.get_cog("Surveillance")
    salon = brancher_salon(bot)
    await cog.traiter_message(6001, time.time(), [embed_exemple(user="abslt98x", zone="Unsafe")])
    assert await bot.db.nombre_missions() == 1
    assert salon.envois == []


async def test_stats_estimation_graphique_export(bot):
    cog = bot.get_cog("Surveillance")
    brancher_salon(bot)
    debut = time.time() - 3600
    for i in range(60):
        e = embed_exemple(user="abslt98", gems=f"{37000 + i * 10}")
        await cog.traiter_message(7000 + i, debut + i * 60, [e])
    stats = await bot.services.stats("aujourdhui" if time.localtime().tm_hour >= 2 else "7j")
    abs_stats = next(s for s in stats if s.compte == "abslt98")
    assert abs_stats.gains.missions == 60
    estimations = await bot.services.estimations(1)
    est = next(x for x in estimations if x.nom == "abslt98")
    assert est.estimation is not None and est.estimation.missions > 0
    fichier = await bot.get_cog("Stats").fichier_graphique("gold", "7j")
    assert fichier is not None and fichier.filename.endswith(".png")
    csv_brut = generer_csv(await bot.db.missions(avec_drops=True))
    assert csv_brut.startswith(b"\xef\xbb\xbf") and b"abslt98" in csv_brut
    rapport = await bot.get_cog("Resumes").construire_rapport(hebdo=True)
    assert verifier_embed(rapport) == []


async def test_objectif_atteint_ping(bot):
    cog = bot.get_cog("Surveillance")
    salon = brancher_salon(bot)
    await cog.traiter_message(8001, time.time(), [embed_exemple(user="abslt98", gems="100")])
    await bot.db.ajouter_objectif("abslt98", "gems", 150, 100)
    await cog.traiter_message(8002, time.time(), [embed_exemple(user="abslt98", gems="160")])
    # Le dispatch de discord.py est asynchrone : on attend que l'écouteur ait tourné
    import asyncio

    for _ in range(50):
        if any("Objectif atteint" in (e.embed.title or "") for e in salon.envois):
            break
        await asyncio.sleep(0.02)
    assert any("Objectif atteint" in (e.embed.title or "") for e in salon.envois)
    assert await bot.db.objectifs(actifs_seulement=True) == []


async def test_resume_ancien_supprime_et_reglages(bot):
    salon = brancher_salon(bot)
    resumes = bot.get_cog("Resumes")
    await resumes.envoyer_resume(salon)
    assert bot.reglages["_dernier_resume"] == [SALON_WEBHOOK, 1]
    assert salon.envois[0].view is not None  # boutons persistants


async def test_parser_utilise_dans_flux(bot):
    m = lire_embed_dict(embed_exemple(), 1, 0)
    assert m is not None
