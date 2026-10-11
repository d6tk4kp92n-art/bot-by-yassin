"""OSINT : refus hors périmètre AVANT tout appel réseau, réseau simulé pour le reste."""

import hashlib
import io
from types import SimpleNamespace

import pytest
from discord import app_commands
from PIL import Image

from bot.osint_outils import (
    HorsPerimetre,
    ServiceOSINT,
    compter_fuites,
    lire_exif,
    lire_page_bce,
    lire_recherche_bce,
    lire_whois_texte,
    nettoyer_image,
    numero_bce,
    numero_bce_valide,
    signaux_suspects,
    valider_domaine,
    valider_entreprise,
    valider_ip,
    valider_url,
)
from tests.conftest import OWNER_ID


class FauxHttp:
    """Réseau simulé : URL -> réponse. Enregistre chaque appel."""

    def __init__(self, routes=None, adresses=("93.184.216.34",)):
        self.routes = routes or {}
        self.adresses = list(adresses)
        self.appels = []

    def _trouver(self, url):
        self.appels.append(url)
        for debut, rep in self.routes.items():
            if url.startswith(debut):
                return rep
        return (404, None)

    async def get_json(self, url, params=None, headers=None):
        rep = self._trouver(url)
        return rep(params) if callable(rep) else rep

    async def get_text(self, url, params=None, headers=None):
        rep = self._trouver(url)
        return rep(params) if callable(rep) else rep

    async def post_json(self, url, donnees, headers=None, formulaire=False):
        return self._trouver(url)

    async def sans_redirection(self, url):
        return self._trouver(url)

    async def resoudre(self, hote):
        self.appels.append(f"dns:{hote}")
        return self.adresses

    async def certificat(self, hote):
        return {
            "issuer": ((("organizationName", "Let's Encrypt"),),),
            "notAfter": "Jan  1 00:00:00 2099 GMT",
            "subjectAltName": (("DNS", hote),),
        }

    async def whois(self, serveur, requete):
        self.appels.append(f"whois:{serveur}")
        if serveur == "whois.iana.org":
            return "refer: whois.dns.be\n"
        return "Domain: exemple.be\nStatus: NOT AVAILABLE\nRegistered: Mon Jan 1 2001\n\nRegistrar:\n\tName: Registrar SA\n"


# ---------------------------------------------------------------- périmètre


@pytest.mark.parametrize(
    "cible", ["jean.dupont@gmail.com", "+32 470 12 34 56", "0470 12 34 56", "1-ABC-123", "@pseudo"]
)
async def test_refus_donnees_personnelles_sans_appel_reseau(cible):
    http = FauxHttp()
    service = ServiceOSINT(http)
    for fonction in (service.domaine, service.entreprise, service.lien):
        with pytest.raises(HorsPerimetre):
            await fonction(cible)
    assert http.appels == []  # rien n'est parti sur internet


@pytest.mark.parametrize(
    "url",
    [
        "https://www.instagram.com/quelquun",
        "https://facebook.com/profile.php?id=1",
        "https://www.tiktok.com/@pseudo",
        "https://x.com/pseudo",
        "https://www.linkedin.com/in/jean-dupont",
        "https://www.roblox.com/users/123/profile",
    ],
)
async def test_refus_profils_reseaux_sociaux(url):
    with pytest.raises(HorsPerimetre, match="réseau social"):
        valider_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:11434/api/tags",
        "http://192.168.1.1",
        "http://localhost:8080",
        "http://[::1]/",
    ],
)
async def test_refus_reseau_local(url):
    with pytest.raises(HorsPerimetre):
        valider_url(url)


async def test_redirection_vers_reseau_local_bloquee():
    http = FauxHttp({"https://piege.example": (302, "http://intranet.example/")})
    service = ServiceOSINT(http)

    async def resoudre(hote):
        return ["10.0.0.5"] if hote == "intranet.example" else ["93.184.216.34"]

    http.resoudre = resoudre
    with pytest.raises(HorsPerimetre, match="réseau local"):
        await service.lien("https://piege.example/")


