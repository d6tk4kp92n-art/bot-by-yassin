"""Statistiques : /estimation, /stats, /graphique, /drops, /comparer, /export."""

from __future__ import annotations

import asyncio
import csv
import io
import logging
from datetime import datetime
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from bot.calculs import PERIODES
from bot.config import FUSEAU
from bot.graphiques import TYPES_GRAPHIQUE, graphique
from bot.ui.embeds import (
    embed_comparer,
    embed_erreur,
    embed_estimation,
    embed_info,
    embed_stats,
    pages_drops,
)
from bot.ui.vues import envoyer_pages, repondre

if TYPE_CHECKING:
    from bot.main import TekkitBot

log = logging.getLogger("tekkit.stats")

CHOIX_PERIODE = [app_commands.Choice(name=v, value=k) for k, v in PERIODES.items()]
CHOIX_GRAPHIQUE = [app_commands.Choice(name=v, value=k) for k, v in TYPES_GRAPHIQUE.items()]


async def autocomplete_compte(interaction: discord.Interaction, courant: str) -> list[app_commands.Choice[str]]:
    """Propose les comptes configurés pendant la saisie."""
    bot = interaction.client
    comptes = list(getattr(bot, "reglages", {}).get("comptes", []))
    return [app_commands.Choice(name=c, value=c) for c in comptes if courant.casefold() in c.casefold()][:25]


async def autocomplete_rarete(interaction: discord.Interaction, courant: str) -> list[app_commands.Choice[str]]:
    bot = interaction.client
    raretes = list(getattr(bot, "reglages", {}).get("raretes", []))
    return [app_commands.Choice(name=r, value=r) for r in raretes if courant.casefold() in r.casefold()][:25]


