"""Résumés automatiques et à la demande, boutons du résumé, rapports quotidien/hebdomadaire."""

from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import TYPE_CHECKING, Any

import discord
from discord import app_commands
from discord.ext import commands, tasks

from bot.calculs import records_battus
from bot.config import FORMATS_RESUME, FUSEAU
from bot.ui.embeds import embed_erreur, embed_info, embed_rapport, embed_resume, texte_copiable
from bot.ui.vues import VueResume, repondre

if TYPE_CHECKING:
    from bot.main import TekkitBot

log = logging.getLogger("tekkit.resumes")

CHOIX_FORMAT = [app_commands.Choice(name=v, value=k) for k, v in FORMATS_RESUME.items()]


def heure_rapport(texte: str) -> tuple[int, int]:
    """« 21:00 » -> (21, 0). Valeur par défaut si invalide."""
    try:
        h, m = texte.strip().split(":")
        h_i, m_i = int(h), int(m)
        if 0 <= h_i <= 23 and 0 <= m_i <= 59:
            return h_i, m_i
    except (ValueError, AttributeError):
        pass
    return 21, 0


class Resumes(commands.Cog):
    def __init__(self, bot: TekkitBot) -> None:
        self.bot = bot
        self._dernier_envoi = 0.0

    async def cog_load(self) -> None:
        self.boucle_resume.start()
        self.boucle_rapports.start()

    async def cog_unload(self) -> None:
        self.boucle_resume.cancel()
        self.boucle_rapports.cancel()

    # ------------------------------------------------------------ construction

    async def construire(self, format_: str | None = None) -> discord.Embed:
        etats = await self.bot.services.etat_comptes()
        return embed_resume(etats, self.bot.reglages, pause=self.bot.moteur.pause, format_=format_)

    def vue(self) -> discord.ui.View | None:
        return VueResume() if self.bot.reglages["resume_boutons"] else None

    async def envoyer_resume(self, salon: Any) -> discord.Message | None:
        """Envoie le résumé dans un salon (et supprime l'ancien si demandé)."""
        embed = await self.construire()
        contenu = f"<@{self.bot.config.owner_id}>" if self.bot.reglages["resume_ping"] else None
        message = await salon.send(content=contenu, embed=embed, view=self.vue())
        ancien = self.bot.reglages["_dernier_resume"]
        if self.bot.reglages["resume_supprimer_ancien"] and isinstance(ancien, list) and len(ancien) == 2:
            await self._supprimer(int(ancien[0]), int(ancien[1]))
        await self.bot.reglages.definir("_dernier_resume", [message.channel.id, message.id])
        return message

    async def _supprimer(self, salon_id: int, message_id: int) -> None:
        salon = self.bot.get_channel(salon_id)
        if salon is None or not hasattr(salon, "get_partial_message"):
            return
        try:
            await salon.get_partial_message(message_id).delete()
        except discord.HTTPException:
            pass  # déjà supprimé ou plus de droits : pas grave

    # ------------------------------------------------------------ résumé automatique

    @tasks.loop(seconds=30)
    async def boucle_resume(self) -> None:
        try:
            r = self.bot.reglages
            if not r["resume_auto"]:
                return
            intervalle = max(1, min(60, int(r["resume_intervalle_min"]))) * 60
            if time.time() - self._dernier_envoi < intervalle:
                return
            salon = self.bot.salon_resumes()
            if salon is None:
                return
            self._dernier_envoi = time.time()
            await self.envoyer_resume(salon)
        except Exception:
            log.exception("Erreur pendant l'envoi du résumé automatique")

    @boucle_resume.before_loop
    async def avant_resume(self) -> None:
        await self.bot.wait_until_ready()
        # Premier résumé après un intervalle complet (laisse le temps aux comptes d'apparaître)
        self._dernier_envoi = time.time()

    # ------------------------------------------------------------ commandes

    async def _commande_resume(self, interaction: discord.Interaction, format_: app_commands.Choice[str] | None) -> None:
        await interaction.response.defer(thinking=True)
        embed = await self.construire(format_.value if format_ else None)
        await interaction.followup.send(embed=embed, view=self.vue() or discord.utils.MISSING)

    @app_commands.command(name="resume", description="Affiche le résumé du farm de tous les comptes")
    @app_commands.describe(format="Format d'affichage (par défaut : celui des paramètres)")
    @app_commands.choices(format=CHOIX_FORMAT)
    async def resume(self, interaction: discord.Interaction, format: app_commands.Choice[str] | None = None) -> None:
        await self._commande_resume(interaction, format)

    @app_commands.command(name="résumé", description="Affiche le résumé du farm de tous les comptes")
    @app_commands.describe(format="Format d'affichage (par défaut : celui des paramètres)")
    @app_commands.choices(format=CHOIX_FORMAT)
    async def resume_accent(self, interaction: discord.Interaction, format: app_commands.Choice[str] | None = None) -> None:
        await self._commande_resume(interaction, format)

    # ------------------------------------------------------------ boutons (appelés par VueResume)

    async def bouton_actualiser(self, interaction: discord.Interaction) -> None:
        embed = await self.construire()
        await interaction.response.edit_message(embed=embed, view=self.vue())

    async def bouton_copiable(self, interaction: discord.Interaction) -> None:
        etats = await self.bot.services.etat_comptes()
        await repondre(interaction, embed=embed_info("📋 Résumé copiable", texte_copiable(etats, self.bot.reglages)))

    async def bouton_stats(self, interaction: discord.Interaction) -> None:
        cog = self.bot.get_cog("Stats")
        if cog is None:
            await repondre(interaction, embed=embed_erreur("Le module des stats n'est pas disponible."))
            return
        await cog.repondre_stats(interaction, "session")  # type: ignore[attr-defined]

    async def bouton_estimation(self, interaction: discord.Interaction) -> None:
        cog = self.bot.get_cog("Stats")
        if cog is None:
            await repondre(interaction, embed=embed_erreur("Le module des stats n'est pas disponible."))
            return
        await cog.repondre_estimation(interaction, float(self.bot.reglages["estimation_heures"]))  # type: ignore[attr-defined]

    async def bouton_graphique(self, interaction: discord.Interaction) -> None:
        cog = self.bot.get_cog("Stats")
        if cog is None:
            await repondre(interaction, embed=embed_erreur("Le module des stats n'est pas disponible."))
            return
        await cog.repondre_graphique(interaction, "gold", "aujourdhui")  # type: ignore[attr-defined]

    # ------------------------------------------------------------ rapports automatiques

    async def construire_rapport(self, hebdo: bool) -> discord.Embed:
        maintenant = time.time()
        periode = "7j" if hebdo else "aujourdhui"
        debut, _ = await self.bot.services.bornes(periode, maintenant)
        stats = await self.bot.services.stats(periode, maintenant)
        records: list[str] = []
        for nom in self.bot.reglages["comptes"]:
            pendant = await self.bot.db.missions(compte=nom, debut=debut, fin=maintenant)
            avant = await self.bot.db.missions(compte=nom, fin=debut - 0.001)
            records += records_battus(nom, pendant, avant)
        titre = "🗓️ Rapport de la semaine" if hebdo else "🌙 Rapport du jour"
        return embed_rapport(titre, stats, records, self.bot.reglages["raretes"], debut)

    async def envoyer_rapport(self, hebdo: bool) -> None:
        salon = self.bot.salon_resumes()
        if salon is None:
            return
        embed = await self.construire_rapport(hebdo)
        fichier = None
        stats_cog = self.bot.get_cog("Stats")
        if stats_cog is not None:
            fichier = await stats_cog.fichier_graphique("gold", "7j" if hebdo else "aujourdhui")  # type: ignore[attr-defined]
        if fichier is not None:
            embed.set_image(url=f"attachment://{fichier.filename}")
            await salon.send(embed=embed, file=fichier)
        else:
            await salon.send(embed=embed)

    @tasks.loop(minutes=1)
    async def boucle_rapports(self) -> None:
        try:
            r = self.bot.reglages
            maintenant = datetime.now(FUSEAU)
            h, m = heure_rapport(str(r["rapport_heure"]))
            if (maintenant.hour, maintenant.minute) < (h, m):
                return
            jour = maintenant.date().isoformat()
            if r["rapport_quotidien"] and r["_dernier_rapport_jour"] != jour:
                await self.bot.reglages.definir("_dernier_rapport_jour", jour)
                await self.envoyer_rapport(hebdo=False)
            semaine = f"{maintenant.isocalendar().year}-S{maintenant.isocalendar().week}"
            if r["rapport_hebdo"] and maintenant.weekday() == 6 and r["_dernier_rapport_semaine"] != semaine:
                await self.bot.reglages.definir("_dernier_rapport_semaine", semaine)
                await self.envoyer_rapport(hebdo=True)
        except Exception:
            log.exception("Erreur pendant l'envoi des rapports")

    @boucle_rapports.before_loop
    async def avant_rapports(self) -> None:
        await self.bot.wait_until_ready()
        # Au premier démarrage, ne pas envoyer immédiatement le rapport d'une journée déjà passée
        maintenant = datetime.now(FUSEAU)
        h, m = heure_rapport(str(self.bot.reglages["rapport_heure"]))
        if (maintenant.hour, maintenant.minute) >= (h, m) and self.bot.reglages["_dernier_rapport_jour"] is None:
            await self.bot.reglages.definir("_dernier_rapport_jour", maintenant.date().isoformat())


async def setup(bot: TekkitBot) -> None:
    await bot.add_cog(Resumes(bot))
