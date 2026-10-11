"""Commandes /osint (propriétaire uniquement, réponses éphémères, tout est journalisé)."""

from __future__ import annotations

import asyncio
import io
import logging
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from bot.cogs.general import AVERTISSEMENT_OSINT
from bot.osint_outils import HorsPerimetre, Http, Resultat, ServiceOSINT, lire_exif, nettoyer_image
from bot.ui.couleurs import BLEU, ORANGE, ROUGE, VERT
from bot.ui.embeds import embed_attention, embed_erreur, embed_info
from bot.ui.format import tronquer, ts
from bot.ui.limites import securiser_embed
from bot.ui.vues import VueBase, envoyer_pages, repondre

if TYPE_CHECKING:
    from bot.main import TekkitBot

log = logging.getLogger("tekkit.osint")

TAILLE_IMAGE_MAX = 10 * 1024 * 1024
COULEURS = {"info": BLEU, "vert": VERT, "orange": ORANGE, "rouge": ROUGE}


def embed_resultat(r: Resultat) -> discord.Embed:
    e = discord.Embed(title=r.titre, color=COULEURS.get(r.niveau, BLEU))
    for nom, valeur in r.champs:
        e.add_field(name=nom, value=tronquer(valeur or "—", 1024), inline=False)
    e.set_footer(text=f"Tekkit Watch · OSINT{' · ' + r.note if r.note else ''}")
    return securiser_embed(e)


class ModalMotDePasse(discord.ui.Modal, title="Vérifier un de MES mots de passe"):
    mot_de_passe: discord.ui.TextInput = discord.ui.TextInput(
        label="Mot de passe (jamais stocké ni envoyé)",
        placeholder="Seuls 5 caractères de son empreinte SHA-1 quittent le PC",
        min_length=1,
        max_length=256,
    )

    def __init__(self, cog: OSINT) -> None:
        super().__init__(timeout=300)
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        valeur = self.mot_de_passe.value
        try:
            resultat = await self.cog.service.mot_de_passe(valeur)
        except Exception as exc:
            # On ne journalise JAMAIS le mot de passe : seulement le type d'erreur
            log.warning("Vérification de mot de passe impossible (%s)", type(exc).__name__)
            await self.cog.journaliser(interaction, "motdepasse", "(masqué)", "erreur")
            await repondre(interaction, embed=embed_erreur("Le service Have I Been Pwned ne répond pas. Réessaie plus tard."))
            return
        finally:
            del valeur
        await self.cog.journaliser(interaction, "motdepasse", "(masqué)", "ok")
        await self.cog.envoyer(interaction, embed_resultat(resultat))

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        log.warning("Erreur dans la modal mot de passe (%s)", type(error).__name__)
        await repondre(interaction, embed=embed_erreur("Quelque chose s'est mal passé. Réessaie."))


class VueImage(VueBase):
    def __init__(self, donnees: bytes, nom: str, auteur_id: int) -> None:
        super().__init__(timeout=600)
        self.donnees = donnees
        self.nom = nom
        self.auteur_id = auteur_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.auteur_id

    @discord.ui.button(label="Renvoyer l'image nettoyée", emoji="🧼", style=discord.ButtonStyle.success)
    async def nettoyer(self, interaction: discord.Interaction, bouton: discord.ui.Button) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            propre, extension = await asyncio.to_thread(nettoyer_image, self.donnees)
        except Exception:
            log.exception("Nettoyage d'image impossible")
            await repondre(interaction, embed=embed_erreur("Impossible de nettoyer cette image."))
            return
        base = self.nom.rsplit(".", 1)[0][:50] or "image"
        fichier = discord.File(io.BytesIO(propre), filename=f"{base}_nettoyee.{extension}")
        bouton.disabled = True
        await repondre(interaction, embed=embed_info("🧼 Image nettoyée", "Plus aucune métadonnée (EXIF, GPS, XMP)."), file=fichier)
        self.donnees = b""
        self.stop()


