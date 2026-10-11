"""IA locale : /ia, /ia-generer, /ia-statut. Si Ollama est absent, la surveillance continue."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import discord
from discord import app_commands
from discord.ext import commands

from bot.calculs import formater_duree
from bot.config import MODELE_IA_LEGER, MODES_IA
from bot.ia_moteur import TYPES_GENERATION, ClientOllama, ErreurIA, MoteurIA, OutilsIA
from bot.ui.couleurs import BLEU, ORANGE, VERT
from bot.ui.embeds import embed_attention, embed_erreur, embed_succes
from bot.ui.format import decouper_message
from bot.ui.vues import VueBase, repondre

if TYPE_CHECKING:
    from bot.main import TekkitBot

log = logging.getLogger("tekkit.ia")

CHOIX_GENERATION = [app_commands.Choice(name=v, value=k) for k, v in TYPES_GENERATION.items()]


class VueConversation(VueBase):
    """Bouton 🧹 sous les réponses de l'IA (persistant : marche après redémarrage)."""

    def __init__(self) -> None:
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Nouvelle conversation",
        emoji="🧹",
        style=discord.ButtonStyle.secondary,
        custom_id="tw:ia:nouvelle",
    )
    async def nouvelle(self, interaction: discord.Interaction, _b: discord.ui.Button) -> None:
        cog = interaction.client.get_cog("IA")  # type: ignore[attr-defined]
        if cog is None:
            await repondre(interaction, embed=embed_erreur("Le module IA n'est pas disponible."))
            return
        await cog.nouvelle_conversation(interaction)


def _octets(n: int | None) -> str:
    if not n:
        return "—"
    return f"{n / 1024**3:.1f} Go"


