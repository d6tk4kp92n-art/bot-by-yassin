"""Lecture des embeds postés par le webhook « Tekkit | Rewards Logger ».

Que des fonctions pures (pas de Discord, pas de base de données) : faciles à tester.
Règle d'or : ne JAMAIS planter. Si un champ manque ou est bizarre, on l'ignore.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

# Une ligne d'objet : "Enhanced Metabolism (Common)", "Lucky (Rare) x2", "x2 Lucky (Rare)"
_RE_OBJET = re.compile(
    r"^(?:[x×]\s*(?P<q1>\d+)\s+)?(?P<nom>.+?)\s*\((?P<rarete>[^()]+)\)\s*(?:[x×]\s*(?P<q2>\d+))?$",
    re.IGNORECASE,
)
_RE_BLOC_CODE = re.compile(r"```[A-Za-z0-9_+-]*[ \t]*\n?")


@dataclass(frozen=True)
class Drop:
    """Un objet obtenu à la fin d'une mission."""

    nom: str
    rarete: str
    quantite: int = 1


@dataclass
class Mission:
    """Toutes les infos lues dans UN message du webhook (= une mission d'un compte)."""

    message_id: int
    compte: str
    horodatage: float
    gold: int | None = None
    xp: int | None = None
    gems_gagnes: int | None = None
    gems_total: int | None = None
    gold_total: int | None = None
    level: int | None = None
    prestige: int | None = None
    duree_s: int | None = None
    difficulte: str | None = None
    zone: str | None = None
    drops: list[Drop] = field(default_factory=list)

    @property
    def est_safe(self) -> bool | None:
        """True si la zone est exactement « Safe », False sinon, None si inconnue."""
        return zone_est_safe(self.zone)


def zone_est_safe(zone: str | None) -> bool | None:
    """Comparaison EXACTE (sans tenir compte des majuscules) : « Unsafe » n'est pas « Safe »."""
    if zone is None or not zone.strip():
        return None
    return zone.strip().casefold() == "safe"


def nettoyer_valeur(texte: str | None) -> str:
    """Enlève les blocs de code ```...``` et les accents graves d'une valeur de champ."""
    if not texte:
        return ""
    texte = _RE_BLOC_CODE.sub("\n", texte)
    texte = texte.replace("`", "")
    return texte.strip()


def normaliser_nom_champ(nom: str | None) -> str:
    """« Player Stats: » -> « playerstats » (minuscules, lettres uniquement)."""
    return re.sub(r"[^a-z]", "", (nom or "").casefold())


def lire_nombre(texte: str | None) -> int | None:
    """« 37,807 » ou « 37.807 » -> 37807. Garde uniquement les chiffres."""
    if texte is None:
        return None
    chiffres = re.sub(r"\D", "", str(texte))
    if not chiffres:
        return None
    try:
        return int(chiffres)
    except ValueError:
        return None


def lire_duree(texte: str | None) -> int | None:
    """« 01:04 » -> 64 s ; « 1:02:03 » -> 3723 s ; « 1m 4s » -> 64 s."""
    if not texte:
        return None
    texte = texte.strip().casefold()
    if ":" in texte:
        morceaux = [lire_nombre(m) for m in texte.split(":")]
        if any(m is None for m in morceaux) or len(morceaux) > 3:
            return None
        total = 0
        for m in morceaux:
            total = total * 60 + int(m or 0)
        return total
    unites = re.findall(r"(\d+)\s*([hms])", texte)
    if unites:
        mult = {"h": 3600, "m": 60, "s": 1}
        return sum(int(n) * mult[u] for n, u in unites)
    return lire_nombre(texte)


def lire_paires(texte: str) -> dict[str, str]:
    """Transforme des lignes « Clé: valeur » en dictionnaire {« cle »: « valeur »}."""
    paires: dict[str, str] = {}
    for ligne in nettoyer_valeur(texte).splitlines():
        ligne = ligne.strip().lstrip("-•*· ").strip()
        if ":" not in ligne:
            continue
        cle, _, valeur = ligne.partition(":")
        cle_norm = normaliser_nom_champ(cle)
        if cle_norm and valeur.strip():
            paires[cle_norm] = valeur.strip()
    return paires


