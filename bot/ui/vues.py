"""Vues (boutons, menus) réutilisables."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable, Sequence
from typing import Any

import discord

from bot.ui.embeds import embed_erreur

log = logging.getLogger("tekkit.ui")


async def repondre(interaction: discord.Interaction, ephemeral: bool = True, **kwargs: Any) -> None:
    """Répond à une interaction, qu'on ait déjà répondu (defer) ou non."""
    kwargs = {k: v for k, v in kwargs.items() if v is not None}
    try:
        if interaction.response.is_done():
            await interaction.followup.send(ephemeral=ephemeral, **kwargs)
        else:
            await interaction.response.send_message(ephemeral=ephemeral, **kwargs)
    except discord.HTTPException as exc:
        log.warning("Impossible de répondre à l'interaction : %s", exc)


async def repondre_erreur(interaction: discord.Interaction, texte: str) -> None:
    await repondre(interaction, embed=embed_erreur(texte))


class VueBase(discord.ui.View):
    """Vue qui n'affiche jamais de trace Python : un message gentil à la place."""

    async def on_error(
        self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item[Any]
    ) -> None:
        log.exception("Erreur dans un composant (%s)", type(item).__name__, exc_info=error)
        await repondre_erreur(
            interaction, "Quelque chose s'est mal passé avec ce bouton. Réessaie dans un instant."
        )


class VueResume(VueBase):
    """Boutons sous le résumé. PERSISTANTS : ils marchent encore après un redémarrage
    (timeout=None + custom_id fixes + bot.add_view au démarrage)."""

    def __init__(self) -> None:
        super().__init__(timeout=None)

    async def _cog(self, interaction: discord.Interaction) -> Any:
        cog = interaction.client.get_cog("Resumes")  # type: ignore[attr-defined]
        if cog is None:
            await repondre_erreur(
                interaction, "Le module des résumés n'est pas disponible pour le moment."
            )
        return cog

    @discord.ui.button(
        label="Actualiser",
        emoji="🔄",
        style=discord.ButtonStyle.primary,
        custom_id="tw:resume:actualiser",
        row=0,
    )
    async def actualiser(self, interaction: discord.Interaction, _b: discord.ui.Button) -> None:
        if cog := await self._cog(interaction):
            await cog.bouton_actualiser(interaction)

    @discord.ui.button(
        label="Copiable",
        emoji="📋",
        style=discord.ButtonStyle.secondary,
        custom_id="tw:resume:copiable",
        row=0,
    )
    async def copiable(self, interaction: discord.Interaction, _b: discord.ui.Button) -> None:
        if cog := await self._cog(interaction):
            await cog.bouton_copiable(interaction)

    @discord.ui.button(
        label="Stats",
        emoji="📈",
        style=discord.ButtonStyle.secondary,
        custom_id="tw:resume:stats",
        row=0,
    )
    async def stats(self, interaction: discord.Interaction, _b: discord.ui.Button) -> None:
        if cog := await self._cog(interaction):
            await cog.bouton_stats(interaction)

    @discord.ui.button(
        label="Estimation",
        emoji="🔮",
        style=discord.ButtonStyle.secondary,
        custom_id="tw:resume:estimation",
        row=1,
    )
    async def estimation(self, interaction: discord.Interaction, _b: discord.ui.Button) -> None:
        if cog := await self._cog(interaction):
            await cog.bouton_estimation(interaction)

    @discord.ui.button(
        label="Graphique",
        emoji="📊",
        style=discord.ButtonStyle.secondary,
        custom_id="tw:resume:graphique",
        row=1,
    )
    async def graphique(self, interaction: discord.Interaction, _b: discord.ui.Button) -> None:
        if cog := await self._cog(interaction):
            await cog.bouton_graphique(interaction)

    @discord.ui.button(
        label="Paramètres",
        emoji="⚙️",
        style=discord.ButtonStyle.secondary,
        custom_id="tw:resume:parametres",
        row=1,
    )
    async def parametres(self, interaction: discord.Interaction, _b: discord.ui.Button) -> None:
        cog = interaction.client.get_cog("Parametres")  # type: ignore[attr-defined]
        if cog is None:
            await repondre_erreur(
                interaction, "Le panneau des paramètres n'est pas disponible pour le moment."
            )
            return
        await cog.ouvrir_panneau(interaction)


