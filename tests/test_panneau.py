"""Toutes les vues du panneau /parametres respectent les limites Discord."""

import pytest

from bot.cogs.general import AIDE, VueAide, embed_aide
from bot.ui.limites import verifier_embed, verifier_modal, verifier_vue
from bot.ui.panneau import (
    PAGES,
    ModalCompte,
    ModalConservation,
    ModalCouleur,
    ModalIA,
    ModalTemps,
    VueAccueil,
    VueSalons,
)
from bot.ui.vues import VueConfirmation, VuePagination, VueResume
from tests.conftest import OWNER_ID


async def pire_cas(bot):
    """Réglages qui poussent les limites au maximum."""
    await bot.reglages.definir("comptes", [f"compte_tres_long_{i:02d}"[:20] for i in range(10)])
    await bot.reglages.definir("couleur", "#123456")
    await bot.reglages.definir("ia_utilisateurs", list(range(1000, 1025)))
    bot.get_cog("IA").moteur.client.modeles = [f"modele-{i}:latest" for i in range(30)]


@pytest.mark.parametrize("extreme", [False, True])
async def test_toutes_les_pages_respectent_les_limites(bot, extreme):
    if extreme:
        await pire_cas(bot)
    for classe in [VueAccueil, VueSalons, *PAGES.values()]:
        vue = classe(bot, OWNER_ID)
        await vue.preparer()
        assert verifier_vue(vue) == [], f"{classe.__name__} : {verifier_vue(vue)}"
        assert verifier_embed(vue.embed()) == [], classe.__name__
        assert len(vue.children) > 0


async def test_chaque_page_a_un_bouton_retour(bot):
    for classe in [VueSalons, *PAGES.values()]:
        vue = classe(bot, OWNER_ID)
        await vue.preparer()
        assert any(getattr(c, "label", None) == "Retour" for c in vue.children), classe.__name__


async def test_modals_respectent_les_limites(bot):
    page = VueAccueil(bot, OWNER_ID)
    for modal in (
        ModalCompte(page),
        ModalTemps(page),
        ModalIA(page),
        ModalCouleur(page),
        ModalConservation(page),
    ):
        assert verifier_modal(modal) == [], type(modal).__name__


async def test_autres_vues(bot):
    async def rien(_):
        return None

    for vue in (
        VueResume(),
        VueAide(),
        VueConfirmation(rien, OWNER_ID),
        VuePagination([embed_aide("accueil")] * 3),
    ):
        assert verifier_vue(vue) == [], type(vue).__name__
    for cle in AIDE:
        assert verifier_embed(embed_aide(cle)) == []


async def test_comptes_maximum_desactive_ajout(bot):
    await pire_cas(bot)
    vue = PAGES["comptes"](bot, OWNER_ID)
    await vue.preparer()
    ajouter = next(c for c in vue.children if getattr(c, "label", "") == "Ajouter un compte")
    assert ajouter.disabled


async def test_verificateur_detecte_les_depassements():
    import discord

    from bot.ui.limites import securiser_embed

    vue = discord.ui.View()
    vue.add_item(discord.ui.Select(options=[discord.SelectOption(label="x" * 101, value="a")]))
    assert verifier_vue(vue)
    e = discord.Embed(title="t", description="d")
    for i in range(10):
        e.add_field(name=f"c{i}", value="v" * 1100)
    assert verifier_embed(e)
    assert verifier_embed(securiser_embed(e)) == []


async def test_modal_mot_de_passe(bot):
    from bot.cogs.osint import ModalMotDePasse

    assert verifier_modal(ModalMotDePasse(bot.get_cog("OSINT"))) == []
