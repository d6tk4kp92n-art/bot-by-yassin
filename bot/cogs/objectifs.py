"""Objectifs : /objectif ajouter|liste|supprimer, et ping quand un objectif est atteint."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from bot.calculs import date_atteinte, progression
from bot.cogs.stats import autocomplete_compte
from bot.database import Objectif
from bot.moteur_surveillance import Alerte
from bot.parser import Mission
from bot.services import TYPES_OBJECTIF
from bot.ui.embeds import embed_erreur, embed_info, embed_succes, ligne_objectif
from bot.ui.format import nombre
from bot.ui.vues import envoyer_pages, repondre

if TYPE_CHECKING:
    from bot.main import TekkitBot

log = logging.getLogger("tekkit.objectifs")

CHOIX_TYPE = [app_commands.Choice(name=v, value=k) for k, v in TYPES_OBJECTIF.items()]


class Objectifs(commands.GroupCog, group_name="objectif", group_description="Objectifs de farm"):
    def __init__(self, bot: TekkitBot) -> None:
        self.bot = bot
        super().__init__()

    async def _ligne(self, o: Objectif) -> str:
        actuel = await self.bot.services.valeur_actuelle(o.compte, o.type)
        fraction = progression(actuel or 0, o.valeur_depart, o.valeur_cible)
        quand = None
        if not o.atteint_le and actuel is not None:
            taux = await self.bot.services.taux_objectif(o.compte, o.type)
            quand = date_atteinte(actuel, o.valeur_cible, taux, time.time())
        return ligne_objectif(o, actuel, fraction, quand)

    @app_commands.command(name="ajouter", description="Ajoute un objectif (ex. 100 000 gems)")
    @app_commands.describe(
        compte="Compte concerné", type="Type d'objectif", valeur="Valeur à atteindre"
    )
    @app_commands.choices(type=CHOIX_TYPE)
    @app_commands.autocomplete(compte=autocomplete_compte)
    async def ajouter(
        self,
        interaction: discord.Interaction,
        compte: str,
        type: app_commands.Choice[str],
        valeur: app_commands.Range[int, 1, 2_000_000_000],
    ) -> None:
        nom = next(
            (c for c in self.bot.reglages["comptes"] if c.casefold() == compte.strip().casefold()),
            None,
        )
        if nom is None:
            await repondre(
                interaction, embed=embed_erreur(f"Le compte « {compte} » n'est pas surveillé.")
            )
            return
        actuel = await self.bot.services.valeur_actuelle(nom, type.value) or 0
        if actuel >= valeur:
            await repondre(
                interaction,
                embed=embed_info(
                    "🎉 Déjà atteint", f"**{nom}** a déjà {nombre(actuel)} ({type.name})."
                ),
            )
            return
        identifiant = await self.bot.db.ajouter_objectif(nom, type.value, int(valeur), int(actuel))
        objectif = Objectif(
            identifiant, nom, type.value, int(valeur), int(actuel), time.time(), None
        )
        await repondre(
            interaction, embed=embed_succes(await self._ligne(objectif), "🎯 Objectif ajouté")
        )

    @app_commands.command(name="liste", description="Affiche les objectifs et leur progression")
    async def liste(self, interaction: discord.Interaction) -> None:
        objectifs = await self.bot.db.objectifs()
        if not objectifs:
            await repondre(
                interaction,
                embed=embed_info(
                    "🎯 Objectifs", "Aucun objectif. Ajoute-en un avec `/objectif ajouter`."
                ),
            )
            return
        lignes = [await self._ligne(o) for o in objectifs]
        pages = [
            embed_info("🎯 Objectifs", "\n\n".join(lignes[i : i + 6]))
            for i in range(0, len(lignes), 6)
        ]
        await envoyer_pages(interaction, pages)

    @app_commands.command(name="supprimer", description="Supprime un objectif")
    @app_commands.describe(numero="Numéro de l'objectif (voir /objectif liste)")
    async def supprimer(self, interaction: discord.Interaction, numero: int) -> None:
        if not self.bot.est_proprietaire(interaction.user):
            raise app_commands.CheckFailure("🔒 Seul le propriétaire peut supprimer un objectif.")
        if await self.bot.db.supprimer_objectif(numero):
            await repondre(interaction, embed=embed_succes(f"Objectif #{numero} supprimé."))
        else:
            await repondre(interaction, embed=embed_erreur(f"Aucun objectif #{numero}."))

    @commands.Cog.listener()
    async def on_mission_tekkit(self, mission: Mission) -> None:
        """À chaque mission : vérifie si un objectif du compte vient d'être atteint."""
        try:
            for o in await self.bot.db.objectifs(actifs_seulement=True):
                if o.compte.casefold() != mission.compte.casefold():
                    continue
                actuel = await self.bot.services.valeur_actuelle(o.compte, o.type)
                if actuel is None or actuel < o.valeur_cible:
                    continue
                maintenant = time.time()
                await self.bot.db.objectif_atteint(o.id, maintenant)
                surveillance = self.bot.get_cog("Surveillance")
                if surveillance is not None:
                    alerte = Alerte(
                        type="objectif",
                        compte=o.compte,
                        titre=f"🎉 Objectif atteint pour {o.compte} !",
                        texte=f"{TYPES_OBJECTIF.get(o.type, o.type)} : **{nombre(actuel)}** / {nombre(o.valeur_cible)}",
                        ping=bool(self.bot.reglages["ping_objectif"]),
                        couleur=0x57F287,
                        horodatage=maintenant,
                    )
                    await surveillance.envoyer_alerte(alerte)  # type: ignore[attr-defined]
        except Exception:
            log.exception("Erreur pendant la vérification des objectifs")


async def setup(bot: TekkitBot) -> None:
    await bot.add_cog(Objectifs(bot))
