"""Point d'entrée du bot Tekkit Watch.

Lancement : python -m bot.main
"""

from __future__ import annotations

import logging
import sys
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

import discord
from discord import app_commands
from discord.ext import commands

from bot.config import CHEMIN_BASE, DOSSIER_LOGS, VERSION, Config
from bot.database import Database
from bot.moteur_surveillance import MoteurSurveillance
from bot.reglages import Reglages
from bot.services import Services
from bot.ui.embeds import embed_erreur
from bot.ui.vues import VueResume, repondre

log = logging.getLogger("tekkit")

COGS = [
    "bot.cogs.surveillance",  # priorité n°1 : chargé en premier
    "bot.cogs.resumes",
    "bot.cogs.stats",
    "bot.cogs.objectifs",
    "bot.cogs.parametres",
    "bot.cogs.general",
    "bot.cogs.ia",
    "bot.cogs.osint",
]


# ---------------------------------------------------------------- logs


class FiltreSecrets(logging.Filter):
    """Remplace les secrets (token, clés) par *** dans tous les logs."""

    def __init__(self, secrets: list[str]) -> None:
        super().__init__()
        self.secrets = [s for s in secrets if s and len(s) >= 6]

    def filter(self, record: logging.LogRecord) -> bool:
        if self.secrets:
            message = record.getMessage()
            nettoye = message
            for s in self.secrets:
                nettoye = nettoye.replace(s, "***")
            if nettoye != message:
                record.msg, record.args = nettoye, None
        return True


def configurer_logs(secrets: list[str], dossier: Path = DOSSIER_LOGS) -> None:
    """Logs lisibles dans la console + fichiers en rotation dans data/logs/."""
    dossier.mkdir(parents=True, exist_ok=True)
    format_ = logging.Formatter("%(asctime)s | %(levelname)-7s | %(name)s | %(message)s", "%d/%m %H:%M:%S")
    filtre = FiltreSecrets(secrets)

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(format_)
    console.addFilter(filtre)
    fichier = RotatingFileHandler(dossier / "bot.log", maxBytes=2_000_000, backupCount=5, encoding="utf-8")
    fichier.setFormatter(format_)
    fichier.addFilter(filtre)

    racine = logging.getLogger()
    racine.handlers.clear()
    racine.setLevel(logging.INFO)
    racine.addHandler(console)
    racine.addHandler(fichier)
    logging.getLogger("discord").setLevel(logging.WARNING)
    logging.getLogger("discord.gateway").setLevel(logging.WARNING)


# ---------------------------------------------------------------- bot


class Arbre(app_commands.CommandTree):
    """Arbre de commandes avec un gestionnaire d'erreurs gentil (jamais de trace Python)."""

    async def on_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
        if isinstance(error, app_commands.CheckFailure):
            texte = str(error) or "Tu n'as pas le droit d'utiliser cette commande."
        elif isinstance(error, app_commands.CommandOnCooldown):
            texte = f"Doucement 🙂 Réessaie dans {error.retry_after:.0f} s."
        else:
            original = getattr(error, "original", error)
            log.error("Erreur dans /%s", interaction.command.qualified_name if interaction.command else "?",
                      exc_info=original)
            texte = "Une erreur inattendue s'est produite. Elle a été notée dans les logs ; réessaie dans un instant."
        await repondre(interaction, embed=embed_erreur(texte))


