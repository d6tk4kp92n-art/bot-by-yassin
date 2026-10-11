"""OSINT 100 % légal (Belgique / RGPD) : infrastructures, liens, entreprises, MES données.

JAMAIS de recherche sur des personnes privées. Les contrôles de périmètre sont faits
AVANT tout appel réseau. Tous les appels passent par la classe `Http` (simulée dans les tests).
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import html
import io
import ipaddress
import re
import socket
import ssl
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol
from urllib.parse import urljoin, urlsplit

import aiohttp

from bot.config import USER_AGENT

# ====================================================================== périmètre


class HorsPerimetre(Exception):
    """Requête refusée : elle sort du périmètre légal du module."""


_RE_EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[a-z]{2,}", re.IGNORECASE)
_RE_TELEPHONE = re.compile(r"^(?:\+|00)?[\d\s./()-]{9,}$")
_RE_PLAQUE = re.compile(r"^(?:\d-?[A-Z]{3}-?\d{3}|[A-Z]{3}-?\d{3})$", re.IGNORECASE)
_RE_PSEUDO = re.compile(r"^@\w{2,}$")
_RE_DOMAINE = re.compile(r"^(?=.{1,253}$)(?!-)(?:[a-z0-9-]{1,63}(?<!-)\.)+[a-z]{2,63}$")

# Réseaux sociaux : un lien vers un PROFIL est hors périmètre (pas de profilage de personnes)
RESEAUX_SOCIAUX = (
    "facebook.com", "fb.com", "instagram.com", "tiktok.com", "twitter.com", "x.com", "linkedin.com",
    "snapchat.com", "threads.net", "reddit.com", "pinterest.com", "vk.com", "onlyfans.com",
    "twitch.tv", "youtube.com", "github.com", "steamcommunity.com", "roblox.com", "discord.com",
    "discord.gg", "t.me", "telegram.me", "bsky.app", "mastodon.social",
)

MESSAGE_PERSONNES = (
    "🚫 **Hors périmètre** : ce module ne fait **aucune** recherche sur des personnes "
    "(nom, e-mail, téléphone, adresse, plaque, pseudo, profil de réseau social). "
    "Uniquement : domaines, adresses IP publiques, liens, entreprises (BCE) et tes propres données."
)


def detecter_donnees_personnelles(texte: str) -> str | None:
    """Renvoie la raison si le texte ressemble à une donnée personnelle, sinon None."""
    t = texte.strip()
    if _RE_EMAIL.search(t):
        return "adresse e-mail"
    if _RE_PSEUDO.match(t):
        return "pseudo"
    if _RE_PLAQUE.match(t.replace(" ", "")):
        return "plaque d'immatriculation"
    chiffres = re.sub(r"\D", "", t)
    numero = numero_bce(t)
    if numero is not None and numero_bce_valide(numero):
        return None  # c'est un numéro d'entreprise, pas un téléphone
    if _RE_TELEPHONE.match(t) and 9 <= len(chiffres) <= 15:
        return "numéro de téléphone"
    return None


def _refuser_personnel(texte: str) -> None:
    raison = detecter_donnees_personnelles(texte)
    if raison:
        raise HorsPerimetre(f"{MESSAGE_PERSONNES}\n\n(Détecté : {raison}.)")


def valider_domaine(texte: str) -> str:
    """« https://www.Example.com/page » -> « www.example.com ». Refuse ce qui n'est pas un domaine."""
    _refuser_personnel(texte)
    brut = texte.strip()
    if "://" in brut:
        brut = urlsplit(brut).hostname or ""
    brut = brut.split("/")[0].split(":")[0].strip().rstrip(".").lower()
    try:
        brut = brut.encode("idna").decode("ascii")
    except UnicodeError:
        raise HorsPerimetre("Ce nom de domaine n'est pas valide.") from None
    try:
        ipaddress.ip_address(brut)
        raise HorsPerimetre("C'est une adresse IP : utilise `/osint ip`.")
    except ValueError:
        pass
    if not _RE_DOMAINE.match(brut):
        raise HorsPerimetre("Ce n'est pas un nom de domaine valide (exemple : `exemple.be`).")
    return brut


