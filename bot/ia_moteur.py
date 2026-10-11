"""IA locale GRATUITE via Ollama (rien n'est envoyé sur internet).

- une seule génération à la fois (file d'attente) pour ne pas faire ramer Roblox ;
- le modèle se décharge tout seul après quelques minutes (keep_alive) ;
- réponses et contexte limités, nombre de threads limité ;
- outils (tool calling) pour lire les VRAIES stats, avec solution de secours si le modèle
  ne gère pas les outils : un résumé chiffré est ajouté avant la question.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

import aiohttp

from bot.calculs import PERIODES, est_rare, formater_duree
from bot.config import MODELE_IA_LEGER

log = logging.getLogger("tekkit.ia")

PROMPT_SYSTEME = """Tu es Tekkit, l'assistant du serveur Discord de farm Roblox (Attack on Titan: Revolution).
Règles :
- Réponds TOUJOURS en français, de façon concise et claire (listes courtes, pas de blabla).
- N'invente JAMAIS de chiffres. Pour toute question sur le farm (gold, XP, gems, missions, comptes,
  drops, estimations), utilise les outils fournis. Si tu n'as pas la donnée, dis que tu ne sais pas.
- Les nombres s'écrivent avec des espaces : 37 807.
- Refuse poliment toute recherche d'informations personnelles sur des particuliers
  (nom, adresse, téléphone, réseaux sociaux, plaque, identité derrière un pseudo...).
- Tu tournes en local sur le PC de l'utilisateur, gratuitement, avec Ollama."""

GENERATION: dict[str, str] = {
    "annonce": "Rédige une annonce Discord engageante (avec quelques emojis, titres en gras) sur le sujet suivant",
    "regles": "Rédige les règles d'un serveur Discord, numérotées, claires et bienveillantes, sur le thème suivant",
    "description": "Rédige une description courte et accrocheuse (pour un serveur, un salon ou un rôle Discord) sur le sujet suivant",
    "idees": "Propose une liste de 8 idées originales et concrètes sur le sujet suivant",
    "autre": "Rédige un texte prêt à copier-coller sur Discord, selon la demande suivante",
}

TYPES_GENERATION: dict[str, str] = {
    "annonce": "📢 Annonce",
    "regles": "📜 Règles du serveur",
    "description": "📝 Description",
    "idees": "💡 Idées",
    "autre": "✍️ Autre",
}


