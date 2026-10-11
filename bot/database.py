"""Base de données SQLite : schéma, migrations et toutes les requêtes.

Tout ce qui doit survivre à un redémarrage est ici (missions, réglages, objectifs...).
"""

from __future__ import annotations

import json
import time
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import aiosqlite

from bot.parser import Drop, Mission

# Chaque entrée = une étape de migration. On n'enlève JAMAIS une étape, on en ajoute.
MIGRATIONS: list[str] = [
    # Version 1 : schéma initial
    """
    CREATE TABLE IF NOT EXISTS missions (
        message_id   INTEGER PRIMARY KEY,
        compte       TEXT    NOT NULL,
        horodatage   REAL    NOT NULL,
        gold         INTEGER,
        xp           INTEGER,
        gems_gagnes  INTEGER,
        gems_total   INTEGER,
        gold_total   INTEGER,
        level        INTEGER,
        prestige     INTEGER,
        duree_s      INTEGER,
        difficulte   TEXT,
        zone         TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_missions_compte_temps ON missions (compte COLLATE NOCASE, horodatage);
    CREATE INDEX IF NOT EXISTS idx_missions_temps ON missions (horodatage);

    CREATE TABLE IF NOT EXISTS drops (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        mission_id  INTEGER NOT NULL REFERENCES missions(message_id) ON DELETE CASCADE,
        compte      TEXT    NOT NULL,
        horodatage  REAL    NOT NULL,
        nom         TEXT    NOT NULL,
        rarete      TEXT    NOT NULL,
        quantite    INTEGER NOT NULL DEFAULT 1
    );
    CREATE INDEX IF NOT EXISTS idx_drops_compte_temps ON drops (compte COLLATE NOCASE, horodatage);
    CREATE INDEX IF NOT EXISTS idx_drops_mission ON drops (mission_id);

    CREATE TABLE IF NOT EXISTS evenements (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        compte      TEXT,
        type        TEXT NOT NULL,
        texte       TEXT NOT NULL,
        horodatage  REAL NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_evenements_compte_temps ON evenements (compte COLLATE NOCASE, horodatage);

    CREATE TABLE IF NOT EXISTS reglages (
        cle     TEXT PRIMARY KEY,
        valeur  TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS objectifs (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        compte         TEXT NOT NULL,
        type           TEXT NOT NULL,
        valeur_cible   INTEGER NOT NULL,
        valeur_depart  INTEGER NOT NULL DEFAULT 0,
        cree_le        REAL NOT NULL,
        atteint_le     REAL
    );

    CREATE TABLE IF NOT EXISTS ia_conversations (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        salon_id    INTEGER NOT NULL,
        role        TEXT NOT NULL,
        contenu     TEXT NOT NULL,
        horodatage  REAL NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_ia_salon ON ia_conversations (salon_id, id);

    CREATE TABLE IF NOT EXISTS osint_journal (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        utilisateur_id  INTEGER NOT NULL,
        commande        TEXT NOT NULL,
        cible           TEXT NOT NULL,
        resultat        TEXT NOT NULL,
        horodatage      REAL NOT NULL
    );
    """,
]

_COLONNES_MISSION = (
    "message_id, compte, horodatage, gold, xp, gems_gagnes, gems_total, gold_total, "
    "level, prestige, duree_s, difficulte, zone"
)


@dataclass
class Objectif:
    id: int
    compte: str
    type: str
    valeur_cible: int
    valeur_depart: int
    cree_le: float
    atteint_le: float | None


@dataclass
class Evenement:
    compte: str | None
    type: str
    texte: str
    horodatage: float


@dataclass
class DropEnregistre:
    compte: str
    horodatage: float
    nom: str
    rarete: str
    quantite: int


def _mission_depuis_ligne(ligne: Sequence[Any]) -> Mission:
    return Mission(
        message_id=ligne[0],
        compte=ligne[1],
        horodatage=ligne[2],
        gold=ligne[3],
        xp=ligne[4],
        gems_gagnes=ligne[5],
        gems_total=ligne[6],
        gold_total=ligne[7],
        level=ligne[8],
        prestige=ligne[9],
        duree_s=ligne[10],
        difficulte=ligne[11],
        zone=ligne[12],
    )