def ip_publique(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return not (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast
                or ip.is_reserved or ip.is_unspecified)


def valider_ip(texte: str) -> str:
    try:
        ip = ipaddress.ip_address(texte.strip())
    except ValueError:
        raise HorsPerimetre("Ce n'est pas une adresse IP valide (exemple : `8.8.8.8`).") from None
    if not ip_publique(ip):
        raise HorsPerimetre("Adresse IP privée ou réservée (réseau local) : rien de public à analyser.")
    return str(ip)


def est_profil_social(hote: str, chemin: str) -> bool:
    hote = hote.lower().removeprefix("www.").removeprefix("m.")
    if not any(hote == r or hote.endswith("." + r) for r in RESEAUX_SOCIAUX):
        return False
    morceaux = [m for m in chemin.split("/") if m]
    return bool(morceaux)  # la page d'accueil du réseau est OK, un profil/chemin ne l'est pas


def valider_url(texte: str) -> str:
    if "://" not in texte:
        _refuser_personnel(texte)
    url = texte.strip()
    if not re.match(r"^https?://", url, re.IGNORECASE):
        url = "http://" + url
    parties = urlsplit(url)
    if parties.scheme.lower() not in ("http", "https") or not parties.hostname:
        raise HorsPerimetre("Lien invalide : il doit commencer par http:// ou https://.")
    if est_profil_social(parties.hostname, parties.path):
        raise HorsPerimetre(f"{MESSAGE_PERSONNES}\n\n(Détecté : profil de réseau social.)")
    try:
        ip = ipaddress.ip_address(parties.hostname)
        if not ip_publique(ip):
            raise HorsPerimetre("Lien vers une adresse privée (réseau local) : refusé par sécurité.")
    except ValueError:
        if parties.hostname.lower() in ("localhost",) or parties.hostname.lower().endswith(".local"):
            raise HorsPerimetre("Lien vers le réseau local : refusé par sécurité.") from None
    return url


def numero_bce(texte: str) -> str | None:
    """« BE 0403.170.701 » ou « 403170701 » -> « 0403170701 ». None si ce n'est pas un numéro."""
    compact = re.sub(r"[\s.\-]", "", texte.strip()).upper().removeprefix("BE")
    if re.fullmatch(r"\d{9}", compact):
        compact = "0" + compact
    return compact if re.fullmatch(r"[01]\d{9}", compact) else None


def numero_bce_valide(numero: str) -> bool:
    """Contrôle modulo 97 des numéros d'entreprise belges."""
    if not re.fullmatch(r"[01]\d{9}", numero):
        return False
    return 97 - (int(numero[:8]) % 97) == int(numero[8:])


def valider_entreprise(texte: str) -> tuple[str, str]:
    """Renvoie ("numero", "0403170701") ou ("nom", "colruyt")."""
    texte = texte.strip()
    numero = numero_bce(texte)
    if numero is not None:
        if not numero_bce_valide(numero):
            raise HorsPerimetre("Ce numéro d'entreprise n'est pas valide (contrôle modulo 97).")
        return "numero", numero
    _refuser_personnel(texte)
    if len(texte) < 2 or len(texte) > 100:
        raise HorsPerimetre("Donne un numéro d'entreprise ou une dénomination (2 à 100 caractères).")
    return "nom", texte


def formater_bce(numero: str) -> str:
    return f"{numero[:4]}.{numero[4:7]}.{numero[7:]}"


# ====================================================================== HTTP


class ClientHttp(Protocol):
    async def get_json(self, url: str, params: dict[str, str] | None = None, headers: dict[str, str] | None = None) -> tuple[int, Any]: ...
    async def get_text(self, url: str, params: dict[str, str] | None = None, headers: dict[str, str] | None = None) -> tuple[int, str]: ...
    async def post_json(self, url: str, donnees: dict[str, Any], headers: dict[str, str] | None = None, formulaire: bool = False) -> tuple[int, Any]: ...
    async def sans_redirection(self, url: str) -> tuple[int, str | None]: ...
    async def resoudre(self, hote: str) -> list[str]: ...
    async def certificat(self, hote: str) -> dict[str, Any]: ...
    async def whois(self, serveur: str, requete: str) -> str: ...


class Http:
    """Vrais appels réseau : timeouts partout, User-Agent honnête, 1 requête/s max par site."""

    def __init__(self, delai: float = 15.0) -> None:
        self.delai = delai
        self._session: aiohttp.ClientSession | None = None
        self._derniers: dict[str, float] = {}
        self._verrou = asyncio.Lock()

    def _s(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={"User-Agent": USER_AGENT}, timeout=aiohttp.ClientTimeout(total=self.delai)
            )
        return self._session

    async def _politesse(self, url: str) -> None:
        """Respecte les limites des API : au moins 1 s entre deux appels au même site."""
        hote = urlsplit(url).hostname or ""
        async with self._verrou:
            attente = 1.0 - (time.monotonic() - self._derniers.get(hote, 0.0))
            if attente > 0:
                await asyncio.sleep(attente)
            self._derniers[hote] = time.monotonic()

    async def get_json(self, url: str, params: dict[str, str] | None = None, headers: dict[str, str] | None = None) -> tuple[int, Any]:
        await self._politesse(url)
        async with self._s().get(url, params=params, headers=headers) as rep:
            try:
                return rep.status, await rep.json(content_type=None)
            except (ValueError, aiohttp.ContentTypeError):
                return rep.status, None

    async def get_text(self, url: str, params: dict[str, str] | None = None, headers: dict[str, str] | None = None) -> tuple[int, str]:
        await self._politesse(url)
        async with self._s().get(url, params=params, headers=headers) as rep:
            return rep.status, await rep.text(errors="replace")

    async def post_json(self, url: str, donnees: dict[str, Any], headers: dict[str, str] | None = None, formulaire: bool = False) -> tuple[int, Any]:
        await self._politesse(url)
        kwargs: dict[str, Any] = {"data": donnees} if formulaire else {"json": donnees}
        async with self._s().post(url, headers=headers, **kwargs) as rep:
            try:
                return rep.status, await rep.json(content_type=None)
            except (ValueError, aiohttp.ContentTypeError):
                return rep.status, None

    async def sans_redirection(self, url: str) -> tuple[int, str | None]:
        await self._politesse(url)
        async with self._s().get(url, allow_redirects=False) as rep:
            return rep.status, rep.headers.get("Location")

    async def resoudre(self, hote: str) -> list[str]:
        infos = await asyncio.get_running_loop().getaddrinfo(hote, None, proto=socket.IPPROTO_TCP)
        return sorted({i[4][0] for i in infos})

    async def certificat(self, hote: str) -> dict[str, Any]:
        contexte = ssl.create_default_context()
        try:
            _lecteur, ecrivain = await asyncio.wait_for(
                asyncio.open_connection(hote, 443, ssl=contexte, server_hostname=hote), timeout=self.delai
            )
        except ssl.SSLCertVerificationError as exc:
            return {"erreur": exc.verify_message or "certificat invalide"}
        try:
            return dict(ecrivain.get_extra_info("peercert") or {})
        finally:
            ecrivain.close()

    async def whois(self, serveur: str, requete: str) -> str:
        lecteur, ecrivain = await asyncio.wait_for(asyncio.open_connection(serveur, 43), timeout=self.delai)
        try:
            ecrivain.write((requete + "\r\n").encode("idna"))
            await ecrivain.drain()
            donnees = await asyncio.wait_for(lecteur.read(200_000), timeout=self.delai)
            return donnees.decode("utf-8", errors="replace")
        finally:
            ecrivain.close()

    async def fermer(self) -> None:
        if self._session is not None and not self._session.closed:
            await self._session.close()


# ====================================================================== résultats


@dataclass
class Resultat:
    """Résultat d'une recherche OSINT, prêt à être affiché."""

    titre: str
    champs: list[tuple[str, str]] = field(default_factory=list)
    niveau: str = "info"  # info, vert, orange, rouge
    note: str | None = None


# ====================================================================== service


class ServiceOSINT:
    def __init__(self, http: ClientHttp, virustotal_key: str | None = None, urlscan_key: str | None = None) -> None:
        self.http = http
        self.vt_key = virustotal_key
        self.urlscan_key = urlscan_key

    # ------------------------------------------------------------ domaine

    async def domaine(self, cible: str) -> Resultat:
        nom = valider_domaine(cible)
        r = Resultat(titre=f"🌐 Domaine · {nom}")
        taches = await asyncio.gather(
            self._whois(nom), self._dns(nom), self._ssl(nom), self._archive(nom), return_exceptions=True
        )
        noms = ("📇 WHOIS", "🧭 DNS", "🔒 Certificat SSL", "🏛️ Archive.org")
        for titre, valeur in zip(noms, taches, strict=True):
            if isinstance(valeur, BaseException):
                r.champs.append((titre, f"Indisponible ({type(valeur).__name__})"))
            else:
                r.champs.append((titre, valeur))
        return r

    async def _whois(self, nom: str) -> str:
        statut, donnees = await self.http.get_json(f"https://rdap.org/domain/{nom}")
        if statut == 200 and isinstance(donnees, dict):
            return lire_rdap(donnees)
        # Pas de RDAP (ex. .be) : WHOIS classique, uniquement registrar et dates
        texte = await self.http.whois("whois.iana.org", nom.rsplit(".", 1)[-1])
        serveur = next((ligne.split(":", 1)[1].strip() for ligne in texte.splitlines()
                        if ligne.lower().startswith(("refer:", "whois:"))), None)
        if not serveur:
            return "Aucune information WHOIS publique."
        return lire_whois_texte(await self.http.whois(serveur, nom))

    async def _dns(self, nom: str) -> str:
        lignes = []
        for type_ in ("A", "AAAA", "MX", "NS", "TXT"):
            statut, donnees = await self.http.get_json("https://dns.google/resolve", params={"name": nom, "type": type_})
            if statut != 200 or not isinstance(donnees, dict):
                lignes.append(f"**{type_}** : indisponible")
                continue
            valeurs = [str(a.get("data", "")).strip('"') for a in donnees.get("Answer") or [] if a.get("data")]
            if valeurs:
                texte = ", ".join(v[:80] for v in valeurs[:4]) + (f" (+{len(valeurs) - 4})" if len(valeurs) > 4 else "")
                lignes.append(f"**{type_}** : `{texte}`")
            else:
                lignes.append(f"**{type_}** : —")
        return "\n".join(lignes)

    async def _ssl(self, nom: str) -> str:
        cert = await self.http.certificat(nom)
        if not cert:
            return "Pas de certificat (pas de HTTPS ?)"
        if "erreur" in cert:
            return f"❌ Certificat invalide : {cert['erreur']}"
        emetteur = dict(x[0] for x in cert.get("issuer", ()) if x)
        fin = cert.get("notAfter")
        lignes = [f"Émetteur : **{emetteur.get('organizationName') or emetteur.get('commonName', '?')}**"]
        if fin:
            expiration = ssl.cert_time_to_seconds(fin)
            jours = int((expiration - time.time()) // 86400)
            alerte = " ⚠️" if jours < 15 else ""
            lignes.append(f"Expire le {datetime.fromtimestamp(expiration):%d/%m/%Y} (dans {jours} j){alerte}")
        noms = [v for k, v in cert.get("subjectAltName", ()) if k == "DNS"]
        if noms:
            lignes.append(f"Couvre {len(noms)} nom(s) : `{', '.join(noms[:3])}`" + (" …" if len(noms) > 3 else ""))
        return "\n".join(lignes)

    async def _archive(self, nom: str) -> str:
        statut, donnees = await self.http.get_json("https://archive.org/wayback/available", params={"url": nom})
        proche = (donnees or {}).get("archived_snapshots", {}).get("closest") if statut == 200 and isinstance(donnees, dict) else None
        statut2, premiere = await self.http.get_json(
            "https://web.archive.org/cdx/search/cdx", params={"url": nom, "limit": "1", "output": "json"}
        )
        lignes = []
        if statut2 == 200 and isinstance(premiere, list) and len(premiere) > 1:
            lignes.append(f"Première capture : {_date_wayback(premiere[1][1])}")
        if proche and proche.get("timestamp"):
            lignes.append(f"Dernière capture : {_date_wayback(proche['timestamp'])}")
        return "\n".join(lignes) or "Jamais archivé."

    # ------------------------------------------------------------ IP

    async def ip(self, cible: str) -> Resultat:
        adresse = valider_ip(cible)
        statut, d = await self.http.get_json(f"https://ipwho.is/{adresse}")
        if statut != 200 or not isinstance(d, dict) or d.get("success") is False:
            raise RuntimeError("service de géolocalisation indisponible")
        connexion = d.get("connection") or {}
        r = Resultat(titre=f"📍 Adresse IP · {adresse}")
        r.champs = [
            ("🌍 Localisation approximative", f"{d.get('flag', {}).get('emoji', '')} {d.get('country', '?')} · {d.get('city', '?')}".strip()),
            ("🏢 Fournisseur", str(connexion.get("isp") or connexion.get("org") or "?")),
            ("🔢 ASN", f"AS{connexion.get('asn')}" if connexion.get("asn") else "?"),
            ("🌐 Type", str(d.get("type", "?"))),
        ]
        r.note = "La localisation d'une IP est approximative (souvent la ville du fournisseur)."
        return r

    # ------------------------------------------------------------ lien

    async def lien(self, cible: str) -> Resultat:
        url = valider_url(cible)
        chaine = await self._suivre_redirections(url)
        finale = chaine[-1]
        r = Resultat(titre="🔗 Analyse de lien")
        r.champs.append(("➡️ Redirections", "\n".join(f"`{_court(u)}`" for u in chaine) if len(chaine) > 1 else "Aucune"))
        signaux = signaux_suspects(url, chaine)
        r.champs.append(("🔎 Indices", "\n".join(f"• {s}" for s in signaux) if signaux else "Rien de suspect dans l'adresse"))
        niveaux = []
        if self.vt_key:
            niveau, texte = await self._virustotal(finale)
            niveaux.append(niveau)
            r.champs.append(("🧪 VirusTotal", texte))
        if self.urlscan_key:
            niveau, texte = await self._urlscan(finale)
            niveaux.append(niveau)
            r.champs.append(("🛰️ urlscan.io", texte))
        if "rouge" in niveaux:
            r.niveau = "rouge"
        elif "orange" in niveaux or len(signaux) >= 2:
            r.niveau = "orange"
        else:
            r.niveau = "vert"
        verdicts = {
            "vert": "🟢 **Aucun signal négatif.** Reste quand même prudent.",
            "orange": "🟠 **Prudence** : des éléments sont suspects. Ne saisis aucun mot de passe sur ce site.",
            "rouge": "🔴 **Dangereux** : ne clique pas sur ce lien.",
        }
        r.champs.insert(0, ("Verdict", verdicts[r.niveau]))
        if not (self.vt_key or self.urlscan_key):
            r.note = "Analyse limitée : ajoute une clé gratuite VirusTotal ou urlscan.io dans .env pour un avis plus fiable."
        return r

    async def _verifier_hote(self, url: str) -> None:
        """Protection : on ne contacte JAMAIS une adresse du réseau local (box, PC, Ollama...)."""
        hote = urlsplit(url).hostname or ""
        try:
            adresses = await self.http.resoudre(hote)
        except OSError:
            raise HorsPerimetre(f"Le site `{hote}` n'existe pas (nom introuvable).") from None
        for a in adresses:
            if not ip_publique(ipaddress.ip_address(a.split("%")[0])):
                raise HorsPerimetre("Ce lien mène vers le réseau local : refusé par sécurité.")

    async def _suivre_redirections(self, url: str, maximum: int = 8) -> list[str]:
        chaine = [url]
        for _ in range(maximum):
            await self._verifier_hote(chaine[-1])
            try:
                statut, location = await self.http.sans_redirection(chaine[-1])
            except (aiohttp.ClientError, TimeoutError):
                break
            if statut not in (301, 302, 303, 307, 308) or not location:
                break
            suivante = urljoin(chaine[-1], location)
            if urlsplit(suivante).scheme not in ("http", "https"):
                break
            chaine.append(suivante)
        return chaine

    async def _virustotal(self, url: str) -> tuple[str, str]:
        identifiant = base64.urlsafe_b64encode(url.encode()).decode().rstrip("=")
        entetes = {"x-apikey": self.vt_key or ""}
        statut, d = await self.http.get_json(f"https://www.virustotal.com/api/v3/urls/{identifiant}", headers=entetes)
        if statut == 404:
            await self.http.post_json("https://www.virustotal.com/api/v3/urls", {"url": url}, headers=entetes, formulaire=True)
            return "info", "Lien jamais analysé : analyse demandée, réessaie dans 1 minute."
        if statut == 401:
            return "info", "Clé VirusTotal refusée (vérifie VIRUSTOTAL_API_KEY)."
        if statut == 429:
            return "info", "Limite gratuite atteinte (4 requêtes/min), réessaie plus tard."
        if statut != 200 or not isinstance(d, dict):
            return "info", "Service indisponible."
        stats = d.get("data", {}).get("attributes", {}).get("last_analysis_stats", {})
        mal, sus = int(stats.get("malicious", 0)), int(stats.get("suspicious", 0))
        total = sum(int(v) for v in stats.values() if isinstance(v, int))
        niveau = "rouge" if mal >= 2 else ("orange" if mal or sus else "vert")
        return niveau, f"{mal} antivirus disent dangereux, {sus} suspect, sur {total}"

    async def _urlscan(self, url: str) -> tuple[str, str]:
        entetes = {"API-Key": self.urlscan_key or ""}
        statut, d = await self.http.post_json(
            "https://urlscan.io/api/v1/scan/", {"url": url, "visibility": "unlisted"}, headers=entetes
        )
        if statut == 429:
            return "info", "Limite gratuite atteinte, réessaie plus tard."
        if statut not in (200, 201) or not isinstance(d, dict) or not d.get("uuid"):
            message = (d or {}).get("message") if isinstance(d, dict) else None
            return "info", f"Analyse impossible{f' : {message}' if message else ''}."
        for _ in range(8):  # le résultat arrive en ~10-30 s
            await asyncio.sleep(4)
            statut, res = await self.http.get_json(f"https://urlscan.io/api/v1/result/{d['uuid']}/", headers=entetes)
            if statut == 200 and isinstance(res, dict):
                verdict = res.get("verdicts", {}).get("overall", {})
                if verdict.get("malicious"):
                    return "rouge", f"⚠️ Jugé malveillant (score {verdict.get('score', '?')})"
                return "vert", f"Rien de malveillant détecté (score {verdict.get('score', 0)})"
        return "info", "Analyse toujours en cours, réessaie dans une minute."

    # ------------------------------------------------------------ entreprise (BCE / KBO)

    async def entreprise(self, cible: str) -> Resultat:
        type_, valeur = valider_entreprise(cible)
        base = "https://kbopub.economie.fgov.be/kbopub"
        if type_ == "numero":
            statut, page = await self.http.get_text(
                f"{base}/toonondernemingps.html", params={"ondernemingsnummer": valeur, "lang": "fr"}
            )
            if statut != 200:
                raise RuntimeError("site de la BCE indisponible")
            infos = lire_page_bce(page)
            if not infos:
                return Resultat(f"🏢 BCE · {formater_bce(valeur)}", [("Résultat", "Aucune entreprise trouvée avec ce numéro.")])
            return resultat_entreprise(valeur, infos)
        # Recherche par nom : UNIQUEMENT les personnes morales (ondNP=false)
        statut, page = await self.http.get_text(
            f"{base}/zoeknaamfonetischform.html",
            params={
                "searchWord": valeur, "_oudeBenaming": "on", "pstcdeNPRP": "", "postgemeente1": "",
                "ondNP": "false", "_ondNP": "on", "ondRP": "true", "_ondRP": "on", "rechtsvormFonetic": "ALL",
                "_vest": "on", "filterEnkelActieve": "true", "_filterEnkelActieve": "on",
                "actionNPRP": "Rechercher", "lang": "fr",
            },
        )
        if statut != 200:
            raise RuntimeError("site de la BCE indisponible")
        trouvees = lire_recherche_bce(page)
        r = Resultat(titre=f"🏢 BCE · recherche « {valeur} »")
        if not trouvees:
            r.champs.append(("Résultat", "Aucune personne morale active trouvée avec ce nom."))
        else:
            r.champs.append((
                f"{len(trouvees)} résultat(s)",
                "\n".join(f"`{formater_bce(n)}` · {nom}" for n, nom in trouvees[:10]),
            ))
            r.note = "Pour le détail : `/osint entreprise numero_ou_nom:<numéro>`."
        return r

    # ------------------------------------------------------------ mot de passe (k-anonymity)

    async def mot_de_passe(self, mot_de_passe: str) -> Resultat:
        """Vérifie une fuite SANS envoyer le mot de passe : seuls 5 caractères du hash SHA-1 partent."""
        empreinte = hashlib.sha1(mot_de_passe.encode("utf-8")).hexdigest().upper()  # noqa: S324 (imposé par l'API HIBP)
        prefixe, suffixe = empreinte[:5], empreinte[5:]
        statut, texte = await self.http.get_text(
            f"https://api.pwnedpasswords.com/range/{prefixe}", headers={"Add-Padding": "true"}
        )
        if statut != 200:
            raise RuntimeError("service Have I Been Pwned indisponible")
        fois = compter_fuites(texte, suffixe)
        r = Resultat(titre="🔑 Vérification de mot de passe")
        if fois:
            r.niveau = "rouge"
            r.champs.append(("🔴 Mot de passe compromis", f"Il apparaît **{fois:,}** fois dans des fuites connues.".replace(",", " ")))
            r.champs.append(("Que faire ?", "Change-le partout où tu l'utilises, et active la double authentification."))
        else:
            r.niveau = "vert"
            r.champs.append(("🟢 Aucune fuite connue", "Ce mot de passe n'apparaît dans aucune fuite publique connue."))
        r.note = "Ton mot de passe n'a jamais quitté le PC : seuls 5 caractères de son empreinte SHA-1 ont été envoyés."
        return r


# ====================================================================== lecteurs (fonctions pures)


def _date_wayback(ts: str) -> str:
    try:
        return datetime.strptime(ts[:8], "%Y%m%d").strftime("%d/%m/%Y")
    except ValueError:
        return ts


def _court(url: str, n: int = 90) -> str:
    return url if len(url) <= n else url[: n - 1] + "…"


def lire_rdap(d: dict[str, Any]) -> str:
    """Registrar, dates et statut d'un domaine (format RDAP). Aucune donnée de personne."""
    registrar = "?"
    for entite in d.get("entities") or []:
        if "registrar" in (entite.get("roles") or []):
            for champ in (entite.get("vcardArray") or [None, []])[1]:
                if champ and champ[0] == "fn":
                    registrar = str(champ[3])
    dates = {e.get("eventAction"): e.get("eventDate", "")[:10] for e in d.get("events") or []}
    lignes = [f"Registrar : **{registrar}**"]
    for cle, libelle in (("registration", "Créé le"), ("expiration", "Expire le"), ("last changed", "Modifié le")):
        if dates.get(cle):
            try:
                lignes.append(f"{libelle} {datetime.fromisoformat(dates[cle]):%d/%m/%Y}")
            except ValueError:
                lignes.append(f"{libelle} {dates[cle]}")
    if d.get("status"):
        lignes.append("Statut : " + ", ".join(d["status"][:3]))
    return "\n".join(lignes)


def lire_whois_texte(texte: str) -> str:
    """Extrait seulement registrar et dates d'une réponse WHOIS (on ignore tout ce qui concerne le titulaire)."""
    recherches = {
        "Registrar": ("registrar:", "registrar name:", "sponsoring registrar:"),
        "Créé le": ("creation date:", "registered:", "created:"),
        "Expire le": ("registry expiry date:", "expiration date:", "expires:", "paid-till:"),
        "Statut": ("status:", "domain status:"),
    }
    lignes = texte.splitlines()
    resultat = []
    for libelle, prefixes in recherches.items():
        for i, ligne in enumerate(lignes):
            basse = ligne.strip().lower()
            if basse.startswith(prefixes):
                valeur = ligne.split(":", 1)[1].strip()
                if not valeur and libelle == "Registrar" and i + 1 < len(lignes):
                    # Format DNS Belgium : « Registrar: » puis « Name: X » à la ligne suivante
                    suivante = lignes[i + 1].strip()
                    valeur = suivante.split(":", 1)[1].strip() if ":" in suivante else suivante
                if valeur:
                    resultat.append(f"{libelle} : **{valeur[:80]}**")
                    break
    return "\n".join(resultat) or "Aucune information WHOIS publique."


def signaux_suspects(url: str, chaine: Sequence[str]) -> list[str]:
    """Indices simples qui doivent rendre prudent (sans aucun service externe)."""
    signaux = []
    p = urlsplit(url)
    hote = (p.hostname or "").lower()
    if p.scheme == "http":
        signaux.append("Pas de HTTPS (connexion non chiffrée)")
    try:
        ipaddress.ip_address(hote)
        signaux.append("Adresse IP au lieu d'un nom de site")
    except ValueError:
        pass
    if "xn--" in hote:
        signaux.append("Nom de domaine avec caractères spéciaux (punycode) : risque d'imitation")
    if "@" in p.netloc:
        signaux.append("Contient « @ » dans l'adresse : technique de tromperie classique")
    if hote.count(".") >= 4:
        signaux.append("Beaucoup de sous-domaines")
    if hote.rsplit(".", 1)[-1] in {"zip", "mov", "xyz", "top", "click", "gq", "tk", "ml", "cf", "ga", "rest", "cam"}:
        signaux.append("Extension de domaine souvent utilisée par des arnaques")
    if hote in {"bit.ly", "tinyurl.com", "t.co", "goo.gl", "is.gd", "cutt.ly", "rb.gy", "ow.ly", "shorturl.at"}:
        signaux.append("Lien raccourci : la vraie destination est cachée")
    if len(url) > 200:
        signaux.append("Adresse anormalement longue")
    mots = ("login", "verify", "free-robux", "robux", "nitro", "gift", "wallet", "password", "account-update")
    if any(m in url.lower() for m in mots):
        signaux.append("Mots typiques du phishing (connexion, cadeau, Robux, Nitro...)")
    if len(chaine) > 1:
        depart = (urlsplit(chaine[0]).hostname or "").removeprefix("www.")
        arrivee = (urlsplit(chaine[-1]).hostname or "").removeprefix("www.")
        if depart != arrivee:
            signaux.append(f"Redirige vers un autre site : `{arrivee}`")
    return signaux


def compter_fuites(reponse_api: str, suffixe: str) -> int:
    """Cherche notre suffixe de hash dans la réponse « SUFFIXE:NOMBRE » de Pwned Passwords."""
    for ligne in reponse_api.splitlines():
        s, _, n = ligne.strip().partition(":")
        if s.upper() == suffixe.upper():
            try:
                return int(n)  # les lignes de remplissage (« padding ») valent 0
            except ValueError:
                return 0
    return 0


def _texte_html(fragment: str) -> str:
    fragment = re.sub(r"<span class=\"upd\">.*?</span>", "", fragment, flags=re.IGNORECASE | re.DOTALL)
    fragment = re.sub(r"<br\s*/?>", "\n", fragment, flags=re.IGNORECASE)
    fragment = re.sub(r"<[^>]+>", "", fragment)
    lignes = [re.sub(r"\s+", " ", html.unescape(x)).strip() for x in fragment.splitlines()]
    return "\n".join(x for x in lignes if x)


def lire_page_bce(page: str) -> dict[str, str]:
    """Lit la fiche publique d'une entreprise (tableau « libellé : valeur » du site de la BCE)."""
    voulus = {
        "dénomination": "denomination",
        "statut": "statut",
        "situation juridique": "situation",
        "date de début": "debut",
        "adresse du siège": "siege",
        "type d'entité": "type",
        "forme légale": "forme",
        "forme juridique": "forme",
    }
    infos: dict[str, str] = {}
    for ligne in re.findall(r"<tr[^>]*>(.*?)</tr>", page, flags=re.IGNORECASE | re.DOTALL):
        cellules = re.findall(r"<td[^>]*>(.*?)</td>", ligne, flags=re.IGNORECASE | re.DOTALL)
        if len(cellules) < 2:
            continue
        libelle = _texte_html(cellules[0]).rstrip(":").strip().casefold()
        cle = voulus.get(libelle)
        if cle and cle not in infos:
            valeur = _texte_html(cellules[1])
            if valeur:
                infos[cle] = valeur
    return infos


def lire_recherche_bce(page: str) -> list[tuple[str, str]]:
    """Résultats d'une recherche par nom : [(numéro, dénomination)]."""
    resultats: list[tuple[str, str]] = []
    vus = set()
    for ligne in re.findall(r"<tr[^>]*>(.*?)</tr>", page, flags=re.IGNORECASE | re.DOTALL):
        m = re.search(r"ondernemingsnummer=(\d{10})", ligne)
        if not m or m.group(1) in vus:
            continue
        cellules = [_texte_html(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", ligne, flags=re.IGNORECASE | re.DOTALL)]
        candidats = [c.split("\n")[0] for c in cellules if c and re.search(r"[A-Za-zÀ-ÿ]{2}", c)
                     and not re.fullmatch(r"[\d.\s]+", c) and c.casefold() not in {"actif", "arrêté", "active"}]
        nom = max(candidats, key=len) if candidats else "?"
        vus.add(m.group(1))
        resultats.append((m.group(1), nom[:80]))
    return resultats


def resultat_entreprise(numero: str, infos: dict[str, str]) -> Resultat:
    r = Resultat(titre=f"🏢 BCE · {formater_bce(numero)}")
    personne_physique = "physique" in infos.get("type", "").casefold()
    if personne_physique:
        # RGPD : une entreprise en personne physique = une personne. On ne montre ni nom ni adresse.
        r.champs.append(("👤 Personne physique", "Entreprise individuelle : nom et adresse masqués (RGPD)."))
    else:
        r.champs.append(("📛 Dénomination", infos.get("denomination", "?").split("\n")[0]))
        if infos.get("forme"):
            r.champs.append(("⚖️ Forme juridique", infos["forme"].split("\n")[0]))
        if infos.get("siege"):
            r.champs.append(("📍 Siège", infos["siege"]))
    r.champs.append(("📊 Statut", " · ".join(x for x in (infos.get("statut"), infos.get("situation", "").split("\n")[0]) if x) or "?"))
    if infos.get("debut"):
        r.champs.append(("📅 Date de création", infos["debut"]))
    r.note = "Source : Banque-Carrefour des Entreprises (données publiques)."
    return r


# ====================================================================== EXIF (images envoyées par MOI)


def lire_exif(donnees: bytes) -> tuple[list[tuple[str, str]], tuple[float, float] | None]:
    """Métadonnées EXIF lisibles + coordonnées GPS éventuelles."""
    from PIL import ExifTags, Image

    with Image.open(io.BytesIO(donnees)) as img:
        exif = img.getexif()
        lignes: list[tuple[str, str]] = [("Format", f"{img.format} · {img.width}×{img.height}")]
        importants = {"Make": "Appareil (marque)", "Model": "Appareil (modèle)", "Software": "Logiciel",
                      "DateTime": "Date", "Artist": "Auteur", "Copyright": "Copyright"}
        for tag, valeur in exif.items():
            nom = ExifTags.TAGS.get(tag, str(tag))
            if nom in importants:
                lignes.append((importants[nom], str(valeur)[:100]))
        sous = exif.get_ifd(ExifTags.IFD.Exif)
        for tag, valeur in sous.items():
            nom = ExifTags.TAGS.get(tag, str(tag))
            if nom in ("DateTimeOriginal", "LensModel"):
                lignes.append(({"DateTimeOriginal": "Prise de vue", "LensModel": "Objectif"}[nom], str(valeur)[:100]))
        gps = exif.get_ifd(ExifTags.IFD.GPSInfo)
        lignes.append(("Nombre de métadonnées", str(len(exif) + len(sous) + len(gps))))
        return lignes, _coordonnees(gps)


def _coordonnees(gps: dict[int, Any]) -> tuple[float, float] | None:
    try:
        def deg(valeurs: Sequence[Any], ref: str) -> float:
            d, m, s = (float(v) for v in valeurs)
            signe = -1 if ref in ("S", "W") else 1
            return signe * (d + m / 60 + s / 3600)

        if 2 in gps and 4 in gps:
            return round(deg(gps[2], gps.get(1, "N")), 6), round(deg(gps[4], gps.get(3, "E")), 6)
    except (TypeError, ValueError, ZeroDivisionError):
        pass
    return None


def nettoyer_image(donnees: bytes) -> tuple[bytes, str]:
    """Renvoie l'image SANS aucune métadonnée (EXIF, GPS, XMP, commentaires) + son extension."""
    from PIL import Image, ImageOps

    with Image.open(io.BytesIO(donnees)) as img:
        format_ = (img.format or "PNG").upper()
        propre = ImageOps.exif_transpose(img)  # garde le bon sens de la photo
        propre.info = {}
        sortie = io.BytesIO()
        if format_ in ("JPEG", "MPO"):
            propre.convert("RGB").save(sortie, format="JPEG", quality=95)
            return sortie.getvalue(), "jpg"
        if format_ == "WEBP":
            propre.save(sortie, format="WEBP", quality=95)
            return sortie.getvalue(), "webp"
        propre.save(sortie, format="PNG")
        return sortie.getvalue(), "png"
