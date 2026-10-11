"""Graphiques PNG (matplotlib), rendus en mémoire puis envoyés comme fichier Discord.

Thème sombre, une couleur fixe par compte, une seule échelle, courbes fines,
légende dès 2 comptes et valeur finale écrite au bout de chaque courbe (≤ 4 comptes).
"""

from __future__ import annotations

import io
from collections.abc import Mapping, Sequence
from datetime import datetime

import matplotlib

matplotlib.use("Agg")  # pas de fenêtre : rendu en mémoire uniquement

import matplotlib.dates as mdates  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402

from bot.calculs import formater_nombre  # noqa: E402
from bot.config import FUSEAU  # noqa: E402
from bot.parser import Mission  # noqa: E402
from bot.ui.couleurs import COULEURS_COMPTES  # noqa: E402

# Couleurs de l'habillage (thème sombre)
FOND = "#1a1a19"
ENCRE = "#f0efec"
ENCRE_SECONDAIRE = "#c3c2b7"
ENCRE_DISCRETE = "#898781"
GRILLE = "#2c2c2a"
AXE = "#383835"

TYPES_GRAPHIQUE: dict[str, str] = {
    "gold": "💰 Gold gagné (cumulé)",
    "xp": "✨ XP gagnée (cumulée)",
    "gems": "💎 Gems gagnées (cumulées)",
    "missions": "🎯 Missions (cumulées)",
}
_TITRES = {
    "gold": "Gold gagné",
    "xp": "XP gagnée",
    "gems": "Gems gagnées",
    "missions": "Missions terminées",
}


def serie_cumulee(missions: Sequence[Mission], type_: str) -> tuple[list[float], list[float]]:
    """Points (horodatage, valeur cumulée) d'un compte pour le type demandé."""
    triees = sorted(missions, key=lambda m: m.horodatage)
    xs: list[float] = []
    ys: list[float] = []
    if type_ == "gems":
        depart = next((m.gems_total for m in triees if m.gems_total is not None), None)
        if depart is None:
            return [], []
        for m in triees:
            if m.gems_total is not None:
                xs.append(m.horodatage)
                ys.append(max(0, m.gems_total - depart))
        return xs, ys
    cumul = 0.0
    for m in triees:
        if type_ == "gold":
            cumul += m.gold or 0
        elif type_ == "xp":
            cumul += m.xp or 0
        else:
            cumul += 1
        xs.append(m.horodatage)
        ys.append(cumul)
    return xs, ys


def _format_axe_y(valeur: float, _pos: int) -> str:
    if abs(valeur) >= 1_000_000:
        return f"{valeur / 1_000_000:.1f} M".replace(".0 M", " M")
    if abs(valeur) >= 10_000:
        return f"{valeur / 1000:.0f} k"
    return formater_nombre(valeur).replace(" ", " ")


def graphique(
    series: Mapping[str, Sequence[Mission]],
    type_: str,
    titre_periode: str,
    ordre_comptes: Sequence[str],
) -> io.BytesIO | None:
    """Trace une courbe par compte. Renvoie un PNG en mémoire, ou None si aucune donnée."""
    courbes = []
    for nom, missions in series.items():
        xs, ys = serie_cumulee(missions, type_)
        if len(xs) >= 1:
            courbes.append((nom, xs, ys))
    if not courbes:
        return None

    # Figure (et pas pyplot) : aucun état global, donc utilisable depuis un thread
    fig = Figure(figsize=(10, 5.2), dpi=110)
    ax = fig.subplots()
    fig.patch.set_facecolor(FOND)
    ax.set_facecolor(FOND)

    index = {c.casefold(): i for i, c in enumerate(ordre_comptes)}
    etiquettes = len(courbes) <= 4
    for nom, xs, ys in courbes:
        i = index.get(nom.casefold(), len(index))
        couleur = COULEURS_COMPTES[i % len(COULEURS_COMPTES)]
        style = "-" if i < len(COULEURS_COMPTES) else "--"  # au-delà de 8 : pointillés
        dates = [datetime.fromtimestamp(x, FUSEAU) for x in xs]
        ax.plot(dates, ys, color=couleur, linewidth=2, linestyle=style, label=nom,
                solid_capstyle="round", solid_joinstyle="round")
        # Point final avec un anneau couleur du fond, pour rester lisible au croisement
        ax.plot(dates[-1:], ys[-1:], marker="o", markersize=7, color=couleur,
                markeredgecolor=FOND, markeredgewidth=2)
        if etiquettes:
            ax.annotate(
                f"{formater_nombre(ys[-1])}".replace(" ", " "),
                xy=(dates[-1], ys[-1]), xytext=(8, 0), textcoords="offset points",
                va="center", fontsize=9, color=ENCRE,
            )

    ax.set_title(f"{_TITRES.get(type_, type_)} · {titre_periode}", color=ENCRE, fontsize=13,
                 loc="left", pad=12, fontweight="bold")
    ax.grid(axis="y", color=GRILLE, linewidth=1)
    ax.grid(axis="x", visible=False)
    for cote in ("top", "right", "left"):
        ax.spines[cote].set_visible(False)
    ax.spines["bottom"].set_color(AXE)
    ax.tick_params(colors=ENCRE_DISCRETE, length=0, pad=6)
    ax.yaxis.set_major_formatter(FuncFormatter(_format_axe_y))
    localisateur = mdates.AutoDateLocator(tz=FUSEAU, maxticks=8)
    ax.xaxis.set_major_locator(localisateur)
    ax.xaxis.set_major_formatter(
        mdates.ConciseDateFormatter(
            localisateur,
            tz=FUSEAU,
            formats=["%Y", "%m/%Y", "%d/%m", "%H:%M", "%H:%M", "%S"],
            zero_formats=["", "%Y", "%m/%Y", "%d/%m", "%H:%M", "%H:%M"],
            offset_formats=["", "%Y", "%m/%Y", "%d/%m/%Y", "%d/%m/%Y", "%d/%m/%Y %H:%M"],
        )
    )
    ax.set_ylim(bottom=0)
    ax.margins(x=0.08 if etiquettes else 0.02)

    if len(courbes) >= 2:
        legende = ax.legend(loc="upper left", frameon=False, labelcolor=ENCRE_SECONDAIRE,
                            ncol=min(5, len(courbes)), handlelength=1.6)
        for ligne in legende.get_lines():
            ligne.set_linewidth(3)

    fig.text(0.99, 0.985, "Tekkit Watch", color=ENCRE_DISCRETE, fontsize=8, ha="right", va="top")
    fig.tight_layout()
    tampon = io.BytesIO()
    fig.savefig(tampon, format="png", facecolor=FOND)
    tampon.seek(0)
    return tampon