def test_validations():
    assert valider_domaine("https://WWW.Exemple.be/page?x=1") == "www.exemple.be"
    with pytest.raises(HorsPerimetre):
        valider_domaine("8.8.8.8")
    with pytest.raises(HorsPerimetre):
        valider_domaine("pas un domaine")
    assert valider_ip(" 8.8.8.8 ") == "8.8.8.8"
    for ip in ("192.168.0.1", "10.1.2.3", "127.0.0.1", "abc"):
        with pytest.raises(HorsPerimetre):
            valider_ip(ip)
    assert valider_url("exemple.be") == "http://exemple.be"
    assert (
        valider_url("https://www.instagram.com/") == "https://www.instagram.com/"
    )  # page d'accueil OK
    assert numero_bce("BE 0403.170.701") == "0403170701"
    assert numero_bce("403170701") == "0403170701"
    assert numero_bce_valide("0403170701")
    assert not numero_bce_valide("0403170702")
    assert valider_entreprise("0403.170.701") == ("numero", "0403170701")
    assert valider_entreprise("Colruyt") == ("nom", "Colruyt")
    with pytest.raises(HorsPerimetre, match="modulo 97"):
        valider_entreprise("0403.170.702")


# ---------------------------------------------------------------- commandes (réseau simulé)


async def test_domaine():
    http = FauxHttp(
        {
            "https://rdap.org/domain/": (
                200,
                {
                    "entities": [
                        {
                            "roles": ["registrar"],
                            "vcardArray": ["vcard", [["fn", {}, "text", "Gandi SAS"]]],
                        }
                    ],
                    "events": [
                        {"eventAction": "registration", "eventDate": "2001-02-03T00:00:00Z"}
                    ],
                    "status": ["active"],
                },
            ),
            "https://dns.google/resolve": lambda p: (
                200,
                {"Answer": [{"data": f"valeur-{p['type']}"}]},
            ),
            "https://archive.org/wayback/available": (
                200,
                {"archived_snapshots": {"closest": {"timestamp": "20240101000000"}}},
            ),
            "https://web.archive.org/cdx": (
                200,
                [["urlkey", "timestamp"], ["x", "19990505000000"]],
            ),
        }
    )
    r = await ServiceOSINT(http).domaine("exemple.com")
    champs = dict(r.champs)
    assert "Gandi SAS" in champs["📇 WHOIS"] and "03/02/2001" in champs["📇 WHOIS"]
    assert "valeur-MX" in champs["🧭 DNS"] and "valeur-TXT" in champs["🧭 DNS"]
    assert "Let's Encrypt" in champs["🔒 Certificat SSL"]
    assert "05/05/1999" in champs["🏛️ Archive.org"]


async def test_domaine_be_whois_classique():
    http = FauxHttp(
        {
            "https://dns.google": (200, {}),
            "https://archive.org": (200, {}),
            "https://web.archive.org": (200, []),
        }
    )
    r = await ServiceOSINT(http).domaine("exemple.be")
    assert "Registrar SA" in dict(r.champs)["📇 WHOIS"]
    assert "whois:whois.dns.be" in http.appels


async def test_ip():
    http = FauxHttp(
        {
            "https://ipwho.is/8.8.8.8": (
                200,
                {
                    "success": True,
                    "country": "United States",
                    "city": "Mountain View",
                    "type": "IPv4",
                    "flag": {"emoji": "🇺🇸"},
                    "connection": {"asn": 15169, "isp": "Google LLC"},
                },
            )
        }
    )
    r = await ServiceOSINT(http).ip("8.8.8.8")
    champs = dict(r.champs)
    assert champs["🔢 ASN"] == "AS15169" and champs["🏢 Fournisseur"] == "Google LLC"


