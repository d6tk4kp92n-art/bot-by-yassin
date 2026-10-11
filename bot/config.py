"""Configuration du bot : lecture du fichier .env et réglages par défaut.

Les secrets (token, clés d'API) viennent UNIQUEMENT du fichier .env.
Les réglages modifiables (comptes, délais, couleurs...) sont stockés en base
et ont une valeur par défaut définie ici.
"""

from __future__ import annotations

import copy
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from dotenv import dotenv_values

# Dossier racine du projet (celui qui contient "bot/")
RACINE = Path(__file__).resolve().parent.parent
DOSSIER_DATA = RACINE / "data"
DOSSIER_LOGS = DOSSIER_DATA / "logs"
CHEMIN_BASE = DOSSIER_DATA / "tekkit.db"

# Fuseau horaire utilisé pour "aujourd'hui", les rapports, etc.
FUSEAU = ZoneInfo("Europe/Brussels")

VERSION = "1.0.0"
USER_AGENT = f"TekkitWatch/{VERSION} (bot Discord personnel; usage defensif)"

# Ordre des raretés, de la plus faible à la plus forte (modifiable dans les réglages).
RARETES_DEFAUT: list[str] = [
    "Common",
    "Uncommon",
    "Rare",
    "Epic",
    "Legendary",
    "Mythic",
    "Secret",
    "Exotic",
]
# Noms alternatifs qui veulent dire la même chose.
ALIAS_RARETES: dict[str, str] = {"mythical": "Mythic"}

# Infos qu'on peut cocher dans le résumé : clé -> libellé affiché.
INFOS_RESUME: dict[str, str] = {
    "connexion": "🟢 Connexion",
    "zone": "🛡️ Zone",
    "niveau": "⭐ Niveau / prestige",
    "missions": "🎯 Missions",
    "gold": "💰 Gold",
    "xp": "✨ XP",
    "gems": "💎 Gems",
    "temps_moyen": "⏱️ Temps moyen par mission",
    "objets": "🎁 Objets",
    "estimation": "🔮 Estimation",
    "changements": "📜 Changements récents",
    "session": "🧮 Totaux de session",
    "bilan": "📊 Bilan",
}

FORMATS_RESUME: dict[str, str] = {
    "detaille": "Détaillé (un champ par compte)",
    "compact": "Compact (une ligne par compte)",
    "texte": "Texte copiable (bloc de code)",
}

# Palette de couleurs proposée dans les réglages.
PALETTE: dict[str, str] = {
    "auto": "Auto (vert / orange / rouge selon l'état)",
    "#5865F2": "Bleu Discord",
    "#57F287": "Vert",
    "#FEE75C": "Jaune",
    "#EB459E": "Rose",
    "#ED4245": "Rouge",
    "#9B59B6": "Violet",
    "#1ABC9C": "Turquoise",
    "#E67E22": "Orange",
    "#2C2F33": "Gris foncé",
}

SENSIBILITES: dict[str, str] = {
    "basse": "Basse (peu d'alertes)",
    "normale": "Normale",
    "haute": "Haute (beaucoup d'alertes)",
}

# Modèles Ollama conseillés (gratuits, open source, tournent sur processeur).
MODELE_IA_DEFAUT = "qwen3.5:4b"
MODELE_IA_LEGER = "qwen3.5:2b"

MODES_IA: dict[str, str] = {
    "leger": "Léger (économise le PC)",
    "equilibre": "Équilibré (réponses plus longues)",
}

NB_COMPTES_MAX = 10

