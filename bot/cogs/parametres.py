"""Commande /parametres : ouvre le panneau de réglages (propriétaire uniquement)."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from bot.ui.embeds import embed_erreur, embed_succes
from bot.ui.panneau import VueAccueil
from bot.ui.vues import repondre

if TYPE_CHECKING:
    from bot.main import TekkitBot

log = logging.getLogger("tekkit.parametres")


class Parametres(commands.Cog):
    def __init__(self, bot: TekkitBot) -> None:
        self.bot = bot

    async def ouvrir_panneau(self, interaction: discord.Interaction) -> None:
        if not self.bot.est_proprietaire(interaction.user):
            await repondre(
                interaction,
                embed=embed_erreur("🔒 Les paramètres sont réservés au propriétaire du bot."),
            )
            return
        vue = VueAccueil(self.bot, interaction.user.id)
        await vue.preparer()
        await repondre(interaction, embed=vue.embed(), view=vue)

    @app_commands.command(name="parametres", description="Ouvre le panneau des réglages du bot")
    @app_commands.describe(importer="(Optionnel) fichier tekkit_reglages.json à restaurer")
    async def parametres(
        self, interaction: discord.Interaction, importer: discord.Attachment | None = None
    ) -> None:
        if importer is None:
            await self.ouvrir_panneau(interaction)
            return
        if not self.bot.est_proprietaire(interaction.user):
            await repondre(
                interaction,
                embed=embed_erreur("🔒 Les paramètres sont réservés au propriétaire du bot."),
            )
            return
        if importer.size > 100_000 or not importer.filename.lower().endswith(".json"):
            await repondre(
                interaction,
                embed=embed_erreur("Envoie le fichier `.json` créé par le bouton 💾 Exporter."),
            )
            return
        try:
            donnees = json.loads(await importer.read())
            if not isinstance(donnees, dict):
                raise ValueError("format inattendu")
        except (ValueError, discord.HTTPException):
            await repondre(
                interaction,
                embed=embed_erreur("Ce fichier n'est pas une sauvegarde de réglages valide."),
            )
            return
        acceptees = await self.bot.reglages.importer(donnees)
        self.bot.moteur.configurer(self.bot.reglages["comptes"])
        await self.bot.mettre_a_jour_statut()
        await repondre(
            interaction,
            embed=embed_succes(f"{len(acceptees)} réglages restaurés.", "📥 Réglages importés"),
        )


async def setup(bot: TekkitBot) -> None:
    await bot.add_cog(Parametres(bot))
