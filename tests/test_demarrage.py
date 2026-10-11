"""Le bot démarre (sans se connecter à Discord) : base, réglages, tous les modules, commandes."""

import logging

import pytest
from discord import app_commands

from bot.config import Config
from bot.main import COGS, FiltreSecrets, TekkitBot

FAUX_TOKEN = "MTIzNDU2Nzg5MDEyMzQ1Njc4.faux.token_de_test_qui_ne_marche_pas"


@pytest.fixture
async def bot(tmp_path):
    config = Config(token=FAUX_TOKEN, owner_id=111, webhook_channel_id=222, virustotal_key="vt-secret-123456")
    b = TekkitBot(config, chemin_base=tmp_path / "test.db")
    async with b:  # initialise le client sans se connecter à Discord
        await b.preparer()
        yield b
        for nom in list(b.extensions):
            await b.unload_extension(nom)


async def test_tous_les_modules_se_chargent(bot):
    assert bot.cogs_en_erreur == {}
    assert set(bot.extensions) == set(COGS)
    for nom in ("Surveillance", "Resumes", "Stats", "Objectifs", "Parametres", "General", "IA", "OSINT"):
        assert bot.get_cog(nom) is not None, nom


async def test_commandes_slash_enregistrees(bot):
    noms = {c.name for c in bot.tree.get_commands()}
    attendues = {
        "resume", "résumé", "estimation", "stats", "graphique", "drops", "comparer", "export",
        "objectif", "parametres", "aide", "sync", "pause", "ia", "ia-generer", "ia-statut", "osint",
    }
    assert attendues <= noms
    osint = bot.tree.get_command("osint")
    assert isinstance(osint, app_commands.Group)
    assert {c.name for c in osint.commands} == {"domaine", "ip", "lien", "entreprise", "motdepasse", "image"}
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
    assert c.owner_id == 1 and c.webhook_channel_id == 2 and c.ollama_url == "http://localhost:11434"
    assert c.virustotal_key is None