def parametres_mode(mode: str, nb_coeurs: int | None = None) -> dict[str, Any]:
    """Options Ollama selon le mode : « leger » économise le PC, « equilibre » répond plus longuement."""
    coeurs = nb_coeurs or os.cpu_count() or 4
    if mode == "equilibre":
        return {
            "num_ctx": 6144,
            "num_predict": 900,
            "num_thread": max(2, coeurs // 2),
            "temperature": 0.6,
        }
    return {
        "num_ctx": 4096,
        "num_predict": 450,
        "num_thread": max(2, coeurs // 4),
        "temperature": 0.5,
    }


def delai_mode(mode: str) -> float:
    return 240.0 if mode == "equilibre" else 150.0


# ====================================================================== erreurs


class ErreurIA(Exception):
    """Erreur avec un message gentil pour l'utilisateur."""


class OllamaAbsent(ErreurIA):
    def __init__(self, url: str) -> None:
        super().__init__(
            f"🤖 **Ollama ne répond pas** sur `{url}`.\n"
            "1. Installe Ollama (gratuit) : https://ollama.com/download\n"
            "2. Lance l'application **Ollama** (icône de lama près de l'horloge Windows).\n"
            "3. Réessaie dans quelques secondes.\n\n"
            "👀 La surveillance du farm continue normalement."
        )


class ModeleAbsent(ErreurIA):
    def __init__(self, modele: str) -> None:
        self.modele = modele
        super().__init__(
            f"🧠 Le modèle `{modele}` n'est pas encore téléchargé.\n"
            f"Ouvre un terminal (touche Windows → tape `cmd`) et lance :\n```\nollama pull {modele}\n```\n"
            f"PC modeste ? Prends plutôt le modèle léger : `ollama pull {MODELE_IA_LEGER}` "
            "puis choisis-le dans `/parametres` → 🤖 IA."
        )


class IATropLente(ErreurIA):
    def __init__(self, secondes: float) -> None:
        super().__init__(
            f"⏱️ L'IA a mis plus de {secondes:.0f} s à répondre, j'ai abandonné pour ne pas bloquer le PC.\n"
            f"Essaie une question plus courte, ou le modèle plus léger `{MODELE_IA_LEGER}` (`/parametres` → 🤖 IA)."
        )


class OutilsNonSupportes(Exception):
    """Le modèle choisi ne sait pas utiliser les outils."""


# ====================================================================== client HTTP


class ClientIA(Protocol):
    url: str

    async def tags(self, delai: float = 5) -> list[dict[str, Any]]: ...
    async def ps(self) -> list[dict[str, Any]]: ...
    async def chat(self, corps: dict[str, Any], delai: float) -> dict[str, Any]: ...
    async def fermer(self) -> None: ...


class ClientOllama:
    """Appels à l'API locale d'Ollama (/api/tags, /api/ps, /api/chat)."""

    def __init__(self, url: str) -> None:
        self.url = url.rstrip("/")
        self._session: aiohttp.ClientSession | None = None

    def _s(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def _requete(
        self, methode: str, chemin: str, delai: float, corps: Any = None
    ) -> dict[str, Any]:
        try:
            async with self._s().request(
                methode,
                f"{self.url}{chemin}",
                json=corps,
                timeout=aiohttp.ClientTimeout(total=delai),
            ) as rep:
                texte = await rep.text()
                try:
                    donnees = json.loads(texte) if texte else {}
                except json.JSONDecodeError:
                    donnees = {"error": texte[:300]}
                if rep.status >= 400:
                    erreur = str(donnees.get("error", f"HTTP {rep.status}"))
                    raise _ErreurHTTP(rep.status, erreur)
                return donnees
        except TimeoutError:
            raise IATropLente(delai) from None
        except aiohttp.ClientConnectionError:
            raise OllamaAbsent(self.url) from None

    async def tags(self, delai: float = 5) -> list[dict[str, Any]]:
        return list((await self._requete("GET", "/api/tags", delai)).get("models") or [])

    async def ps(self) -> list[dict[str, Any]]:
        return list((await self._requete("GET", "/api/ps", 5)).get("models") or [])

    async def chat(self, corps: dict[str, Any], delai: float) -> dict[str, Any]:
        return await self._requete("POST", "/api/chat", delai, corps)

    async def fermer(self) -> None:
        if self._session is not None and not self._session.closed:
            await self._session.close()


class _ErreurHTTP(Exception):
    def __init__(self, statut: int, message: str) -> None:
        super().__init__(message)
        self.statut = statut
        self.message = message


# ====================================================================== outils


class SourceDonnees(Protocol):
    """Ce dont les outils ont besoin (implémenté par bot.services.Services)."""

    reglages: Mapping[str, Any]

    async def etat_comptes(self, maintenant: float | None = None) -> Sequence[Any]: ...
    async def stats(
        self, periode: str, maintenant: float | None = None, comptes: list[str] | None = None
    ) -> Sequence[Any]: ...
    async def drops_rares(
        self, compte: str | None, rarete_min: str, periode: str = "tout", limite: int = 200
    ) -> Sequence[Any]: ...
    async def estimations(
        self, heures: float, maintenant: float | None = None
    ) -> Sequence[Any]: ...


def _outil(
    nom: str, description: str, proprietes: dict[str, Any], requis: list[str]
) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": nom,
            "description": description,
            "parameters": {"type": "object", "properties": proprietes, "required": requis},
        },
    }


PERIODE_PARAM = {
    "type": "string",
    "enum": list(PERIODES),
    "description": "session, aujourdhui, 7j, 30j ou tout",
}

DEFINITIONS_OUTILS: list[dict[str, Any]] = [
    _outil(
        "obtenir_etat_comptes",
        "État actuel de chaque compte : en ligne ou non, zone, niveau, gains récents, rythme par heure.",
        {},
        [],
    ),
    _outil(
        "obtenir_stats",
        "Statistiques d'un compte (ou de tous) sur une période : gold, XP, gems, missions, temps de jeu, disponibilité, records.",
        {
            "compte": {"type": "string", "description": "Nom du compte, ou 'tous'"},
            "periode": PERIODE_PARAM,
        },
        ["periode"],
    ),
    _outil(
        "obtenir_drops",
        "Objets rares obtenus (du plus récent au plus ancien).",
        {
            "compte": {"type": "string", "description": "Nom du compte, ou 'tous'"},
            "rarete_min": {
                "type": "string",
                "description": "Rareté minimum (Common, Uncommon, Rare, Epic, Legendary, Mythic, Secret, Exotic)",
            },
            "periode": PERIODE_PARAM,
        },
        [],
    ),
    _outil(
        "obtenir_estimation",
        "Gains estimés pour les prochaines heures au rythme des 30 dernières minutes.",
        {"heures": {"type": "number", "description": "Nombre d'heures (1 à 48)"}},
        ["heures"],
    ),
]


class OutilsIA:
    """Fonctions que l'IA peut appeler pour lire les vraies données du farm."""

    def __init__(self, source: SourceDonnees) -> None:
        self.source = source

    def _compte(self, compte: Any) -> list[str] | None:
        if not compte or str(compte).strip().casefold() in ("tous", "all", "*"):
            return None
        for c in self.source.reglages["comptes"]:
            if c.casefold() == str(compte).strip().casefold():
                return [c]
        return []

    @staticmethod
    def _periode(periode: Any) -> str:
        p = str(periode or "aujourdhui").strip().casefold().replace("'", "").replace(" ", "")
        alias = {
            "today": "aujourdhui",
            "jour": "aujourdhui",
            "semaine": "7j",
            "7jours": "7j",
            "mois": "30j",
            "30jours": "30j",
        }
        p = alias.get(p, p)
        return p if p in PERIODES else "aujourdhui"

    async def obtenir_etat_comptes(self) -> dict[str, Any]:
        resultat = []
        for e in await self.source.etat_comptes():
            d = e.derniere
            resultat.append(
                {
                    "compte": e.nom,
                    "en_ligne": e.en_ligne,
                    "zone": e.zone,
                    "niveau": d.level if d else None,
                    "prestige": d.prestige if d else None,
                    "gems_total": d.gems_total if d else None,
                    "gold_total": d.gold_total if d else None,
                    "derniere_mission_il_y_a": formater_duree(time.time() - d.horodatage)
                    if d
                    else None,
                    "periode_minutes": self.source.reglages["periode_gains_min"],
                    "missions_periode": e.gains.missions,
                    "gold_periode": e.gains.gold,
                    "xp_periode": e.gains.xp,
                    "gems_periode": e.gains.gems,
                    "gold_par_heure": round(e.rythme.gold_h) if e.rythme else None,
                    "gems_par_heure": round(e.rythme.gems_h) if e.rythme else None,
                }
            )
        return {"comptes": resultat}

    async def obtenir_stats(self, compte: Any = None, periode: Any = None) -> dict[str, Any]:
        comptes = self._compte(compte)
        if comptes == []:
            return {
                "erreur": f"compte inconnu : {compte}",
                "comptes_connus": list(self.source.reglages["comptes"]),
            }
        p = self._periode(periode)
        stats = await self.source.stats(p, comptes=comptes)
        return {
            "periode": PERIODES[p],
            "stats": [
                {
                    "compte": s.compte,
                    "missions": s.gains.missions,
                    "gold": s.gains.gold,
                    "xp": s.gains.xp,
                    "gems": s.gains.gems,
                    "gold_par_heure_de_jeu": round(s.par_heure(s.gains.gold)),
                    "temps_de_jeu": formater_duree(s.temps_actif_s),
                    "disponibilite_pourcent": round(s.disponibilite),
                    "duree_moyenne_mission": formater_duree(s.gains.duree_moyenne_s),
                    "record_gold_une_mission": s.gains.record_gold,
                    "meilleure_heure": f"{s.meilleure_heure[0]} h" if s.meilleure_heure else None,
                    "objets_par_rarete": dict(s.gains.objets),
                }
                for s in stats
            ],
        }

    async def obtenir_drops(
        self, compte: Any = None, rarete_min: Any = None, periode: Any = None
    ) -> dict[str, Any]:
        comptes = self._compte(compte)
        if comptes == []:
            return {"erreur": f"compte inconnu : {compte}"}
        raretes = list(self.source.reglages["raretes"])
        minimum = str(rarete_min or self.source.reglages["rarete_min"])
        if not est_rare(minimum, minimum, raretes):
            minimum = raretes[0] if raretes else "Common"
        p = self._periode(periode or "7j")
        drops = await self.source.drops_rares(
            comptes[0] if comptes else None, minimum, p, limite=30
        )
        return {
            "periode": PERIODES[p],
            "rarete_min": minimum,
            "nombre": len(drops),
            "drops": [
                {
                    "compte": d.compte,
                    "objet": d.nom,
                    "rarete": d.rarete,
                    "quantite": d.quantite,
                    "il_y_a": formater_duree(time.time() - d.horodatage),
                }
                for d in drops
            ],
        }

    async def obtenir_estimation(self, heures: Any = 6) -> dict[str, Any]:
        try:
            h = max(1.0, min(48.0, float(heures)))
        except (TypeError, ValueError):
            h = 6.0
        resultat = []
        for e in await self.source.estimations(h):
            resultat.append(
                {
                    "compte": e.nom,
                    "en_ligne": e.en_ligne,
                    "estimation": None
                    if e.estimation is None
                    else {
                        "gold": e.estimation.gold,
                        "xp": e.estimation.xp,
                        "gems": e.estimation.gems,
                        "missions": e.estimation.missions,
                    },
                }
            )
        return {"heures": h, "rythme_base_sur": "30 dernières minutes", "comptes": resultat}

    async def executer(self, nom: str, arguments: Mapping[str, Any] | str | None) -> dict[str, Any]:
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments) if arguments.strip() else {}
            except json.JSONDecodeError:
                arguments = {}
        args = dict(arguments or {})
        fonctions: dict[str, Callable[..., Awaitable[dict[str, Any]]]] = {
            "obtenir_etat_comptes": self.obtenir_etat_comptes,
            "obtenir_stats": self.obtenir_stats,
            "obtenir_drops": self.obtenir_drops,
            "obtenir_estimation": self.obtenir_estimation,
        }
        fonction = fonctions.get(nom)
        if fonction is None:
            return {"erreur": f"outil inconnu : {nom}"}
        accepte = set(fonction.__code__.co_varnames[1 : fonction.__code__.co_argcount])
        try:
            return await fonction(**{k: v for k, v in args.items() if k in accepte})
        except Exception as exc:  # un outil ne doit jamais faire planter la réponse
            log.exception("Erreur dans l'outil %s", nom)
            return {"erreur": f"impossible de lire les données ({type(exc).__name__})"}

    async def contexte_compact(self) -> str:
        """Solution de secours : résumé chiffré des stats, ajouté avant la question."""
        etat = await self.obtenir_etat_comptes()
        jour = await self.obtenir_stats("tous", "aujourdhui")
        return (
            "Données actuelles du farm (JSON, à utiliser pour répondre, ne pas inventer d'autres chiffres) :\n"
            + json.dumps(
                {"etat": etat["comptes"], "aujourdhui": jour["stats"]},
                ensure_ascii=False,
                separators=(",", ":"),
            )
        )