class Stats(commands.Cog):
    def __init__(self, bot: TekkitBot) -> None:
        self.bot = bot

    def _compte_valide(self, compte: str | None) -> str | None:
        """Renvoie le nom configuré, ou None. Lève ValueError si le compte est inconnu."""
        if compte is None:
            return None
        for c in self.bot.reglages["comptes"]:
            if c.casefold() == compte.strip().casefold():
                return c
        raise ValueError(f"Le compte « {compte} » n'est pas dans la liste des comptes surveillés.")

    # ------------------------------------------------------------ estimation

    async def repondre_estimation(self, interaction: discord.Interaction, heures: float) -> None:
        estimations = await self.bot.services.estimations(heures)
        await repondre(interaction, embed=embed_estimation(heures, estimations))

    @app_commands.command(name="estimation", description="Estime les gains des prochaines heures au rythme actuel")
    @app_commands.describe(heures="Nombre d'heures (1 à 48)")
    async def estimation(self, interaction: discord.Interaction, heures: app_commands.Range[int, 1, 48]) -> None:
        await self.repondre_estimation(interaction, float(heures))

    # ------------------------------------------------------------ stats

    async def repondre_stats(self, interaction: discord.Interaction, periode: str) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        debut, _ = await self.bot.services.bornes(periode)
        stats = await self.bot.services.stats(periode)
        await repondre(interaction, embed=embed_stats(periode, debut, stats, self.bot.reglages["raretes"]))

    @app_commands.command(name="stats", description="Statistiques détaillées sur une période")
    @app_commands.describe(periode="Période à analyser")
    @app_commands.choices(periode=CHOIX_PERIODE)
    async def stats(self, interaction: discord.Interaction, periode: app_commands.Choice[str]) -> None:
        await self.repondre_stats(interaction, periode.value)

    # ------------------------------------------------------------ graphique

    async def fichier_graphique(self, type_: str, periode: str) -> discord.File | None:
        debut, fin = await self.bot.services.bornes(periode)
        comptes = list(self.bot.reglages["comptes"])
        series = {c: await self.bot.db.missions(compte=c, debut=debut, fin=fin) for c in comptes}
        image = await asyncio.to_thread(graphique, series, type_, PERIODES.get(periode, periode).lower(), comptes)
        if image is None:
            return None
        return discord.File(image, filename=f"graphique_{type_}_{periode}.png")

    async def repondre_graphique(self, interaction: discord.Interaction, type_: str, periode: str) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        fichier = await self.fichier_graphique(type_, periode)
        if fichier is None:
            await repondre(interaction, embed=embed_info("📊 Graphique", "Pas encore de données sur cette période."))
            return
        embed = embed_info(f"📊 {TYPES_GRAPHIQUE[type_]}", PERIODES.get(periode, periode))
        embed.set_image(url=f"attachment://{fichier.filename}")
        await repondre(interaction, embed=embed, file=fichier)

    @app_commands.command(name="graphique", description="Courbe des gains par compte, en image")
    @app_commands.describe(type="Ce qu'on affiche", periode="Période")
    @app_commands.choices(type=CHOIX_GRAPHIQUE, periode=CHOIX_PERIODE)
    async def graphique_cmd(
        self, interaction: discord.Interaction, type: app_commands.Choice[str], periode: app_commands.Choice[str]
    ) -> None:
        await self.repondre_graphique(interaction, type.value, periode.value)

    # ------------------------------------------------------------ drops

    @app_commands.command(name="drops", description="Historique des objets rares")
    @app_commands.describe(compte="Un seul compte (sinon tous)", rarete="Rareté minimum", periode="Période")
    @app_commands.autocomplete(compte=autocomplete_compte, rarete=autocomplete_rarete)
    @app_commands.choices(periode=CHOIX_PERIODE)
    async def drops(
        self,
        interaction: discord.Interaction,
        compte: str | None = None,
        rarete: str | None = None,
        periode: app_commands.Choice[str] | None = None,
    ) -> None:
        try:
            nom = self._compte_valide(compte)
        except ValueError as exc:
            await repondre(interaction, embed=embed_erreur(str(exc)))
            return
        rarete_min = rarete or self.bot.reglages["rarete_min"]
        if rarete_min.casefold() not in {r.casefold() for r in self.bot.reglages["raretes"]}:
            await repondre(interaction, embed=embed_erreur(f"Rareté inconnue : « {rarete_min} »."))
            return
        p = periode.value if periode else "tout"
        liste = await self.bot.services.drops_rares(nom, rarete_min, p)
        titre = f"🎁 Objets {rarete_min}+ · {nom or 'tous les comptes'} · {PERIODES[p]}"
        await envoyer_pages(interaction, pages_drops(liste, titre))

    # ------------------------------------------------------------ comparer

    @app_commands.command(name="comparer", description="Compare les comptes côte à côte")
    @app_commands.describe(periode="Période (par défaut : aujourd'hui)")
    @app_commands.choices(periode=CHOIX_PERIODE)
    async def comparer(self, interaction: discord.Interaction, periode: app_commands.Choice[str] | None = None) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        p = periode.value if periode else "aujourdhui"
        stats = await self.bot.services.stats(p)
        await repondre(interaction, embed=embed_comparer(p, stats))

    # ------------------------------------------------------------ export

    @app_commands.command(name="export", description="Exporte les missions en CSV (pour Excel)")
    @app_commands.describe(periode="Période (par défaut : tout)")
    @app_commands.choices(periode=CHOIX_PERIODE)
    async def export(self, interaction: discord.Interaction, periode: app_commands.Choice[str] | None = None) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        p = periode.value if periode else "tout"
        debut, fin = await self.bot.services.bornes(p)
        missions = await self.bot.db.missions(debut=debut, fin=fin, avec_drops=True)
        contenu = generer_csv(missions)
        nom = f"tekkit_missions_{datetime.now(FUSEAU):%Y-%m-%d_%H%M}.csv"
        fichier = discord.File(io.BytesIO(contenu), filename=nom)
        await repondre(
            interaction,
            embed=embed_info("📤 Export CSV", f"{len(missions)} missions · {PERIODES[p]}\nOuvre le fichier avec Excel."),
            file=fichier,
        )


def generer_csv(missions: list) -> bytes:
    """CSV lisible par Excel en français (séparateur « ; », encodage UTF-8 avec BOM)."""
    tampon = io.StringIO()
    ecrivain = csv.writer(tampon, delimiter=";")
    ecrivain.writerow([
        "date", "compte", "gold", "xp", "gems_total", "gold_total", "niveau", "prestige",
        "duree_s", "difficulte", "zone", "objets",
    ])
    for m in missions:
        ecrivain.writerow([
            datetime.fromtimestamp(m.horodatage, FUSEAU).strftime("%d/%m/%Y %H:%M:%S"),
            m.compte, m.gold, m.xp, m.gems_total, m.gold_total, m.level, m.prestige,
            m.duree_s, m.difficulte or "", m.zone or "",
            ", ".join(f"{d.nom} ({d.rarete})" + (f" x{d.quantite}" if d.quantite > 1 else "") for d in m.drops),
        ])
    return tampon.getvalue().encode("utf-8-sig")


async def setup(bot: TekkitBot) -> None:
    await bot.add_cog(Stats(bot))