class OSINT(commands.GroupCog, group_name="osint", group_description="Outils OSINT légaux (propriétaire)"):
    def __init__(self, bot: TekkitBot) -> None:
        self.bot = bot
        self.http = Http()
        self.service = ServiceOSINT(self.http, bot.config.virustotal_key, bot.config.urlscan_key)
        super().__init__()

    async def cog_unload(self) -> None:
        await self.http.fermer()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not self.bot.est_proprietaire(interaction.user):
            raise app_commands.CheckFailure("🔒 Les outils OSINT sont réservés au propriétaire du bot.")
        if not self.bot.reglages["osint_active"]:
            raise app_commands.CheckFailure("🛡️ Le module OSINT est désactivé (`/parametres` → 🛡️ OSINT).")
        return True

    # ------------------------------------------------------------ outils

    async def journaliser(self, interaction: discord.Interaction, commande: str, cible: str, resultat: str) -> None:
        try:
            await self.bot.db.journaliser_osint(interaction.user.id, commande, cible, resultat)
        except Exception:
            log.exception("Journal OSINT indisponible")

    async def envoyer(self, interaction: discord.Interaction, embed: discord.Embed, **kwargs: object) -> None:
        """Envoie le résultat ; ajoute l'avertissement légal au premier usage."""
        embeds = [embed]
        avertis = list(self.bot.reglages["_osint_avertis"])
        if interaction.user.id not in avertis:
            embeds.insert(0, embed_attention(AVERTISSEMENT_OSINT, "⚖️ Premier usage de l'OSINT"))
            await self.bot.reglages.definir("_osint_avertis", [*avertis, interaction.user.id])
        await repondre(interaction, embeds=embeds, **kwargs)

    async def _executer(self, interaction: discord.Interaction, commande: str, cible: str, travail: object) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            resultat = await travail  # type: ignore[misc]
        except HorsPerimetre as exc:
            await self.journaliser(interaction, commande, cible, "refusé")
            await repondre(interaction, embed=embed_erreur(str(exc), "🚫 Requête refusée"))
            return
        except Exception as exc:
            log.warning("OSINT %s : %s", commande, type(exc).__name__)
            await self.journaliser(interaction, commande, cible, "erreur")
            await repondre(interaction, embed=embed_erreur("Le service en ligne ne répond pas pour le moment. Réessaie plus tard."))
            return
        await self.journaliser(interaction, commande, cible, "ok")
        await self.envoyer(interaction, embed_resultat(resultat))

    # ------------------------------------------------------------ commandes

    @app_commands.command(name="domaine", description="WHOIS, DNS, certificat SSL et archives d'un nom de domaine")
    @app_commands.describe(nom="Ex. exemple.be")
    async def domaine(self, interaction: discord.Interaction, nom: app_commands.Range[str, 1, 255]) -> None:
        await self._executer(interaction, "domaine", nom, self.service.domaine(nom))

    @app_commands.command(name="ip", description="Pays, fournisseur et ASN d'une adresse IP publique")
    @app_commands.describe(adresse="Ex. 8.8.8.8")
    async def ip(self, interaction: discord.Interaction, adresse: app_commands.Range[str, 1, 64]) -> None:
        await self._executer(interaction, "ip", adresse, self.service.ip(adresse))

    @app_commands.command(name="lien", description="Analyse un lien AVANT de cliquer (redirections, réputation)")
    @app_commands.describe(url="Le lien à vérifier")
    async def lien(self, interaction: discord.Interaction, url: app_commands.Range[str, 1, 2000]) -> None:
        await self._executer(interaction, "lien", url, self.service.lien(url))

    @app_commands.command(name="entreprise", description="Données publiques d'une entreprise belge (BCE/KBO)")
    @app_commands.describe(numero_ou_nom="Numéro d'entreprise (0403.170.701) ou dénomination")
    async def entreprise(self, interaction: discord.Interaction, numero_ou_nom: app_commands.Range[str, 1, 100]) -> None:
        await self._executer(interaction, "entreprise", numero_ou_nom, self.service.entreprise(numero_ou_nom))

    @app_commands.command(name="motdepasse", description="Un de MES mots de passe a-t-il fuité ? (k-anonymity)")
    async def motdepasse(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(ModalMotDePasse(self))

    @app_commands.command(name="image", description="Métadonnées EXIF d'une image que J'envoie (+ version nettoyée)")
    @app_commands.describe(fichier="Ta propre image (JPEG, PNG, WEBP...)")
    async def image(self, interaction: discord.Interaction, fichier: discord.Attachment) -> None:
        if not (fichier.content_type or "").startswith("image/") or fichier.size > TAILLE_IMAGE_MAX:
            await repondre(interaction, embed=embed_erreur("Envoie une image de moins de 10 Mo."))
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            donnees = await fichier.read()
            lignes, gps = await asyncio.to_thread(lire_exif, donnees)
        except Exception as exc:
            log.warning("Lecture EXIF impossible : %s", type(exc).__name__)
            await self.journaliser(interaction, "image", "(image personnelle)", "erreur")
            await repondre(interaction, embed=embed_erreur("Impossible de lire cette image."))
            return
        resultat = Resultat(titre="🖼️ Métadonnées de ton image", champs=[(k, v) for k, v in lignes])
        if gps:
            resultat.niveau = "orange"
            resultat.champs.insert(0, (
                "⚠️ Position GPS présente",
                f"`{gps[0]}, {gps[1]}` : n'importe qui peut voir **où** la photo a été prise. "
                "Envoie plutôt la version nettoyée.",
            ))
        else:
            resultat.niveau = "vert"
        resultat.note = "Rien n'est stocké."
        await self.journaliser(interaction, "image", "(image personnelle)", "ok")
        await self.envoyer(interaction, embed_resultat(resultat), view=VueImage(donnees, fichier.filename, interaction.user.id))

    # ------------------------------------------------------------ journal (bouton du panneau)

    async def afficher_journal(self, interaction: discord.Interaction) -> None:
        lignes = [
            f"{ts(quand)} · <@{uid}> · `/osint {commande}` · {tronquer(cible, 60)} · {resultat}"
            for uid, commande, cible, resultat, quand in await self.bot.db.journal_osint(200)
        ]
        if not lignes:
            await repondre(interaction, embed=embed_info("📜 Journal OSINT", "Aucune recherche pour le moment."))
            return
        pages = [embed_info("📜 Journal OSINT", "\n".join(lignes[i : i + 15])) for i in range(0, len(lignes), 15)]
        await envoyer_pages(interaction, pages)


async def setup(bot: TekkitBot) -> None:
    await bot.add_cog(OSINT(bot))