def lire_objet(ligne: str) -> Drop | None:
    """« Lucky (Common) » -> Drop("Lucky", "Common", 1). None si ce n'est pas un objet."""
    ligne = ligne.strip().lstrip("-•*· ").strip()
    if not ligne:
        return None
    m = _RE_OBJET.match(ligne)
    if not m:
        return None
    nom = m.group("nom").strip()
    rarete = m.group("rarete").strip()
    if not nom or not rarete:
        return None
    quantite = int(m.group("q1") or m.group("q2") or 1)
    return Drop(nom=nom, rarete=rarete, quantite=max(1, quantite))


def lire_drops(texte: str) -> tuple[int | None, int | None, int | None, list[Drop]]:
    """Lit le champ « Drops: ». Renvoie (gold, xp, gems, objets)."""
    gold = xp = gems = None
    objets: list[Drop] = []
    for ligne in nettoyer_valeur(texte).splitlines():
        ligne = ligne.strip()
        if not ligne:
            continue
        objet = lire_objet(ligne)
        if objet is not None:
            objets.append(objet)
            continue
        if ":" in ligne:
            cle, _, valeur = ligne.partition(":")
            cle_norm = normaliser_nom_champ(cle)
            if cle_norm == "gold":
                gold = lire_nombre(valeur)
            elif cle_norm in ("xp", "exp", "experience"):
                xp = lire_nombre(valeur)
            elif cle_norm in ("gems", "gem"):
                gems = lire_nombre(valeur)
    return gold, xp, gems, objets


def lire_champs(champs: Iterable[tuple[str, str]], message_id: int, horodatage: float) -> Mission | None:
    """Construit une Mission à partir des champs (nom, valeur) d'un embed.

    Renvoie None si l'embed n'a pas de champ « User: » (ce n'est pas un rapport de mission).
    """
    par_nom: dict[str, str] = {}
    for nom, valeur in champs:
        cle = normaliser_nom_champ(nom)
        if cle and cle not in par_nom:
            par_nom[cle] = valeur or ""

    compte = nettoyer_valeur(par_nom.get("user") or par_nom.get("username") or "")
    compte = compte.splitlines()[0].strip() if compte else ""
    if not compte:
        return None

    mission = Mission(message_id=int(message_id), compte=compte, horodatage=float(horodatage))

    stats = lire_paires(par_nom.get("playerstats", ""))
    mission.prestige = lire_nombre(stats.get("prestige"))
    mission.level = lire_nombre(stats.get("level") or stats.get("lvl"))
    mission.gems_total = lire_nombre(stats.get("gems"))
    mission.gold_total = lire_nombre(stats.get("gold"))

    infos = lire_paires(par_nom.get("missionstats", ""))
    mission.duree_s = lire_duree(infos.get("timetaken") or infos.get("time"))
    difficulte = infos.get("difficulty")
    mission.difficulte = difficulte.strip() if difficulte else None

    if "drops" in par_nom:
        gold, xp, gems, objets = lire_drops(par_nom["drops"])
        mission.gold, mission.xp, mission.gems_gagnes, mission.drops = gold, xp, gems, objets

    zone = nettoyer_valeur(par_nom.get("safetystatus") or par_nom.get("safety") or "")
    mission.zone = zone.splitlines()[0].strip() if zone else None
    return mission


def lire_embed_dict(embed: Mapping[str, Any], message_id: int, horodatage: float) -> Mission | None:
    """Lit un embed au format dictionnaire (format de l'API Discord)."""
    try:
        champs = [
            (str(c.get("name") or ""), str(c.get("value") or ""))
            for c in (embed.get("fields") or [])
            if isinstance(c, Mapping)
        ]
        return lire_champs(champs, message_id, horodatage)
    except Exception:  # sécurité : un embed bizarre ne doit jamais faire planter le bot
        return None


def lire_embeds(embeds: Iterable[Mapping[str, Any]], message_id: int, horodatage: float) -> Mission | None:
    """Prend le premier embed du message qui ressemble à un rapport de mission."""
    for embed in embeds:
        mission = lire_embed_dict(embed, message_id, horodatage)
        if mission is not None:
            return mission
    return None


def meme_compte(a: str | None, b: str | None) -> bool:
    """Compare deux usernames EN ENTIER (sans tenir compte des majuscules)."""
    if not a or not b:
        return False
    return a.strip().casefold() == b.strip().casefold()


def trouver_compte(nom: str | None, comptes: Iterable[str]) -> str | None:
    """Renvoie le nom configuré qui correspond exactement à `nom`, sinon None."""
    for compte in comptes:
        if meme_compte(nom, compte):
            return compte
    return None