# ====================================================================== moteur


@dataclass
class ReponseIA:
    texte: str
    duree_s: float
    outils: list[str] = field(default_factory=list)
    secours: bool = False


@dataclass
class StatutIA:
    joignable: bool
    modeles: list[str]
    modele_choisi: str
    modele_installe: bool
    charge: bool
    ram_octets: int | None
    derniere_duree_s: float | None
    en_attente: int


class MoteurIA:
    def __init__(self, client: ClientIA, reglages: Mapping[str, Any], outils: OutilsIA) -> None:
        self.client = client
        self.reglages = reglages
        self.outils = outils
        self._verrou = asyncio.Lock()  # UNE SEULE génération à la fois
        self._en_attente = 0
        self._requetes: dict[int, deque[float]] = defaultdict(deque)
        self.derniere_duree_s: float | None = None
        self.generations_en_cours = 0  # pour les tests : ne doit jamais dépasser 1

    # ------------------------------------------------------------ accès

    def autorise(self, utilisateur_id: int, proprietaire_id: int) -> bool:
        return utilisateur_id == proprietaire_id or utilisateur_id in {
            int(u) for u in self.reglages["ia_utilisateurs"]
        }

    def limite_atteinte(self, utilisateur_id: int, maintenant: float | None = None) -> bool:
        """Max N questions par minute et par utilisateur. Enregistre la question si elle passe."""
        maintenant = maintenant or time.time()
        file = self._requetes[utilisateur_id]
        while file and maintenant - file[0] > 60:
            file.popleft()
        if len(file) >= int(self.reglages["ia_limite_minute"]):
            return True
        file.append(maintenant)
        return False

    @property
    def en_attente(self) -> int:
        return self._en_attente

    # ------------------------------------------------------------ appels

    def _corps(self, messages: list[dict[str, Any]], outils: bool) -> dict[str, Any]:
        corps: dict[str, Any] = {
            "model": self.reglages["ia_modele"],
            "messages": messages,
            "stream": False,
            "keep_alive": f"{int(self.reglages['ia_keep_alive_min'])}m",
            "options": parametres_mode(str(self.reglages["ia_mode"])),
            "think": False,  # pas de « réflexion » interminable sur processeur
        }
        if outils:
            corps["tools"] = DEFINITIONS_OUTILS
        return corps

    async def _chat(self, messages: list[dict[str, Any]], outils: bool) -> dict[str, Any]:
        corps = self._corps(messages, outils)
        delai = delai_mode(str(self.reglages["ia_mode"]))
        try:
            return await self.client.chat(corps, delai)
        except _ErreurHTTP as exc:
            message = exc.message.casefold()
            if "not found" in message or exc.statut == 404:
                raise ModeleAbsent(str(self.reglages["ia_modele"])) from None
            if "does not support tools" in message:
                raise OutilsNonSupportes() from None
            if "thinking" in message:  # vieux modèle/Ollama : on réessaie sans l'option « think »
                corps.pop("think", None)
                try:
                    return await self.client.chat(corps, delai)
                except _ErreurHTTP as exc2:
                    if "does not support tools" in exc2.message.casefold():
                        raise OutilsNonSupportes() from None
                    raise ErreurIA(
                        f"🤖 Ollama a renvoyé une erreur : {exc2.message[:300]}"
                    ) from None
            raise ErreurIA(f"🤖 Ollama a renvoyé une erreur : {exc.message[:300]}") from None

    async def _dans_la_file(
        self,
        travail: Callable[[], Awaitable[Any]],
        sur_attente: Callable[[int], Awaitable[None]] | None,
    ) -> Any:
        """Exécute `travail` quand c'est notre tour. Prévient de la position dans la file."""
        position = self._en_attente + (1 if self._verrou.locked() else 0)
        self._en_attente += 1
        try:
            if position > 0 and sur_attente is not None:
                try:
                    await sur_attente(position)
                except Exception:
                    log.debug("Impossible d'afficher la position dans la file")
            await self._verrou.acquire()
        finally:
            self._en_attente -= 1  # même si la demande est annulée pendant l'attente
        self.generations_en_cours += 1
        debut = time.monotonic()
        try:
            return await travail()
        finally:
            self.generations_en_cours -= 1
            self.derniere_duree_s = time.monotonic() - debut
            self._verrou.release()

    async def repondre(
        self,
        question: str,
        historique: Sequence[Mapping[str, str]] = (),
        sur_attente: Callable[[int], Awaitable[None]] | None = None,
    ) -> ReponseIA:
        """Répond à une question en utilisant les outils (ou la solution de secours)."""

        async def travail() -> ReponseIA:
            debut = time.monotonic()
            messages: list[dict[str, Any]] = [{"role": "system", "content": PROMPT_SYSTEME}]
            messages += [{"role": m["role"], "content": m["content"]} for m in historique]
            messages.append({"role": "user", "content": question})
            utilises: list[str] = []
            try:
                for _ in range(4):  # max 3 tours d'outils puis une réponse
                    rep = await self._chat(messages, outils=True)
                    message = rep.get("message") or {}
                    appels = message.get("tool_calls") or []
                    if not appels:
                        return ReponseIA(
                            _nettoyer(message.get("content", "")),
                            time.monotonic() - debut,
                            utilises,
                        )
                    messages.append(
                        {
                            "role": "assistant",
                            "content": message.get("content", ""),
                            "tool_calls": appels,
                        }
                    )
                    for appel in appels[:4]:
                        fonction = appel.get("function") or {}
                        nom = str(fonction.get("name", ""))
                        resultat = await self.outils.executer(nom, fonction.get("arguments"))
                        utilises.append(nom)
                        messages.append(
                            {
                                "role": "tool",
                                "tool_name": nom,
                                "content": json.dumps(resultat, ensure_ascii=False, default=str)[
                                    :6000
                                ],
                            }
                        )
                # Trop de tours : on demande une réponse finale sans outils
                rep = await self._chat(messages, outils=False)
                return ReponseIA(
                    _nettoyer((rep.get("message") or {}).get("content", "")),
                    time.monotonic() - debut,
                    utilises,
                )
            except OutilsNonSupportes:
                # Solution de secours : les chiffres sont injectés directement avant la question
                contexte = await self.outils.contexte_compact()
                messages = messages[: len(historique) + 1]
                messages.append({"role": "user", "content": f"{contexte}\n\nQuestion : {question}"})
                rep = await self._chat(messages, outils=False)
                return ReponseIA(
                    _nettoyer((rep.get("message") or {}).get("content", "")),
                    time.monotonic() - debut,
                    secours=True,
                )

        return await self._dans_la_file(travail, sur_attente)

    async def generer(
        self, type_: str, sujet: str, sur_attente: Callable[[int], Awaitable[None]] | None = None
    ) -> ReponseIA:
        """Génère un texte prêt à copier (annonce, règles...)."""
        consigne = GENERATION.get(type_, GENERATION["autre"])

        async def travail() -> ReponseIA:
            debut = time.monotonic()
            messages = [
                {
                    "role": "system",
                    "content": PROMPT_SYSTEME
                    + "\nPour les textes à générer, donne directement le texte final, sans introduction.",
                },
                {"role": "user", "content": f"{consigne} : {sujet}"},
            ]
            rep = await self._chat(messages, outils=False)
            return ReponseIA(
                _nettoyer((rep.get("message") or {}).get("content", "")), time.monotonic() - debut
            )

        return await self._dans_la_file(travail, sur_attente)

    # ------------------------------------------------------------ statut

    async def modeles_installes(self) -> list[str]:
        """Liste rapide (2 s max : le panneau doit répondre à Discord en moins de 3 s)."""
        try:
            return sorted(
                str(m.get("name") or m.get("model")) for m in await self.client.tags(delai=2)
            )
        except ErreurIA:
            return []

    async def statut(self) -> StatutIA:
        choisi = str(self.reglages["ia_modele"])
        try:
            modeles = sorted(str(m.get("name") or m.get("model")) for m in await self.client.tags())
            charges = await self.client.ps()
            joignable = True
        except ErreurIA:
            modeles, charges, joignable = [], [], False
        actif = next(
            (m for m in charges if _meme_modele(str(m.get("name") or m.get("model")), choisi)), None
        )
        return StatutIA(
            joignable=joignable,
            modeles=modeles,
            modele_choisi=choisi,
            modele_installe=any(_meme_modele(m, choisi) for m in modeles),
            charge=actif is not None,
            ram_octets=int(actif.get("size") or 0) if actif else None,
            derniere_duree_s=self.derniere_duree_s,
            en_attente=self._en_attente + (1 if self._verrou.locked() else 0),
        )


def _meme_modele(a: str, b: str) -> bool:
    """« qwen3.5:4b » == « qwen3.5:4b » ; « llama3 » == « llama3:latest »."""

    def norm(x: str) -> str:
        return x if ":" in x else f"{x}:latest"

    return norm(a.strip()) == norm(b.strip())


def _nettoyer(texte: str) -> str:
    """Enlève un éventuel bloc <think>...</think> et les espaces superflus."""
    texte = texte or ""
    while "<think>" in texte and "</think>" in texte:
        debut, fin = texte.index("<think>"), texte.index("</think>") + len("</think>")
        texte = texte[:debut] + texte[fin:]
    texte = texte.strip()
    return texte or "🤔 Je n'ai pas de réponse à donner."
