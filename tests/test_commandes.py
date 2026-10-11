"""Chaque commande et chaque bouton s'exécute sans erreur avec une interaction simulée."""

import time
from types import SimpleNamespace

import discord
import pytest
from discord import app_commands

from bot.ui.limites import verifier_embed
from tests.conftest import OWNER_ID, SALON_WEBHOOK, FauxClientOllama, embed_exemple


class FausseReponse:
    def __init__(self, inter):
        self.inter = inter
        self.fait = False

    def is_done(self):
        return self.fait

    async def defer(self, **kw):
        self.fait = True

    async def send_message(self, content=None, **kw):
        self.fait = True
        self.inter.envois.append({"content": content, **kw})

    async def edit_message(self, **kw):
        self.fait = True
        self.inter.envois.append(kw)

    async def send_modal(self, modal):
        self.fait = True
        self.inter.envois.append({"modal": modal})


class FauxSuivi:
    def __init__(self, inter):
        self.inter = inter

    async def send(self, content=None, **kw):
        self.inter.envois.append({"content": content, **kw})


class FausseInteraction:
    def __init__(self, bot, user_id=OWNER_ID):
        self.client = bot
        self.user = SimpleNamespace(id=user_id, bot=False)
        self.channel_id = SALON_WEBHOOK
        self.envois = []
        self.response = FausseReponse(self)
        self.followup = FauxSuivi(self)

    async def edit_original_response(self, **kw):
        self.envois.append(kw)

    def embeds(self):
        resultat = []
        for e in self.envois:
            if e.get("embed"):
                resultat.append(e["embed"])
            resultat += e.get("embeds") or []
        return resultat

    def texte(self):
        morceaux = []
        for e in self.envois:
            morceaux.append(str(e.get("content") or ""))
        for emb in self.embeds():
            morceaux += [emb.title or "", emb.description or ""] + [
                f"{c.name} {c.value}" for c in emb.fields
            ]
        return "\n".join(morceaux)


@pytest.fixture
async def rempli(bot):
    cog = bot.get_cog("Surveillance")
    for i in range(20):
        for compte in ("abslt98", "yayaoui00"):
            await cog.traiter_message(
                (i + 1) * 10 + len(compte),
                time.time() - (20 - i) * 60,
                [embed_exemple(user=compte)],
            )
    return bot


def choix(valeur):
    return app_commands.Choice(name=valeur, value=valeur)


async def test_commandes_stats(rempli):
    bot = rempli
    stats = bot.get_cog("Stats")
    for appel in (
        lambda i: stats.estimation.callback(stats, i, 6),
        lambda i: stats.stats.callback(stats, i, choix("7j")),
        lambda i: stats.graphique_cmd.callback(stats, i, choix("gems"), choix("7j")),
        lambda i: stats.drops.callback(stats, i, "abslt98", "Common", choix("tout")),
        lambda i: stats.comparer.callback(stats, i, None),
        lambda i: stats.export.callback(stats, i, None),
    ):
        inter = FausseInteraction(bot)
        await appel(inter)
        assert inter.envois, "aucune réponse"
        for e in inter.embeds():
            assert verifier_embed(e) == []
        assert "Oups" not in inter.texte()
    inter = FausseInteraction(bot)
    await stats.drops.callback(stats, inter, "inconnu", None, None)
    assert "pas dans la liste" in inter.texte()


async def test_commande_resume_et_boutons(rempli):
    bot = rempli
    resumes = bot.get_cog("Resumes")
    inter = FausseInteraction(bot)
    await resumes.resume.callback(resumes, inter, None)
    assert "abslt98" in inter.texte()
    for bouton in (
        "bouton_actualiser",
        "bouton_copiable",
        "bouton_stats",
        "bouton_estimation",
        "bouton_graphique",
    ):
        inter = FausseInteraction(bot)
        await getattr(resumes, bouton)(inter)
        assert inter.envois, bouton
        assert "Oups" not in inter.texte(), bouton


async def test_panneau_proprietaire_seulement(bot):
    cog = bot.get_cog("Parametres")
    inter = FausseInteraction(bot)
    await cog.ouvrir_panneau(inter)
    assert inter.envois[0]["view"] is not None
    intrus = FausseInteraction(bot, user_id=999)
    await cog.ouvrir_panneau(intrus)
    assert "réservés au propriétaire" in intrus.texte()