class Database:
    """Accès asynchrone à la base SQLite."""

    def __init__(self, chemin: Path | str) -> None:
        self.chemin = str(chemin)
        self._db: aiosqlite.Connection | None = None

    # ------------------------------------------------------------ connexion

    async def connecter(self) -> None:
        if self.chemin != ":memory:":
            Path(self.chemin).parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(self.chemin)
        await self._db.execute("PRAGMA foreign_keys = ON")
        await self._db.execute("PRAGMA journal_mode = WAL")
        await self._db.execute("PRAGMA synchronous = NORMAL")
        await self._migrer()

    async def fermer(self) -> None:
        if self._db is not None:
            await self._db.close()
            self._db = None

    @property
    def db(self) -> aiosqlite.Connection:
        if self._db is None:
            raise RuntimeError("La base n'est pas connectée.")
        return self._db

    async def _migrer(self) -> None:
        async with self.db.execute("PRAGMA user_version") as cur:
            ligne = await cur.fetchone()
        version = int(ligne[0]) if ligne else 0
        for numero, script in enumerate(MIGRATIONS, start=1):
            if numero > version:
                await self.db.executescript(script)
                await self.db.execute(f"PRAGMA user_version = {numero}")
        await self.db.commit()

    async def version_schema(self) -> int:
        async with self.db.execute("PRAGMA user_version") as cur:
            ligne = await cur.fetchone()
        return int(ligne[0]) if ligne else 0

    # ------------------------------------------------------------ missions

    async def ajouter_mission(self, m: Mission) -> bool:
        """Enregistre une mission. Renvoie False si ce message a DÉJÀ été compté."""
        cur = await self.db.execute(
            f"INSERT OR IGNORE INTO missions ({_COLONNES_MISSION}) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                m.message_id, m.compte, m.horodatage, m.gold, m.xp, m.gems_gagnes, m.gems_total,
                m.gold_total, m.level, m.prestige, m.duree_s, m.difficulte, m.zone,
            ),
        )
        nouvelle = cur.rowcount == 1
        await cur.close()
        if nouvelle and m.drops:
            await self.db.executemany(
                "INSERT INTO drops (mission_id, compte, horodatage, nom, rarete, quantite) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                [(m.message_id, m.compte, m.horodatage, d.nom, d.rarete, d.quantite) for d in m.drops],
            )
        await self.db.commit()
        return nouvelle

    async def mission_existe(self, message_id: int) -> bool:
        async with self.db.execute("SELECT 1 FROM missions WHERE message_id = ?", (message_id,)) as cur:
            return await cur.fetchone() is not None

    async def missions(
        self,
        compte: str | None = None,
        debut: float | None = None,
        fin: float | None = None,
        avec_drops: bool = False,
    ) -> list[Mission]:
        """Missions (triées par date) filtrées par compte et par période."""
        conditions, params = [], []
        if compte is not None:
            conditions.append("compte = ? COLLATE NOCASE")
            params.append(compte)
        if debut is not None:
            conditions.append("horodatage >= ?")
            params.append(debut)
        if fin is not None:
            conditions.append("horodatage <= ?")
            params.append(fin)
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        async with self.db.execute(
            f"SELECT {_COLONNES_MISSION} FROM missions {where} ORDER BY horodatage", params
        ) as cur:
            liste = [_mission_depuis_ligne(r) for r in await cur.fetchall()]
        if avec_drops and liste:
            await self._charger_drops(liste, compte, debut, fin)
        return liste

    async def _charger_drops(
        self, liste: list[Mission], compte: str | None, debut: float | None, fin: float | None
    ) -> None:
        par_id = {m.message_id: m for m in liste}
        for d in await self.drops(compte=compte, debut=debut, fin=fin, avec_id=True):
            mission = par_id.get(d[0])
            if mission is not None:
                mission.drops.append(Drop(d[1].nom, d[1].rarete, d[1].quantite))

    async def dernieres_missions(self, compte: str, n: int) -> list[Mission]:
        """Les `n` dernières missions d'un compte (de la plus ancienne à la plus récente)."""
        async with self.db.execute(
            f"SELECT {_COLONNES_MISSION} FROM missions WHERE compte = ? COLLATE NOCASE "
            "ORDER BY horodatage DESC LIMIT ?",
            (compte, n),
        ) as cur:
            lignes = await cur.fetchall()
        return [_mission_depuis_ligne(r) for r in reversed(lignes)]

    async def derniere_mission(self, compte: str) -> Mission | None:
        liste = await self.dernieres_missions(compte, 1)
        return liste[0] if liste else None

    async def derniere_mission_avant(self, compte: str, avant: float) -> Mission | None:
        async with self.db.execute(
            f"SELECT {_COLONNES_MISSION} FROM missions WHERE compte = ? COLLATE NOCASE "
            "AND horodatage < ? ORDER BY horodatage DESC LIMIT 1",
            (compte, avant),
        ) as cur:
            ligne = await cur.fetchone()
        return _mission_depuis_ligne(ligne) if ligne else None

    async def premiere_mission(self) -> float | None:
        async with self.db.execute("SELECT MIN(horodatage) FROM missions") as cur:
            ligne = await cur.fetchone()
        return ligne[0] if ligne and ligne[0] is not None else None

    async def comptes_vus(self) -> list[str]:
        async with self.db.execute("SELECT DISTINCT compte FROM missions ORDER BY compte") as cur:
            return [r[0] for r in await cur.fetchall()]

    async def nombre_missions(self) -> int:
        async with self.db.execute("SELECT COUNT(*) FROM missions") as cur:
            ligne = await cur.fetchone()
        return int(ligne[0]) if ligne else 0

    # ------------------------------------------------------------ drops

    async def drops(
        self,
        compte: str | None = None,
        raretes: Iterable[str] | None = None,
        debut: float | None = None,
        fin: float | None = None,
        limite: int | None = None,
        avec_id: bool = False,
    ) -> list[Any]:
        """Objets obtenus, du plus récent au plus ancien (sauf avec_id : ordre chronologique)."""
        conditions, params = [], []
        if compte is not None:
            conditions.append("compte = ? COLLATE NOCASE")
            params.append(compte)
        if raretes is not None:
            liste = [r.casefold() for r in raretes]
            if not liste:
                return []
            conditions.append(f"LOWER(rarete) IN ({','.join('?' * len(liste))})")
            params.extend(liste)
        if debut is not None:
            conditions.append("horodatage >= ?")
            params.append(debut)
        if fin is not None:
            conditions.append("horodatage <= ?")
            params.append(fin)
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        ordre = "ASC" if avec_id else "DESC"
        sql = (
            f"SELECT mission_id, compte, horodatage, nom, rarete, quantite FROM drops {where} "
            f"ORDER BY horodatage {ordre}, id {ordre}"
        )
        if limite:
            sql += f" LIMIT {int(limite)}"
        async with self.db.execute(sql, params) as cur:
            lignes = await cur.fetchall()
        resultat = [(r[0], DropEnregistre(r[1], r[2], r[3], r[4], r[5])) for r in lignes]
        return resultat if avec_id else [d for _, d in resultat]

    # ------------------------------------------------------------ événements

    async def ajouter_evenement(self, compte: str | None, type_: str, texte: str, horodatage: float | None = None) -> None:
        await self.db.execute(
            "INSERT INTO evenements (compte, type, texte, horodatage) VALUES (?, ?, ?, ?)",
            (compte, type_, texte, horodatage if horodatage is not None else time.time()),
        )
        await self.db.commit()

    async def evenements(self, compte: str | None = None, depuis: float | None = None, limite: int = 10) -> list[Evenement]:
        conditions, params = [], []
        if compte is not None:
            conditions.append("compte = ? COLLATE NOCASE")
            params.append(compte)
        if depuis is not None:
            conditions.append("horodatage >= ?")
            params.append(depuis)
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        async with self.db.execute(
            f"SELECT compte, type, texte, horodatage FROM evenements {where} "
            "ORDER BY horodatage DESC, id DESC LIMIT ?",
            (*params, limite),
        ) as cur:
            return [Evenement(*r) for r in await cur.fetchall()]

    # ------------------------------------------------------------ réglages

    async def lire_reglages(self) -> dict[str, Any]:
        resultat: dict[str, Any] = {}
        async with self.db.execute("SELECT cle, valeur FROM reglages") as cur:
            for cle, valeur in await cur.fetchall():
                try:
                    resultat[cle] = json.loads(valeur)
                except (json.JSONDecodeError, TypeError):
                    continue
        return resultat

    async def ecrire_reglage(self, cle: str, valeur: Any) -> None:
        await self.db.execute(
            "INSERT INTO reglages (cle, valeur) VALUES (?, ?) "
            "ON CONFLICT(cle) DO UPDATE SET valeur = excluded.valeur",
            (cle, json.dumps(valeur, ensure_ascii=False)),
        )
        await self.db.commit()

    async def effacer_reglages(self, garder_prefixe: str = "_") -> None:
        await self.db.execute(
            "DELETE FROM reglages WHERE substr(cle, 1, ?) != ?", (len(garder_prefixe), garder_prefixe)
        )
        await self.db.commit()

    # ------------------------------------------------------------ objectifs

    async def ajouter_objectif(self, compte: str, type_: str, cible: int, depart: int) -> int:
        cur = await self.db.execute(
            "INSERT INTO objectifs (compte, type, valeur_cible, valeur_depart, cree_le) VALUES (?, ?, ?, ?, ?)",
            (compte, type_, cible, depart, time.time()),
        )
        identifiant = cur.lastrowid
        await cur.close()
        await self.db.commit()
        return int(identifiant or 0)

    async def objectifs(self, actifs_seulement: bool = False) -> list[Objectif]:
        where = "WHERE atteint_le IS NULL" if actifs_seulement else ""
        async with self.db.execute(
            "SELECT id, compte, type, valeur_cible, valeur_depart, cree_le, atteint_le "
            f"FROM objectifs {where} ORDER BY id"
        ) as cur:
            return [Objectif(*r) for r in await cur.fetchall()]

    async def objectif_atteint(self, identifiant: int, quand: float) -> None:
        await self.db.execute("UPDATE objectifs SET atteint_le = ? WHERE id = ?", (quand, identifiant))
        await self.db.commit()

    async def supprimer_objectif(self, identifiant: int) -> bool:
        cur = await self.db.execute("DELETE FROM objectifs WHERE id = ?", (identifiant,))
        ok = cur.rowcount > 0
        await cur.close()
        await self.db.commit()
        return ok

    # ------------------------------------------------------------ IA

    async def ajouter_message_ia(self, salon_id: int, role: str, contenu: str) -> None:
        await self.db.execute(
            "INSERT INTO ia_conversations (salon_id, role, contenu, horodatage) VALUES (?, ?, ?, ?)",
            (salon_id, role, contenu, time.time()),
        )
        await self.db.commit()

    async def historique_ia(self, salon_id: int, n_messages: int) -> list[dict[str, str]]:
        async with self.db.execute(
            "SELECT role, contenu FROM ia_conversations WHERE salon_id = ? ORDER BY id DESC LIMIT ?",
            (salon_id, n_messages),
        ) as cur:
            lignes = await cur.fetchall()
        return [{"role": r, "content": c} for r, c in reversed(lignes)]

    async def effacer_conversation_ia(self, salon_id: int) -> None:
        await self.db.execute("DELETE FROM ia_conversations WHERE salon_id = ?", (salon_id,))
        await self.db.commit()

    # ------------------------------------------------------------ OSINT

    async def journaliser_osint(self, utilisateur_id: int, commande: str, cible: str, resultat: str) -> None:
        await self.db.execute(
            "INSERT INTO osint_journal (utilisateur_id, commande, cible, resultat, horodatage) VALUES (?, ?, ?, ?, ?)",
            (utilisateur_id, commande, cible[:200], resultat[:50], time.time()),
        )
        await self.db.commit()

    async def journal_osint(self, limite: int = 100) -> list[tuple[int, str, str, str, float]]:
        async with self.db.execute(
            "SELECT utilisateur_id, commande, cible, resultat, horodatage FROM osint_journal "
            "ORDER BY id DESC LIMIT ?",
            (limite,),
        ) as cur:
            return [tuple(r) for r in await cur.fetchall()]  # type: ignore[misc]

    # ------------------------------------------------------------ entretien

    async def purger(self, jours: int, maintenant: float | None = None) -> int:
        """Supprime les données plus vieilles que `jours` jours. Renvoie le nombre de missions supprimées."""
        if jours <= 0:
            return 0
        limite = (maintenant if maintenant is not None else time.time()) - jours * 86400
        cur = await self.db.execute("DELETE FROM missions WHERE horodatage < ?", (limite,))
        n = cur.rowcount
        await cur.close()
        await self.db.execute("DELETE FROM drops WHERE horodatage < ?", (limite,))
        await self.db.execute("DELETE FROM evenements WHERE horodatage < ?", (limite,))
        await self.db.execute("DELETE FROM ia_conversations WHERE horodatage < ?", (limite,))
        await self.db.execute("DELETE FROM osint_journal WHERE horodatage < ?", (limite,))
        await self.db.commit()
        return max(0, n)