class TekkitBot(commands.Bot):
    def __init__(self, config: Config, chemin_base: Path | str = CHEMIN_BASE) -> None:
        intents = discord.Intents.default()
        intents.message_content = True  # nécessaire pour lire les embeds du webhook
        super().__init__(
            command_prefix=commands.when_mentioned,
            intents=intents,
            tree_cls=Arbre,
            help_command=None,
            allowed_mentions=discord.AllowedMentions(everyone=False, roles=False, users=True),
        )
        self.config = config
        self.demarrage = time.time()
        self.db = Database(chemin_base)
        self.reglages = Reglages(self.db)
        self.moteur = MoteurSurveillance(self.demarrage)
        self.services = Services(self.db, self.reglages, self.moteur, self.demarrage)
        self.cogs_en_erreur: dict[str, str] = {}
        self._annonce_faite = False

    # ------------------------------------------------------------ démarrage

    async def preparer(self) -> None:
        """Base, réglages, cogs, vues persistantes. Ne demande pas de connexion à Discord."""
        await self.db.connecter()
        await self.reglages.charger()
        self.moteur.configurer(self.reglages["comptes"])
        if not self.reglages["surveillance_active"]:
            self.moteur.mettre_en_pause()
        for nom in COGS:
            try:
                await self.load_extension(nom)
            except Exception as exc:  # un module cassé ne doit pas empêcher les autres de tourner
                self.cogs_en_erreur[nom] = str(exc)
                log.exception("Impossible de charger le module %s", nom)
        self.add_view(VueResume())  # boutons du résumé : marchent après redémarrage

    async def setup_hook(self) -> None:
        await self.preparer()
        await self.synchroniser_commandes()

    async def synchroniser_commandes(self, global_: bool = False) -> int:
        """Synchronise les commandes slash sur le serveur du salon webhook (instantané)."""
        try:
            if global_:
                return len(await self.tree.sync())
            salon = self.get_channel(self.config.webhook_channel_id) or await self.fetch_channel(
                self.config.webhook_channel_id
            )
            guild = getattr(salon, "guild", None)
            if guild is None:
                raise ValueError("ce salon n'appartient à aucun serveur")
            self.tree.copy_global_to(guild=guild)
            commandes = await self.tree.sync(guild=guild)
            log.info("✅ %d commandes synchronisées sur le serveur « %s »", len(commandes), guild.name)
            return len(commandes)
        except (discord.HTTPException, ValueError) as exc:
            log.error(
                "Salon WEBHOOK_CHANNEL_ID introuvable ou inaccessible (%s). Vérifie l'ID dans .env "
                "et que le bot est bien invité sur le serveur avec accès au salon.", exc
            )
            return 0

    async def on_ready(self) -> None:
        log.info("Connecté en tant que %s (ID %s) · Tekkit Watch v%s", self.user, getattr(self.user, "id", "?"), VERSION)
        await self.mettre_a_jour_statut()
        if not self._annonce_faite:
            self._annonce_faite = True
            salon = self.salon_alertes()
            if salon is not None:
                comptes = ", ".join(f"`{c}`" for c in self.reglages["comptes"]) or "aucun"
                delai = self.reglages["delai_absence_min"]
                texte = f"✅ **Surveillance lancée** · comptes : {comptes} · alerte après {delai} min d'absence."
                if self.cogs_en_erreur:
                    texte += "\n⚠️ Modules en erreur : " + ", ".join(self.cogs_en_erreur) + " (voir data/logs)."
                try:
                    await salon.send(texte)
                except discord.HTTPException as exc:
                    log.warning("Impossible d'écrire dans le salon des alertes : %s", exc)

    async def close(self) -> None:
        await super().close()
        await self.db.fermer()

    # ------------------------------------------------------------ outils

    def est_proprietaire(self, utilisateur: discord.abc.User | int) -> bool:
        uid = utilisateur if isinstance(utilisateur, int) else utilisateur.id
        return uid == self.config.owner_id

    def _salon(self, cle: str) -> Any:
        identifiant = self.reglages[cle] or self.config.webhook_channel_id
        salon = self.get_channel(int(identifiant))
        if salon is None and identifiant != self.config.webhook_channel_id:
            salon = self.get_channel(self.config.webhook_channel_id)
        return salon

    def salon_alertes(self) -> Any:
        return self._salon("salon_alertes")

    def salon_resumes(self) -> Any:
        return self._salon("salon_resumes")

    async def mettre_a_jour_statut(self) -> None:
        n = len(self.reglages["comptes"])
        texte = f"⏸️ Surveillance en pause ({n} comptes)" if self.moteur.pause else f"👀 Surveille {n} compte{'s' if n > 1 else ''}"
        try:
            await self.change_presence(activity=discord.CustomActivity(name=texte))
        except Exception as exc:  # le statut n'est pas vital
            log.debug("Statut non mis à jour : %s", exc)


def proprietaire_seulement() -> Any:
    """Décorateur : commande réservée au propriétaire (OWNER_ID)."""

    async def verifier(interaction: discord.Interaction) -> bool:
        bot = interaction.client
        if isinstance(bot, TekkitBot) and bot.est_proprietaire(interaction.user):
            return True
        raise app_commands.CheckFailure("🔒 Cette commande est réservée au propriétaire du bot.")

    return app_commands.check(verifier)


# ---------------------------------------------------------------- lancement


def main() -> int:
    try:
        config = Config.depuis_env()
    except ValueError as exc:
        print(f"\n❌ {exc}\n")
        return 1
    configurer_logs(config.secrets())
    bot = TekkitBot(config)
    try:
        bot.run(config.token, log_handler=None)  # reconnexion automatique incluse
    except discord.LoginFailure:
        log.error("❌ Token Discord refusé. Réinitialise-le sur le portail développeur et colle-le dans .env.")
        return 1
    except discord.PrivilegedIntentsRequired:
        log.error(
            "❌ Active « MESSAGE CONTENT INTENT » sur https://discord.com/developers/applications "
            "(ton application → Bot → Privileged Gateway Intents), puis relance."
        )
        return 1
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
