"""Petites fonctions de mise en forme réutilisées partout."""

from __future__ import annotations

import re

from bot.calculs import formater_duree, formater_nombre

__all__ = [
    "barre",
    "decouper_message",
    "formater_duree",
    "formater_nombre",
    "nombre",
    "ts",
    "tronquer",
]

# Mêmes emojis pour les mêmes notions dans tout le bot
EMOJI = {
    "gold": "💰",
    "xp": "✨",
    "gems": "💎",
    "missions": "🎯",
    "zone": "🛡️",
    "drops": "🎁",
    "estimation": "🔮",
    "temps": "⏱️",
    "niveau": "⭐",
    "stats": "📈",
    "graphique": "📊",
    "en_ligne": "🟢",
    "absent": "🔴",
    "inconnu": "⚪",
}


def nombre(valeur: float | None) -> str:
    """37807 -> « 37 807 »."""
    return formater_nombre(valeur)


def ts(horodatage: float | None, style: str = "R") -> str:
    """Horodatage Discord : <t:...:R> s'affiche « il y a 3 minutes » chez chacun."""
    if horodatage is None:
        return "jamais"
    return f"<t:{int(horodatage)}:{style}>"


def tronquer(texte: str, limite: int) -> str:
    """Coupe un texte trop long en ajoutant « … »."""
    if len(texte) <= limite:
        return texte
    return texte[: max(0, limite - 1)].rstrip() + "…"


def barre(fraction: float, largeur: int = 12) -> str:
    """Barre de progression : ▰▰▰▰▱▱▱▱ 50 %."""
    fraction = max(0.0, min(1.0, fraction))
    pleins = round(fraction * largeur)
    return "▰" * pleins + "▱" * (largeur - pleins) + f" {fraction * 100:.0f} %"


_RE_OUVERTURE = re.compile(r"^```([A-Za-z0-9_+-]*)\s*$")


def decouper_message(texte: str, limite: int = 2000) -> list[str]:
    """Découpe un long texte en morceaux de `limite` caractères maximum.

    On coupe de préférence entre deux lignes, et si on coupe au milieu d'un bloc
    de code ```, on le referme puis on le rouvre dans le morceau suivant.
    """
    texte = texte.strip()
    if not texte:
        return []
    if len(texte) <= limite:
        return [texte]
    morceaux: list[str] = []
    courant = ""
    langage: str | None = None  # None = pas dans un bloc de code

    def fermer() -> None:
        nonlocal courant
        if courant.strip():
            morceaux.append(courant.rstrip("\n") + ("\n```" if langage is not None else ""))
        courant = f"```{langage}\n" if langage is not None else ""

    reserve = 4  # place pour « \n``` »
    for ligne in texte.split("\n"):
        # Une ligne seule trop longue : on la coupe en tranches
        while len(ligne) > limite - reserve - 20:
            espace = limite - reserve - len(courant) - 1
            if espace < 20:
                fermer()
                continue
            courant += ligne[:espace] + "\n"
            ligne = ligne[espace:]
            fermer()
        if len(courant) + len(ligne) + 1 > limite - reserve:
            fermer()
        courant += ligne + "\n"
        m = _RE_OUVERTURE.match(ligne.strip())
        if ligne.strip().startswith("```"):
            if langage is None:
                langage = m.group(1) if m else ""
            else:
                langage = None
    if courant.strip() and courant.strip() not in ("```", f"```{langage}"):
        morceaux.append(courant.rstrip("\n"))
    return morceaux