async def test_lien_redirections_et_verdicts():
    http = FauxHttp(
        {
            "https://bit.ly/abc": (301, "https://free-robux.xyz/login"),
            "https://free-robux.xyz/login": (200, None),
            "https://www.virustotal.com/api/v3/urls/": (
                200,
                {
                    "data": {
                        "attributes": {
                            "last_analysis_stats": {
                                "malicious": 5,
                                "suspicious": 1,
                                "harmless": 60,
                                "undetected": 10,
                            }
                        }
                    }
                },
            ),
        }
    )
    r = await ServiceOSINT(http, virustotal_key="cle").lien("https://bit.ly/abc")
    assert r.niveau == "rouge"
    champs = dict(r.champs)
    assert "free-robux.xyz" in champs["➡️ Redirections"]
    assert "🔴" in champs["Verdict"]
    # Sans clé : seulement les indices -> orange (raccourci + phishing + extension)
    r2 = await ServiceOSINT(http).lien("https://bit.ly/abc")
    assert r2.niveau == "orange" and r2.note
    # Lien propre
    http_ok = FauxHttp({"https://exemple.be": (200, None)})
    assert (await ServiceOSINT(http_ok).lien("https://exemple.be")).niveau == "vert"


def test_signaux_suspects():
    assert signaux_suspects("https://exemple.be", ["https://exemple.be"]) == []
    s = signaux_suspects("http://1.2.3.4/login", ["http://1.2.3.4/login"])
    assert len(s) >= 3


PAGE_BCE = """
<table>
<tr><td class="QL">Numéro d'entreprise:</td><td class="QL">0403.170.701</td></tr>
<tr><td class="QL">Statut:</td><td class="QL"><strong><span class="pageactief">Actif</span></strong></td></tr>
<tr><td class="QL">Situation juridique:</td><td class="QL"><span class="pageactief">Situation normale</span><br><span class="upd">Depuis le 30 décembre 1924</span></td></tr>
<tr><td class="QL">Date de début:</td><td class="QL">30 décembre 1924</td></tr>
<tr><td class="QL">Dénomination:</td><td class="QL" colspan="3">ENTREPRISE EXEMPLE &amp; Cie<br><span class="upd">Dénomination en français, depuis le 1 janvier 2000</span></td></tr>
<tr><td class="RL">Adresse du siège:</td><td class="QL">Rue de la Loi 16<br>1000 Bruxelles<br><span class="upd">Depuis le 1 janvier 2000</span></td></tr>
<tr><td class="QL">Type d'entité:</td><td class="QL">Personne morale</td></tr>
<tr><td class="QL">Forme légale:</td><td class="QL">Société anonyme<br><span class="upd">Depuis le 1 janvier 2000</span></td></tr>
</table>"""


async def test_entreprise_par_numero():
    assert lire_page_bce(PAGE_BCE)["denomination"] == "ENTREPRISE EXEMPLE & Cie"
    http = FauxHttp(
        {"https://kbopub.economie.fgov.be/kbopub/toonondernemingps.html": (200, PAGE_BCE)}
    )
    r = await ServiceOSINT(http).entreprise("BE 0403.170.701")
    champs = dict(r.champs)
    assert champs["📛 Dénomination"] == "ENTREPRISE EXEMPLE & Cie"
    assert champs["⚖️ Forme juridique"] == "Société anonyme"
    assert "Rue de la Loi 16" in champs["📍 Siège"]
    assert "Actif" in champs["📊 Statut"]


async def test_entreprise_personne_physique_masquee():
    page = PAGE_BCE.replace("Personne morale", "Personne physique").replace(
        "ENTREPRISE EXEMPLE &amp; Cie", "DUPONT, Jean"
    )
    http = FauxHttp({"https://kbopub.economie.fgov.be/kbopub/toonondernemingps.html": (200, page)})
    r = await ServiceOSINT(http).entreprise("0403.170.701")
    texte = str(r.champs)
    assert "DUPONT" not in texte and "Rue de la Loi" not in texte
    assert "RGPD" in texte


async def test_entreprise_par_nom_uniquement_personnes_morales():
    page = """<table><tr><td>1</td><td><a href="toonondernemingps.html?ondernemingsnummer=0403170701">0403.170.701</a></td>
    <td>Actif</td><td>ENTREPRISE EXEMPLE</td></tr></table>"""
    vus = {}

    def route(params):
        vus.update(params)
        return (200, page)

    http = FauxHttp({"https://kbopub.economie.fgov.be/kbopub/zoeknaamfonetischform.html": route})
    r = await ServiceOSINT(http).entreprise("exemple")
    assert vus["ondNP"] == "false" and vus["ondRP"] == "true"  # jamais les personnes physiques
    assert "ENTREPRISE EXEMPLE" in str(r.champs)
    assert lire_recherche_bce(page) == [("0403170701", "ENTREPRISE EXEMPLE")]


