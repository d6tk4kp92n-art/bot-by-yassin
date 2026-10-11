"""Commandes générales : /aide et /sync."""

from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from bot.config import VERSION
from bot.ui.couleurs import BLEU
from bot.ui.embeds import embed_succes
from bot.ui.vues import VueBase, repondre

if TYPE_CHECKING:
    from bot.main import TekkitBot

AVERTISSEMENT_OSINT = (
    "⚖️ **Avertissement légal** : les outils OSINT sont réservés à un usage **personnel, défensif et légal** "
    "(RGPD, droit belge). Ils ne servent qu'à analyser des **infrastructures** (domaines, IP, liens), des "
    "**entreprises** (données publiques BCE) et **tes propres données**. Aucune recherche sur des personnes "
    "privées. Tu restes responsable de l'usage que tu en fais."
)

AIDE: dict[str, tuple[str, str, str]] = {
    "accueil": (
        "🏠",
        "Accueil",
        (
            "**Tekkit Watch** surveille tes comptes Roblox en AFK grâce au webhook *Tekkit | Rewards Logger*.\n\n"
            "Choisis une catégorie dans le menu ci-dessous pour voir les commandes.\n\n"
            "Pour commencer : `/resume` pour voir l'état du farm, `/parametres` pour tout régler."
        ),
    ),
    "surveillance": (
        "👀",
        "Surveillance",
        (
            "Le bot lit chaque message du webhook et t'alerte automatiquement :\n"
            "• 🔴 **disparition** d'un compte après X minutes (une seule mention), 🟢 message à son retour\n"
            "• 🚨 **zone** : si un compte quitte la zone Safe (et quand il y revient)\n"
            "• 🎁 **drop rare** à partir de la rareté choisie\n"
            "• ⚠️ **anomalies** : missions lentes, gains en chute, compte bloqué\n\n"
            "`/pause` · met en pause ou relance toutes les alertes (propriétaire)"
        ),
    ),
    "resumes": (
        "📋",
        "Résumés et stats",
        (
            "`/resume` ou `/résumé` · résumé du farm (avec boutons 🔄 📋 📈 🔮 📊 ⚙️)\n"
            "`/estimation heures:` · gains attendus au rythme des 30 dernières minutes\n"
            "`/stats periode:` · totaux, moyennes/h, disponibilité, meilleure heure, records\n"
            "`/graphique type: periode:` · courbe par compte en image\n"
            "`/drops` · historique des objets rares (filtres : compte, rareté, période)\n"
            "`/comparer` · comparaison des comptes côte à côte\n"
            "`/export` · export CSV pour Excel\n\n"
            "Rapports automatiques chaque jour et chaque dimanche (heure réglable)."
        ),
    ),
    "objectifs": (
        "🎯",
        "Objectifs",
        (
            "`/objectif ajouter compte: type: valeur:` · ex. 100 000 gems\n"
            "`/objectif liste` · progression et date estimée\n"
            "`/objectif supprimer numero:`\n\n"
            "Tu es mentionné quand un objectif est atteint."
        ),
    ),
    "ia": (
        "🤖",
        "IA locale",
        (
            "IA **gratuite** qui tourne sur ton PC avec Ollama : rien n'est envoyé sur internet.\n\n"
            "`/ia question:` · discute avec l'IA, elle connaît tes vraies stats\n"
            "`/ia-generer type: sujet:` · annonce, règles du serveur, description, idées...\n"
            "`/ia-statut` · Ollama allumé ? modèle chargé ? RAM utilisée ?\n\n"
            "Le modèle se décharge tout seul après quelques minutes pour ne pas faire ramer Roblox."
        ),
    ),
    "osint": (
        "🛡️",
        "OSINT",
        (
            "`/osint domaine` · WHOIS, DNS, certificat SSL, archive.org\n"
            "`/osint ip` · pays, fournisseur, ASN\n"
            "`/osint lien` · analyse d'un lien avant de cliquer 🟢🟠🔴\n"
            "`/osint entreprise` · données publiques de la BCE/KBO\n"
            "`/osint motdepasse` · ton mot de passe a-t-il fuité ? (il ne quitte jamais ton PC)\n"
            "`/osint image` · métadonnées EXIF + version nettoyée\n\n" + AVERTISSEMENT_OSINT
        ),
    ),
    "admin": (
        "⚙️",
        "Réglages",
        (
            "`/parametres` · panneau complet : comptes, temps, infos, apparence, alertes, IA, OSINT\n"
            "`/parametres importer:` · restaure une sauvegarde de réglages\n"
            "`/sync` · resynchronise les commandes slash si elles n'apparaissent pas"
        ),
    ),
}


def embed_aide(cle: str) -> discord.Embed:
    emoji, titre, texte = AIDE[cle]
    e = discord.Embed(title=f"{emoji} Aide · {titre}", description=texte, color=BLEU)
    e.set_footer(text=f"Tekkit Watch v{VERSION}")
    return e


class VueAide(VueBase):
    def __init__(self) -> None:
        super().__init__(timeout=600)
        menu: discord.ui.Select = discord.ui.Select(
            placeholder="📚 Choisis une catégorie…",
            options=[
                discord.SelectOption(label=t, value=k, emoji=e) for k, (e, t, _) in AIDE.items()
            ],
        )

        async def choisir(interaction: discord.Interaction) -> None:
            await interaction.response.edit_message(embed=embed_aide(menu.values[0]), view=self)

        menu.callback = choisir  # type: ignore[method-assign]
        self.add_item(menu)


class General(commands.Cog):
    def __init__(self, bot: TekkitBot) -> None:
        self.bot = bot

    @app_commands.command(name="aide", description="Liste des commandes et explications")
    async def aide(self, interaction: discord.Interaction) -> None:
        await repondre(interaction, embed=embed_aide("accueil"), view=VueAide())

    @app_commands.command(
        name="sync", description="Resynchronise les commandes slash (propriétaire)"
    )
    @app_commands.describe(partout="Aussi sur tous les serveurs (peut prendre jusqu'à 1 h)")
    async def sync(self, interaction: discord.Interaction, partout: bool = False) -> None:
        if not self.bot.est_proprietaire(interaction.user):
            raise app_commands.CheckFailure(
                "🔒 Cette commande est réservée au propriétaire du bot."
            )
        await interaction.response.defer(ephemeral=True, thinking=True)
        n = await self.bot.synchroniser_commandes(global_=partout)
        await repondre(interaction, embed=embed_succes(f"{n} commandes synchronisées."))


async def setup(bot: TekkitBot) -> None:
    await bot.add_cog(General(bot))