class VuePagination(VueBase):
    """◀️ ▶️ pour feuilleter une liste d'embeds."""

    def __init__(
        self, pages: Sequence[discord.Embed], auteur_id: int | None = None, timeout: float = 300
    ) -> None:
        super().__init__(timeout=timeout)
        self.pages = list(pages)
        self.index = 0
        self.auteur_id = auteur_id
        self._maj_boutons()

    def _maj_boutons(self) -> None:
        self.precedent.disabled = self.index <= 0
        self.suivant.disabled = self.index >= len(self.pages) - 1
        self.compteur.label = f"{self.index + 1}/{len(self.pages)}"

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if self.auteur_id is not None and interaction.user.id != self.auteur_id:
            await repondre_erreur(interaction, "Ces boutons ne sont pas pour toi 🙂")
            return False
        return True

    @discord.ui.button(emoji="◀️", style=discord.ButtonStyle.secondary)
    async def precedent(self, interaction: discord.Interaction, _b: discord.ui.Button) -> None:
        self.index = max(0, self.index - 1)
        self._maj_boutons()
        await interaction.response.edit_message(embed=self.pages[self.index], view=self)

    @discord.ui.button(label="1/1", style=discord.ButtonStyle.secondary, disabled=True)
    async def compteur(self, interaction: discord.Interaction, _b: discord.ui.Button) -> None:
        await interaction.response.defer()

    @discord.ui.button(emoji="▶️", style=discord.ButtonStyle.secondary)
    async def suivant(self, interaction: discord.Interaction, _b: discord.ui.Button) -> None:
        self.index = min(len(self.pages) - 1, self.index + 1)
        self._maj_boutons()
        await interaction.response.edit_message(embed=self.pages[self.index], view=self)


async def envoyer_pages(
    interaction: discord.Interaction, pages: Sequence[discord.Embed], ephemeral: bool = True
) -> None:
    """Envoie une liste d'embeds : avec boutons de pagination seulement s'il y a plusieurs pages."""
    if len(pages) <= 1:
        await repondre(interaction, ephemeral=ephemeral, embed=pages[0] if pages else None)
        return
    await repondre(
        interaction,
        ephemeral=ephemeral,
        embed=pages[0],
        view=VuePagination(pages, interaction.user.id),
    )


class VueConfirmation(VueBase):
    """Demande « Tu es sûr ? » avant une action destructive."""

    def __init__(
        self,
        action: Callable[[discord.Interaction], Awaitable[None]],
        auteur_id: int,
        libelle: str = "Oui, je confirme",
        annuler: Callable[[discord.Interaction], Awaitable[None]] | None = None,
    ) -> None:
        super().__init__(timeout=60)
        self.action = action
        self.annulation = annuler
        self.auteur_id = auteur_id
        self.confirmer.label = libelle

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.auteur_id

    @discord.ui.button(label="Oui, je confirme", emoji="⚠️", style=discord.ButtonStyle.danger)
    async def confirmer(self, interaction: discord.Interaction, _b: discord.ui.Button) -> None:
        self.stop()
        await self.action(interaction)

    @discord.ui.button(label="Annuler", emoji="✖️", style=discord.ButtonStyle.secondary)
    async def annuler(self, interaction: discord.Interaction, _b: discord.ui.Button) -> None:
        self.stop()
        if self.annulation is not None:
            await self.annulation(interaction)
        else:
            await interaction.response.edit_message(
                content="Action annulée.", embed=None, view=None
            )