async def test_mot_de_passe_k_anonymity():
    mdp = "password123"
    empreinte = hashlib.sha1(mdp.encode()).hexdigest().upper()

    def route(_params):
        return (200, f"0000000000000000000000000000000000A:0\n{empreinte[5:]}:12345\n")

    http = FauxHttp({"https://api.pwnedpasswords.com/range/": route})
    r = await ServiceOSINT(http).mot_de_passe(mdp)
    assert r.niveau == "rouge" and "12 345" in str(r.champs)
    url = http.appels[0]
    assert url.endswith("/" + empreinte[:5])  # seulement 5 caractères du hash
    assert mdp not in url and empreinte not in url
    assert compter_fuites("ABC:3\nDEF:0", "def") == 0
    r2 = await ServiceOSINT(
        FauxHttp({"https://api.pwnedpasswords.com/range/": (200, "AAA:1")})
    ).mot_de_passe("autre")
    assert r2.niveau == "vert"


def test_exif_et_nettoyage():
    from PIL import ExifTags

    img = Image.new("RGB", (40, 30), "red")
    exif = Image.Exif()
    exif[ExifTags.Base.Make] = "Canon"
    exif[ExifTags.Base.Model] = "EOS 5D"
    gps = {1: "N", 2: (50.0, 50.0, 0.0), 3: "E", 4: (4.0, 21.0, 0.0)}
    exif[ExifTags.IFD.GPSInfo] = gps
    tampon = io.BytesIO()
    img.save(tampon, format="JPEG", exif=exif)
    lignes, coordonnees = lire_exif(tampon.getvalue())
    assert ("Appareil (marque)", "Canon") in lignes
    assert coordonnees == (50.833333, 4.35)
    propre, extension = nettoyer_image(tampon.getvalue())
    assert extension == "jpg"
    with Image.open(io.BytesIO(propre)) as nettoyee:
        assert len(nettoyee.getexif()) == 0
        assert nettoyee.size == (40, 30)


def test_whois_ignore_le_titulaire():
    texte = "Registrant Name: Jean Dupont\nRegistrar: Gandi\nCreation Date: 2001-01-01\n"
    resultat = lire_whois_texte(texte)
    assert "Gandi" in resultat and "Dupont" not in resultat


# ---------------------------------------------------------------- cog : propriétaire uniquement + journal


async def test_cog_reserve_au_proprietaire_et_journalise(bot):
    cog = bot.get_cog("OSINT")
    intrus = SimpleNamespace(user=SimpleNamespace(id=999))
    with pytest.raises(app_commands.CheckFailure):
        await cog.interaction_check(intrus)
    await bot.reglages.definir("osint_active", False)
    with pytest.raises(app_commands.CheckFailure, match="désactivé"):
        await cog.interaction_check(SimpleNamespace(user=SimpleNamespace(id=OWNER_ID)))
    await bot.reglages.definir("osint_active", True)
    assert await cog.interaction_check(SimpleNamespace(user=SimpleNamespace(id=OWNER_ID)))

    cog.service.http = FauxHttp()
    envois = []

    class FausseReponse:
        def __init__(self):
            self.fait = False

        def is_done(self):
            return self.fait

        async def defer(self, **kw):
            self.fait = True

    class FauxSuivi:
        async def send(self, **kw):
            envois.append(kw)

    interaction = SimpleNamespace(
        user=SimpleNamespace(id=OWNER_ID), response=FausseReponse(), followup=FauxSuivi()
    )
    await cog._executer(
        interaction, "domaine", "jean@gmail.com", cog.service.domaine("jean@gmail.com")
    )
    assert "Requête refusée" in envois[-1]["embed"].title
    journal = await bot.db.journal_osint()
    assert journal[0][1:4] == ("domaine", "jean@gmail.com", "refusé")
    assert cog.service.http.appels == []
