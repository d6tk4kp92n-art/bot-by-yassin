"""IA : Ollama simulé. File d'attente, outils, secours, erreurs gentilles."""

import asyncio
import json
import time

import pytest

from bot.ia_moteur import (
    IATropLente,
    ModeleAbsent,
    OllamaAbsent,
    _ErreurHTTP,
    _nettoyer,
    parametres_mode,
)
from tests.conftest import OWNER_ID, FauxClientOllama, embed_exemple


def reponse(texte="ok", outils=None):
    message = {"role": "assistant", "content": texte}
    if outils:
        message["tool_calls"] = [{"function": {"name": n, "arguments": a}} for n, a in outils]
    return {"message": message, "done": True}


@pytest.fixture
def moteur(bot):
    return bot.get_cog("IA").moteur


async def remplir(bot, n=10):
    cog = bot.get_cog("Surveillance")
    for i in range(n):
        await cog.traiter_message(
            9000 + i, time.time() - (n - i) * 60, [embed_exemple(user="abslt98")]
        )


async def test_une_seule_generation_a_la_fois(moteur):
    moteur.client = FauxClientOllama(
        reponses=[reponse("a"), reponse("b"), reponse("c")], lenteur=0.05
    )
    positions = []

    async def attente(p):
        positions.append(p)

    resultats = await asyncio.gather(
        *(moteur.repondre(f"q{i}", sur_attente=attente) for i in range(3))
    )
    assert sorted(r.texte for r in resultats) == ["a", "b", "c"]
    assert moteur.client.max_en_cours == 1  # jamais deux générations en même temps
    assert sorted(positions) == [1, 2]  # les 2 dernières ont attendu leur tour
    assert moteur.en_attente == 0


async def test_annulation_pendant_l_attente_ne_bloque_pas_la_file(moteur):
    moteur.client = FauxClientOllama(lenteur=0.1)
    premiere = asyncio.create_task(moteur.repondre("1"))
    await asyncio.sleep(0.01)
    deuxieme = asyncio.create_task(moteur.repondre("2"))
    await asyncio.sleep(0.01)
    deuxieme.cancel()
    await premiere
    assert moteur.en_attente == 0
    assert (await moteur.repondre("3")).texte == "ok"


async def test_outils_renvoient_les_vraies_donnees(bot, moteur):
    await remplir(bot, 10)
    moteur.client = FauxClientOllama(
        reponses=[
            reponse("", outils=[("obtenir_stats", {"compte": "abslt98", "periode": "7j"})]),
            reponse("Tu as gagné 38 510 gold."),
        ]
    )
    r = await moteur.repondre("combien de gold ?")
    assert r.texte == "Tu as gagné 38 510 gold."
    assert r.outils == ["obtenir_stats"]
    premier, second = moteur.client.appels
    assert "tools" in premier and len(premier["tools"]) == 4
    message_outil = second["messages"][-1]
    assert message_outil["role"] == "tool"
    donnees = json.loads(message_outil["content"])
    stats = donnees["stats"][0]
    assert stats["compte"] == "abslt98" and stats["missions"] == 10 and stats["gold"] == 38510


async def test_chaque_outil_fonctionne(bot, moteur):
    await remplir(bot, 5)
    outils = moteur.outils
    etat = await outils.executer("obtenir_etat_comptes", {})
    assert {c["compte"] for c in etat["comptes"]} == {"abslt98", "yayaoui00"}
    assert (
        await outils.executer(
            "obtenir_drops", '{"compte": "abslt98", "rarete_min": "Common", "periode": "tout"}'
        )
    )["nombre"] == 10
    estimation = await outils.executer("obtenir_estimation", {"heures": 2})
    assert estimation["heures"] == 2
    assert "erreur" in await outils.executer(
        "obtenir_stats", {"compte": "inconnu", "periode": "tout"}
    )
    assert "erreur" in await outils.executer("outil_bidon", {})
    assert (await outils.executer("obtenir_stats", {"periode": "n'importe quoi"}))[
        "periode"
    ] == "Aujourd'hui"