# Valeurs par défaut de TOUS les réglages modifiables.
# Les clés qui commencent par "_" sont de l'état interne (pas remis à zéro).
DEFAUTS: dict[str, Any] = {
    # Comptes surveillés
    "comptes": ["abslt98", "yayaoui00"],
    # Surveillance
    "surveillance_active": True,
    "delai_absence_min": 3,
    # Résumé automatique
    "resume_auto": True,
    "resume_intervalle_min": 10,
    "resume_ping": False,
    "resume_supprimer_ancien": True,
    "resume_format": "detaille",
    "resume_infos": list(INFOS_RESUME.keys()),
    "resume_boutons": True,
    "couleur": "auto",
    # Calculs
    "periode_gains_min": 60,
    "estimation_heures": 6,
    # Rapports
    "rapport_quotidien": True,
    "rapport_hebdo": True,
    "rapport_heure": "21:00",
    # Alertes (chaque ping séparément)
    "ping_disparition": True,
    "message_retour": True,
    "ping_retour": False,
    "ping_zone": True,
    "ping_drop": True,
    "ping_anomalies": True,
    "ping_objectif": True,
    "rarete_min": "Legendary",
    "raretes": list(RARETES_DEFAUT),
    "sensibilite_anomalies": "normale",
    "salon_alertes": None,
    "salon_resumes": None,
    # Données
    "purge_jours": 90,
    # IA locale (Ollama)
    "ia_active": True,
    "ia_modele": MODELE_IA_DEFAUT,
    "ia_mode": "leger",
    "ia_utilisateurs": [],
    "ia_keep_alive_min": 5,
    "ia_limite_minute": 5,
    "ia_memoire": 6,
    # OSINT
    "osint_active": True,
    # État interne
    "_dernier_resume": None,
    "_dernier_rapport_jour": None,
    "_dernier_rapport_semaine": None,
    "_osint_avertis": [],
}


def defauts() -> dict[str, Any]:
    """Renvoie une copie neuve des réglages par défaut."""
    return copy.deepcopy(DEFAUTS)


def _lire(nom: str, fichier: dict[str, str | None]) -> str:
    """Variable d'environnement (Docker, Windows) en priorité, sinon la ligne du fichier .env."""
    return (os.environ.get(nom) or fichier.get(nom) or "").strip()


def _entier_env(nom: str, fichier: dict[str, str | None]) -> int | None:
    """Lit une variable qui doit être un nombre entier (ID Discord)."""
    valeur = _lire(nom, fichier)
    if not valeur:
        return None
    if not valeur.isdigit():
        raise ValueError(f"{nom} doit être un nombre (ID Discord), pas « {valeur} ».")
    return int(valeur)


@dataclass(frozen=True)
class Config:
    """Secrets et identifiants lus dans le fichier .env."""

    token: str
    owner_id: int
    webhook_channel_id: int
    ollama_url: str = "http://localhost:11434"
    virustotal_key: str | None = None
    urlscan_key: str | None = None

    @classmethod
    def depuis_env(cls, chemin_env: Path | None = None) -> Config:
        """Charge le fichier .env et vérifie que tout ce qui est obligatoire est là."""
        chemin = chemin_env or RACINE / ".env"
        fichier = dict(dotenv_values(chemin)) if chemin.exists() else {}
        token = _lire("DISCORD_TOKEN", fichier)
        manquants = []
        if not token:
            manquants.append("DISCORD_TOKEN")
        owner = _entier_env("OWNER_ID", fichier)
        if owner is None:
            manquants.append("OWNER_ID")
        salon = _entier_env("WEBHOOK_CHANNEL_ID", fichier)
        if salon is None:
            manquants.append("WEBHOOK_CHANNEL_ID")
        if manquants:
            raise ValueError(
                "Il manque dans le fichier .env : "
                + ", ".join(manquants)
                + ". Ouvre .env et remplis ces lignes (voir .env.example)."
            )
        assert owner is not None and salon is not None
        return cls(
            token=token,
            owner_id=owner,
            webhook_channel_id=salon,
            ollama_url=(_lire("OLLAMA_URL", fichier) or "http://localhost:11434").rstrip("/"),
            virustotal_key=_lire("VIRUSTOTAL_API_KEY", fichier) or None,
            urlscan_key=_lire("URLSCAN_API_KEY", fichier) or None,
        )

    def secrets(self) -> list[str]:
        """Liste des valeurs à ne jamais écrire dans les logs."""
        return [s for s in (self.token, self.virustotal_key, self.urlscan_key) if s]
