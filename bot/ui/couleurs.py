"""Couleurs cohérentes dans tout le bot (embeds ET graphiques)."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

VERT = 0x57F287
ORANGE = 0xE67E22
ROUGE = 0xED4245
BLEU = 0x5865F2
GRIS = 0x99AAB5
VIOLET = 0x9B59B6

# Une couleur fixe par compte (même ordre que la liste des comptes).
# Palette catégorielle validée pour fond sombre (lisible par les daltoniens,
# contraste >= 3:1). Au-delà de 8 comptes, les couleurs reviennent mais les
# courbes passent en pointillés (voir graphiques.py) pour rester distinguables.
COULEURS_COMPTES: list[str] = [
    "#3987e5",  # bleu
    "#d95926",  # orange
    "#199e70",  # turquoise
    "#c98500",  # jaune
    "#d55181",  # magenta
    "#008300",  # vert
    "#9085e9",  # violet
    "#e66767",  # rouge
]

_RE_HEX = re.compile(r"^#?([0-9a-fA-F]{6})$")


def hex_vers_int(texte: str | None) -> int | None:
    """« #5865F2 » ou « 5865f2 » -> 0x5865F2. None si invalide."""
    if not texte:
        return None
    m = _RE_HEX.match(texte.strip())
    return int(m.group(1), 16) if m else None


def normaliser_hex(texte: str) -> str | None:
    """« 5865f2 » -> « #5865F2 ». None si invalide."""
    valeur = hex_vers_int(texte)
    return f"#{valeur:06X}" if valeur is not None else None


def couleur_compte(index: int) -> str:
    return COULEURS_COMPTES[index % len(COULEURS_COMPTES)]


def couleur_resume(reglages: Mapping[str, Any], etats: Sequence[Any]) -> int:
    """Couleur du résumé : fixe, ou « auto » (rouge si hors Safe, orange si absent, vert sinon)."""
    choix = str(reglages.get("couleur", "auto"))
    if choix != "auto":
        return hex_vers_int(choix) or BLEU
    if any(getattr(e, "est_safe", None) is False for e in etats):
        return ROUGE
    if any(getattr(e, "en_ligne", None) is not True for e in etats):
        return ORANGE
    return VERT