async def test_secours_si_le_modele_ne_gere_pas_les_outils(bot, moteur):
    await remplir(bot, 3)
    moteur.client = FauxClientOllama(
        reponses=[
            _ErreurHTTP(400, "registry.ollama.ai/library/petit:1b does not support tools"),
            reponse("Voici l'analyse."),
        ]
    )
    r = await moteur.repondre("analyse mon farm")
    assert r.secours is True and r.texte == "Voici l'analyse."
    dernier = moteur.client.appels[-1]
    assert "tools" not in dernier
    assert "abslt98" in dernier["messages"][-1]["content"]  # les chiffres sont injectés


async def test_ollama_absent_message_d_aide_et_surveillance_active(bot, moteur):
    moteur.client = FauxClientOllama(eteint=True)
    with pytest.raises(OllamaAbsent) as exc:
        await moteur.repondre("salut")
    assert "ollama.com/download" in str(exc.value)
    assert "surveillance" in str(exc.value)
    statut = await moteur.statut()
    assert statut.joignable is False
    # La surveillance continue normalement
    cog = bot.get_cog("Surveillance")
    assert await cog.traiter_message(1, time.time(), [embed_exemple()]) is True
    await cog.boucle()  # la boucle tourne sans erreur malgré Ollama éteint
    assert bot.moteur.etat("yayaoui00").derniere_vue is not None


async def test_modele_absent_donne_la_commande(moteur):
    moteur.client = FauxClientOllama(reponses=[_ErreurHTTP(404, "model 'qwen3.5:4b' not found")])
    with pytest.raises(ModeleAbsent) as exc:
        await moteur.repondre("salut")
    assert "ollama pull qwen3.5:4b" in str(exc.value)


async def test_trop_lent(moteur):
    moteur.client = FauxClientOllama(reponses=[IATropLente(150)])
    with pytest.raises(IATropLente) as exc:
        await moteur.repondre("salut")
    assert "150 s" in str(exc.value)


async def test_options_economie_de_ressources(bot, moteur):
    moteur.client = FauxClientOllama()
    await moteur.repondre("salut")
    corps = moteur.client.appels[0]
    assert corps["keep_alive"] == "5m"
    assert corps["options"]["num_ctx"] == 4096
    assert corps["options"]["num_predict"] <= 500
    assert corps["stream"] is False and corps["think"] is False
    assert parametres_mode("leger", 16)["num_thread"] == 4
    assert parametres_mode("equilibre", 16)["num_thread"] == 8
    await bot.reglages.definir("ia_keep_alive_min", 2)
    await moteur.repondre("salut")
    assert moteur.client.appels[-1]["keep_alive"] == "2m"


async def test_acces_et_limite(bot, moteur):
    assert moteur.autorise(OWNER_ID, OWNER_ID)
    assert not moteur.autorise(42, OWNER_ID)
    await bot.reglages.definir("ia_utilisateurs", [42])
    assert moteur.autorise(42, OWNER_ID)
    await bot.reglages.definir("ia_limite_minute", 2)
    assert not moteur.limite_atteinte(42, 1000)
    assert not moteur.limite_atteinte(42, 1001)
    assert moteur.limite_atteinte(42, 1002)
    assert not moteur.limite_atteinte(42, 1070)  # une minute plus tard


async def test_statut_modele_charge(moteur):
    moteur.client = FauxClientOllama()
    s = await moteur.statut()
    assert s.joignable and s.modele_installe and s.charge and s.ram_octets == 3 * 1024**3


async def test_historique_et_generation(moteur):
    moteur.client = FauxClientOllama(
        reponses=[reponse("<think>hmm</think>Réponse"), reponse("Annonce !")]
    )
    r = await moteur.repondre("et maintenant ?", historique=[{"role": "user", "content": "avant"}])
    assert r.texte == "Réponse"
    assert moteur.client.appels[0]["messages"][1] == {"role": "user", "content": "avant"}
    g = await moteur.generer("annonce", "tournoi samedi")
    assert g.texte == "Annonce !"
    assert "tournoi samedi" in moteur.client.appels[-1]["messages"][-1]["content"]
    assert _nettoyer("").startswith("🤔")
