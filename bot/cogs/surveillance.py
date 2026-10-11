"""Surveillance (PRIORITÉ ABSOLUE) : lit le webhook, détecte disparitions, zones, drops, anomalies.

Chaque étape est protégée par try/except : la boucle ne s'arrête JAMAIS.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands, tasks

from bot.calculs import detecter_anomalies
from bot.moteur_surveillance import Alerte
from bot.parser import Mission, lire_embeds, trouver_compte
from bot.ui.embeds import embed_alerte, embed_succes

if TYPE_CHECKING:
    from bot.main import TekkitBot

log = logging.getLogger("tekkit.surveillance")

RATTRAPAGE_MAX = 500  # messages relus au démarrage pour rattraper les missions manquées


class Surveillance(commands.Cog):
    def __init__(self, bot: TekkitBot) -> None:
        self.bot = bot
        self._rattrapage_fait = False

    async def cog_load(self) -> None:
        self.boucle.start()
        self.entretien.start()

    async def cog_unload(self) -> None:
        self.boucle.cancel()
        self.entretien.cancel()

    # ------------------------------------------------------------ lecture du webhook

    def _est_salon_webhook(self, salon_id: int) -> bool:
        return salon_id == self.bot.config.webhook_channel_id

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if not self._est_salon_webhook(message.channel.id) or not message.embeds:
            return
        if self.bot.user is not None and message.author.id == self.bot.user.id:
            return  # nos propres alertes et résumés
        await self.traiter_message(
            message.id, message.created_at.timestamp(), [e.to_dict() for e in message.embeds]
        )

    @commands.Cog.listener()
    async def on_raw_message_edit(self, payload: discord.RawMessageUpdateEvent) -> None:
        """Le webhook peut modifier un message : on ne compte la mission qu'une seule fois."""
        if not self._est_salon_webhook(payload.channel_id):
            return
        try:
            if await self.bot.db.mission_existe(payload.message_id):
                return
            embeds = payload.data.get("embeds") or []
            horodatage = discord.utils.snowflake_time(payload.message_id).timestamp()
            await self.traiter_message(payload.message_id, horodatage, embeds)
        except Exception:
            log.exception("Erreur en lisant un message modifié")

    async def traiter_message(
        self, message_id: int, horodatage: float, embeds: list[dict], alerter: bool = True
    ) -> bool:
        """Lit un message du webhook et l'enregistre. Renvoie True si c'est une NOUVELLE mission."""
        try:
            mission = lire_embeds(embeds, message_id, horodatage)
            if mission is None:
                return False
            # On garde l'orthographe configurée du compte (match EXACT du username)
            compte = trouver_compte(mission.compte, self.bot.reglages["comptes"])
            if compte is not None:
                mission.compte = compte
            if not await self.bot.db.ajouter_mission(mission):
                return False  # déjà compté (message modifié ou relu)
        except Exception:
            log.exception("Erreur en enregistrant une mission")
            return False
        if compte is not None:
            await self._apres_mission(mission, alerter)
        return True

    async def _apres_mission(self, mission: Mission, alerter: bool) -> None:
        """Alertes et événements liés à une nouvelle mission (isolés : ne plantent jamais)."""
        maintenant = time.time()
        anomalies = []
        try:
            recentes = await self.bot.db.dernieres_missions(mission.compte, 30)
            anomalies = detecter_anomalies(recentes, self.bot.reglages["sensibilite_anomalies"])
        except Exception:
            log.exception("Erreur pendant la détection d'anomalies")
        try:
            alertes = self.bot.moteur.mission_recue(
                mission, self.bot.reglages, maintenant, anomalies
            )
        except Exception:
            log.exception("Erreur dans le moteur de surveillance")
            alertes = []
        if alerter:
            for alerte in alertes:
                await self.envoyer_alerte(alerte)
        try:
            self.bot.dispatch("mission_tekkit", mission)  # pour les objectifs
        except Exception:
            log.exception("Erreur en signalant la mission aux autres modules")

    # ------------------------------------------------------------ envoi des alertes

    async def envoyer_alerte(self, alerte: Alerte) -> None:
        try:
            await self.bot.db.ajouter_evenement(
                alerte.compte, alerte.type, alerte.titre, alerte.horodatage
            )
        except Exception:
            log.exception("Impossible d'enregistrer l'événement")
        salon = self.bot.salon_alertes()
        if salon is None:
            log.warning("Alerte non envoyée (salon introuvable) : %s", alerte.titre)
            return
        contenu = f"<@{self.bot.config.owner_id}>" if alerte.ping else None
        try:
            await salon.send(content=contenu, embed=embed_alerte(alerte))
            log.info("Alerte envoyée : %s", alerte.titre)
        except discord.HTTPException as exc:
            log.warning("Impossible d'envoyer l'alerte « %s » : %s", alerte.titre, exc)

    # ------------------------------------------------------------ boucle principale

    @tasks.loop(seconds=15)
    async def boucle(self) -> None:
        try:
            self.bot.moteur.configurer(self.bot.reglages["comptes"])
            alertes = self.bot.moteur.verifier(time.time(), self.bot.reglages)
        except Exception:
            log.exception("Erreur dans la boucle de surveillance")
            return
        for alerte in alertes:
            await self.envoyer_alerte(alerte)

    @boucle.before_loop
    async def avant_boucle(self) -> None:
        await self.bot.wait_until_ready()
        await self.rattraper()

    @boucle.error
    async def erreur_boucle(self, error: BaseException) -> None:  # filet de sécurité
        log.exception("La boucle de surveillance a planté, redémarrage", exc_info=error)
        if not self.boucle.is_running():
            self.boucle.restart()

    async def rattraper(self) -> None:
        """Au démarrage : relit les messages postés pendant que le bot était éteint (sans alerter),
        puis reprend la dernière activité connue de chaque compte."""
        if self._rattrapage_fait:
            return
        self._rattrapage_fait = True
        nouvelles = 0
        try:
            salon = self.bot.get_channel(self.bot.config.webhook_channel_id)
            if salon is not None and hasattr(salon, "history"):
                manques: list[discord.Message] = []
                # Du plus récent au plus ancien, jusqu'au premier message déjà enregistré
                async for message in salon.history(limit=RATTRAPAGE_MAX):
                    if not message.embeds:
                        continue
                    if await self.bot.db.mission_existe(message.id):
                        break
                    manques.append(message)
                for message in reversed(manques):  # puis dans l'ordre chronologique
                    ok = await self.traiter_message(
                        message.id,
                        message.created_at.timestamp(),
                        [e.to_dict() for e in message.embeds],
                        alerter=False,
                    )
                    nouvelles += int(ok)
        except Exception:
            log.exception("Rattrapage de l'historique impossible")
        try:
            for compte in self.bot.reglages["comptes"]:
                derniere = await self.bot.db.derniere_mission(compte)
                if derniere is not None:
                    self.bot.moteur.restaurer(compte, derniere.horodatage, derniere.zone)
        except Exception:
            log.exception("Impossible de restaurer l'état des comptes")
        if nouvelles:
            log.info("Rattrapage : %d missions manquées enregistrées", nouvelles)

    @tasks.loop(hours=6)
    async def entretien(self) -> None:
        try:
            n = await self.bot.db.purger(int(self.bot.reglages["purge_jours"]))
            if n:
                log.info("Purge : %d anciennes missions supprimées", n)
        except Exception:
            log.exception("Erreur pendant la purge")
        try:
            await self.bot.mettre_a_jour_statut()
        except Exception:
            log.exception("Erreur pendant la mise à jour du statut")

    @entretien.before_loop
    async def avant_entretien(self) -> None:
        await self.bot.wait_until_ready()

    # ------------------------------------------------------------ pause

    async def definir_pause(self, pause: bool) -> None:
        """Met la surveillance en pause / la relance (réglage enregistré immédiatement)."""
        await self.bot.reglages.definir("surveillance_active", not pause)
        if pause:
            self.bot.moteur.mettre_en_pause()
        else:
            self.bot.moteur.reprendre(time.time())
        await self.bot.mettre_a_jour_statut()

    @app_commands.command(
        name="pause", description="Met en pause ou relance toutes les alertes de surveillance"
    )
    async def pause(self, interaction: discord.Interaction) -> None:
        if not self.bot.est_proprietaire(interaction.user):
            raise app_commands.CheckFailure(
                "🔒 Cette commande est réservée au propriétaire du bot."
            )
        nouvelle_pause = not self.bot.moteur.pause
        await self.definir_pause(nouvelle_pause)
        delai = self.bot.reglages["delai_absence_min"]
        texte = (
            "⏸️ Surveillance **en pause** : plus aucune alerte."
            if nouvelle_pause
            else f"▶️ Surveillance **relancée** : chaque compte a {delai} min pour réapparaître."
        )
        await interaction.response.send_message(embed=embed_succes(texte), ephemeral=True)


async def setup(bot: TekkitBot) -> None:
    await bot.add_cog(Surveillance(bot))