async def test_navigation_panneau(bot):
    from bot.ui.panneau import VueAccueil

    vue = VueAccueil(bot, OWNER_ID)
    await vue.preparer()
    menu = next(c for c in vue.children if isinstance(c, discord.ui.Select))
    for categorie in ("comptes", "temps", "infos", "apparence", "alertes", "ia", "osint"):
        inter = FausseInteraction(bot)
        menu._values = [categorie]  # simule le choix dans le menu
        await menu.callback(inter)
        page = inter.envois[-1]["view"]
        assert page is not None and verifier_embed(inter.envois[-1]["embed"]) == []
        # Chaque bouton oui/non de la page s'enregistre tout de suite
        for item in page.children:
            if (
                isinstance(item, discord.ui.Button)
                and item.label
                and item.label.endswith((": oui", ": non"))
            ):
                avant = dict(bot.reglages)
                await item.callback(FausseInteraction(bot))
                assert dict(bot.reglages) != avant, item.label


async def test_ia_commandes(bot):
    cog = bot.get_cog("IA")
    cog.moteur.client = FauxClientOllama(reponses=[{"message": {"content": "Bonjour <@123> !"}}])
    inter = FausseInteraction(bot)
    await cog.ia.callback(cog, inter, "salut")
    assert "Bonjour" in inter.texte()
    assert inter.envois[-1]["allowed_mentions"].users is False
    assert len(await bot.db.historique_ia(SALON_WEBHOOK, 10)) == 2
    await cog.nouvelle_conversation(FausseInteraction(bot))
    assert await bot.db.historique_ia(SALON_WEBHOOK, 10) == []

    cog.moteur.client = FauxClientOllama(eteint=True)
    inter = FausseInteraction(bot)
    await cog.ia.callback(cog, inter, "salut")
    assert "Ollama ne répond pas" in inter.texte()

    intrus = FausseInteraction(bot, user_id=999)
    await cog.ia.callback(cog, intrus, "salut")
    assert "pas autorisé" in intrus.texte()

    cog.moteur.client = FauxClientOllama()
    inter = FausseInteraction(bot)
    await cog.ia_generer.callback(cog, inter, choix("annonce"), "tournoi")
    assert "ok" in inter.texte()
    inter = FausseInteraction(bot)
    await cog.ia_statut.callback(cog, inter)
    assert "Ollama OK" in inter.texte()
    inter = FausseInteraction(bot)
    await cog.tester(inter)
    assert "fonctionne" in inter.texte()


async def test_objectifs_et_aide(rempli):
    bot = rempli
    obj = bot.get_cog("Objectifs")
    inter = FausseInteraction(bot)
    await obj.ajouter.callback(obj, inter, "abslt98", choix("gems"), 100_000)
    assert "Objectif ajouté" in inter.texte()
    inter = FausseInteraction(bot)
    await obj.liste.callback(obj, inter)
    assert "▰" in inter.texte() or "▱" in inter.texte()
    general = bot.get_cog("General")
    inter = FausseInteraction(bot)
    await general.aide.callback(general, inter)
    assert "Tekkit Watch" in inter.texte()


async def test_osint_journal_et_image(bot):
    import io

    from PIL import Image

    cog = bot.get_cog("OSINT")
    inter = FausseInteraction(bot)
    await cog.afficher_journal(inter)
    assert "Aucune recherche" in inter.texte()

    tampon = io.BytesIO()
    Image.new("RGB", (10, 10)).save(tampon, format="PNG")
    fichier = SimpleNamespace(
        content_type="image/png", size=len(tampon.getvalue()), filename="moi.png"
    )

    async def lire():
        return tampon.getvalue()

    fichier.read = lire
    inter = FausseInteraction(bot)
    await cog.image.callback(cog, inter, fichier)
    assert "Métadonnées" in inter.texte()
    assert "Premier usage" in inter.texte()  # avertissement légal la première fois
    inter2 = FausseInteraction(bot)
    await cog.image.callback(cog, inter2, fichier)
    assert "Premier usage" not in inter2.texte()  # mais pas les fois suivantes
