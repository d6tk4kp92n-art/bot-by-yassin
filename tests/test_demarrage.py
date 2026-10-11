"""Le bot démarre (sans se connecter à Discord) : base, réglages, tous les modules, commandes."""

import logging

import pytest
from discord import app_commands

from bot.config import Config
from bot.main import COGS, FiltreSecrets
from tests.conftest import FAUX_TOKEN


async def test_tous_les_modules_se_chargent(bot):
    assert bot.cogs_en_erreur == {}
    assert set(bot.extensions) == set(COGS)
    for nom in (
        "Surveillance",
        "Resumes",
        "Stats",
        "Objectifs",
        "Parametres",
        "General",
        "IA",
        "OSINT",
    ):
        assert bot.get_cog(nom) is not None, nom


async def test_commandes_slash_enregistrees(bot):
    noms = {c.name for c in bot.tree.get_commands()}
    attendues = {
        "resume",
        "résumé",
        "estimation",
        "stats",
        "graphique",
        "drops",
        "comparer",
        "export",
        "objectif",
        "parametres",
        "aide",
        "sync",
        "pause",
        "ia",
        "ia-generer",
        "ia-statut",
        "osint",
    }
    assert attendues <= noms
    osint = bot.tree.get_command("osint")
    assert isinstance(osint, app_commands.Group)
    assert {c.name for c in osint.commands} == {
        "domaine",
        "ip",
        "lien",
        "entreprise",
        "motdepasse",
        "image",
    }

    # Toutes les commandes respectent les limites Discord (noms ≤ 32, descriptions ≤ 100)
    def toutes(commandes):
        for c in commandes:
            yield c
            if isinstance(c, app_commands.Group):
                yield from toutes(c.commands)

    for c in toutes(bot.tree.get_commands()):
        assert 1 <= len(c.name) <= 32 and c.name == c.name.lower(), c.name
        assert 1 <= len(c.description) <= 100, c.name
        if isinstance(c, app_commands.Command):
            for p in c.parameters:
                assert len(p.description) <= 100, f"{c.name}.{p.name}"
    # La conversion en JSON (ce qui est envoyé à Discord) ne plante pas
    for c in bot.tree.get_commands():
        c.to_dict(bot.tree)


async def test_vues_persistantes_enregistrees(bot):
    ids = {item.custom_id for vue in bot.persistent_views for item in vue.children}
    assert {"tw:resume:actualiser", "tw:resume:parametres", "tw:ia:nouvelle"} <= ids


async def test_secrets_masques_dans_les_logs(caplog):
    logger = logging.getLogger("test.secrets")
    logger.addFilter(FiltreSecrets([FAUX_TOKEN]))
    with caplog.at_level(logging.INFO, logger="test.secrets"):
        logger.info("token=%s", FAUX_TOKEN)
    assert FAUX_TOKEN not in caplog.text
    assert "***" in caplog.text


def test_config_explique_ce_qui_manque(tmp_path, monkeypatch):
    for cle in ("DISCORD_TOKEN", "OWNER_ID", "WEBHOOK_CHANNEL_ID"):
        monkeypatch.delenv(cle, raising=False)
    env = tmp_path / ".env"
    env.write_text("DISCORD_TOKEN=\nOWNER_ID=abc\n", encoding="utf-8")
    with pytest.raises(ValueError, match="OWNER_ID"):
        Config.depuis_env(env)
    env.write_text("DISCORD_TOKEN=x\nOWNER_ID=1\nWEBHOOK_CHANNEL_ID=2\n", encoding="utf-8")
    monkeypatch.delenv("OWNER_ID", raising=False)
    c = Config.depuis_env(env)
    assert (
        c.owner_id == 1 and c.webhook_channel_id == 2 and c.ollama_url == "http://localhost:11434"
    )
    assert c.virustotal_key is None


async def test_sync_annonce_et_rattrapage(bot):
    """Démarrage complet simulé : sync des commandes, « Surveillance lancée », rattrapage de l'historique."""
    from datetime import UTC, datetime
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    import discord

    from tests.conftest import SALON_WEBHOOK, embed_exemple

    envois = []

    class FauxSalon:
        id = SALON_WEBHOOK
        guild = SimpleNamespace(id=1, name="Mon serveur")

        async def send(self, content=None, **kw):
            envois.append(content)

        async def history(self, limit=100):
            for i in (3, 2, 1):  # du plus récent au plus ancien, comme Discord
                yield SimpleNamespace(
                    id=500 + i,
                    created_at=datetime.fromtimestamp(1_700_000_000 + i * 60, UTC),
                    embeds=[discord.Embed.from_dict(embed_exemple(user="abslt98"))],
                )

    salon = FauxSalon()
    bot.get_channel = lambda _id: salon
    bot.tree.sync = AsyncMock(return_value=[object()] * 20)
    bot.tree.copy_global_to = lambda guild: None
    assert await bot.synchroniser_commandes() == 20

    bot.change_presence = AsyncMock()
    await bot.on_ready()
    assert any("Surveillance lancée" in (c or "") for c in envois)
    bot.change_presence.assert_awaited()
    assert "Surveille 2 comptes" in bot.change_presence.await_args.kwargs["activity"].name

    await bot.get_cog("Surveillance").rattraper()
    missions = await bot.db.missions()
    assert [m.message_id for m in missions] == [501, 502, 503]  # ordre chronologique
    assert bot.moteur.etat("abslt98").derniere_vue == missions[-1].horodatage
    # Un salon introuvable ne fait pas planter : 0 commande et un message clair dans les logs
    bot.get_channel = lambda _id: None
    bot.fetch_channel = AsyncMock(
        side_effect=discord.NotFound(SimpleNamespace(status=404, reason="x"), "inconnu")
    )
    assert await bot.synchroniser_commandes() == 0