class IA(commands.Cog):
    def __init__(self, bot: TekkitBot) -> None:
        self.bot = bot
        self.moteur = MoteurIA(
            ClientOllama(bot.config.ollama_url), bot.reglages, OutilsIA(bot.services)
        )

    async def cog_load(self) -> None:
        self.bot.add_view(VueConversation())

    async def cog_unload(self) -> None:
        await self.moteur.client.fermer()

    # ------------------------------------------------------------ contrôles

    async def _verifier(self, interaction: discord.Interaction) -> bool:
        """Activée ? autorisé ? pas trop de questions ? Répond à la place si non."""
        if not self.bot.reglages["ia_active"]:
            await repondre(
                interaction, embed=embed_attention("L'IA est désactivée (`/parametres` → 🤖 IA).")
            )
            return False
        if not self.moteur.autorise(interaction.user.id, self.bot.config.owner_id):
            await repondre(
                interaction,
                embed=embed_erreur(
                    "🔒 Tu n'es pas autorisé à utiliser l'IA. Demande au propriétaire."
                ),
            )
            return False
        if self.moteur.limite_atteinte(interaction.user.id):
            limite = self.bot.reglages["ia_limite_minute"]
            await repondre(
                interaction,
                embed=embed_attention(
                    f"🚦 Maximum {limite} questions par minute. Patiente un peu."
                ),
            )
            return False
        return True

    def _sur_attente(self, interaction: discord.Interaction) -> Any:
        async def prevenir(position: int) -> None:
            await interaction.edit_original_response(
                content=f"⏳ L'IA est occupée : {position} demande{'s' if position > 1 else ''} avant toi. Patiente…"
            )

        return prevenir

    async def _envoyer_texte(
        self, interaction: discord.Interaction, texte: str, pied: str, vue: discord.ui.View | None
    ) -> None:
        morceaux = decouper_message(texte, 1900) or ["…"]
        morceaux[-1] = f"{morceaux[-1]}\n-# {pied}"
        aucune = discord.AllowedMentions.none()  # l'IA ne mentionne jamais personne
        await interaction.edit_original_response(
            content=morceaux[0], view=vue if len(morceaux) == 1 else None, allowed_mentions=aucune
        )
        for i, morceau in enumerate(morceaux[1:], start=2):
            await interaction.followup.send(
                morceau,
                view=vue if i == len(morceaux) else discord.utils.MISSING,
                allowed_mentions=aucune,
            )

    # ------------------------------------------------------------ /ia

    @app_commands.command(
        name="ia", description="Pose une question à l'IA locale (elle connaît tes stats)"
    )
    @app_commands.describe(
        question="Ex. « analyse mon farm d'aujourd'hui », « quel compte est le plus rentable ? »"
    )
    async def ia(
        self, interaction: discord.Interaction, question: app_commands.Range[str, 1, 1500]
    ) -> None:
        if not await self._verifier(interaction):
            return
        await interaction.response.defer(thinking=True)  # affiche « Tekkit Watch réfléchit… »
        salon = interaction.channel_id or 0
        memoire = int(self.bot.reglages["ia_memoire"]) * 2
        historique = await self.bot.db.historique_ia(salon, memoire) if memoire else []
        try:
            reponse = await self.moteur.repondre(
                question, historique, self._sur_attente(interaction)
            )
        except ErreurIA as exc:
            await interaction.edit_original_response(
                content=None, embed=embed_erreur(str(exc), "🤖 IA indisponible")
            )
            return
        except Exception:
            log.exception("Erreur inattendue de l'IA")
            await interaction.edit_original_response(
                content=None, embed=embed_erreur("L'IA a rencontré un problème inattendu.")
            )
            return
        await self.bot.db.ajouter_message_ia(salon, "user", question)
        await self.bot.db.ajouter_message_ia(salon, "assistant", reponse.texte)
        pied = f"🤖 {self.bot.reglages['ia_modele']} · {formater_duree(reponse.duree_s)}"
        if reponse.outils:
            pied += " · 📊 données réelles"
        elif reponse.secours:
            pied += " · 📊 résumé des stats"
        await self._envoyer_texte(
            interaction, f"> {question[:300]}\n\n{reponse.texte}", pied, VueConversation()
        )

    async def nouvelle_conversation(self, interaction: discord.Interaction) -> None:
        if not self.moteur.autorise(interaction.user.id, self.bot.config.owner_id):
            await repondre(
                interaction, embed=embed_erreur("🔒 Réservé aux utilisateurs autorisés de l'IA.")
            )
            return
        await self.bot.db.effacer_conversation_ia(interaction.channel_id or 0)
        await repondre(
            interaction,
            embed=embed_succes(
                "🧹 Mémoire effacée : la prochaine question démarre une nouvelle conversation."
            ),
        )

    # ------------------------------------------------------------ /ia-generer

    @app_commands.command(
        name="ia-generer", description="Génère un texte prêt à copier (annonce, règles, idées...)"
    )
    @app_commands.describe(type="Type de texte", sujet="De quoi doit parler le texte ?")
    @app_commands.choices(type=CHOIX_GENERATION)
    async def ia_generer(
        self,
        interaction: discord.Interaction,
        type: app_commands.Choice[str],
        sujet: app_commands.Range[str, 1, 1000],
    ) -> None:
        if not await self._verifier(interaction):
            return
        await interaction.response.defer(thinking=True)
        try:
            reponse = await self.moteur.generer(type.value, sujet, self._sur_attente(interaction))
        except ErreurIA as exc:
            await interaction.edit_original_response(
                content=None, embed=embed_erreur(str(exc), "🤖 IA indisponible")
            )
            return
        except Exception:
            log.exception("Erreur inattendue de l'IA")
            await interaction.edit_original_response(
                content=None, embed=embed_erreur("L'IA a rencontré un problème inattendu.")
            )
            return
        pied = (
            f"{type.name} · 🤖 {self.bot.reglages['ia_modele']} · {formater_duree(reponse.duree_s)}"
        )
        await self._envoyer_texte(interaction, reponse.texte, pied, None)

    # ------------------------------------------------------------ /ia-statut

    async def embed_statut(self) -> discord.Embed:
        s = await self.moteur.statut()
        r = self.bot.reglages
        if not s.joignable:
            couleur, etat = ORANGE, f"🔴 Ollama ne répond pas sur `{self.bot.config.ollama_url}`"
        elif not s.modele_installe:
            couleur, etat = (
                ORANGE,
                f"🟠 Ollama OK, mais le modèle n'est pas téléchargé : `ollama pull {s.modele_choisi}`",
            )
        else:
            couleur, etat = VERT, "🟢 Ollama OK, modèle installé"
        e = discord.Embed(
            title="🤖 Statut de l'IA locale",
            description=etat,
            color=couleur if r["ia_active"] else BLEU,
        )
        e.add_field(
            name="🧠 Modèle",
            value=f"`{s.modele_choisi}`\n{MODES_IA.get(r['ia_mode'], r['ia_mode'])}",
            inline=True,
        )
        e.add_field(
            name="💾 En mémoire",
            value=f"{'✅ chargé' if s.charge else '💤 déchargé (0 Go)'}\nRAM : {_octets(s.ram_octets)}",
            inline=True,
        )
        e.add_field(
            name="⏱️ Dernière réponse",
            value=formater_duree(s.derniere_duree_s) if s.derniere_duree_s is not None else "—",
            inline=True,
        )
        e.add_field(name="📋 File d'attente", value=f"{s.en_attente} demande(s)", inline=True)
        e.add_field(
            name="💤 Déchargement auto",
            value=f"après {r['ia_keep_alive_min']} min sans question",
            inline=True,
        )
        e.add_field(name="🤖 IA activée", value="oui" if r["ia_active"] else "non", inline=True)
        if s.modeles:
            e.add_field(
                name="📦 Modèles installés",
                value=", ".join(f"`{m}`" for m in s.modeles[:15]),
                inline=False,
            )
        e.set_footer(
            text=f"PC qui rame ? Essaie le modèle léger {MODELE_IA_LEGER} · 100 % local et gratuit"
        )
        return e

    @app_commands.command(
        name="ia-statut", description="Ollama joignable ? modèle chargé ? RAM utilisée ?"
    )
    async def ia_statut(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        await repondre(interaction, embed=await self.embed_statut())

    async def tester(self, interaction: discord.Interaction) -> None:
        """Bouton « Tester l'IA » du panneau : petite question rapide."""
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            reponse = await self.moteur.generer(
                "autre", "Dis bonjour en une phrase courte et confirme que tu fonctionnes."
            )
            await repondre(
                interaction,
                embed=embed_succes(
                    f"{reponse.texte}\n\n-# ⏱️ {formater_duree(reponse.duree_s)}",
                    "🧪 L'IA fonctionne",
                ),
            )
        except ErreurIA as exc:
            await repondre(interaction, embed=embed_erreur(str(exc), "🧪 Test de l'IA"))


async def setup(bot: TekkitBot) -> None:
    await bot.add_cog(IA(bot))
