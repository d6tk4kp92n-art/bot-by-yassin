"""Panneau /parametres : navigation par catégories, chaque changement enregistré tout de suite."""

from __future__ import annotations

import io
import json
import logging
import re
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any

import discord

from bot.config import (
    FORMATS_RESUME,
    INFOS_RESUME,
    MODELE_IA_DEFAUT,
    MODELE_IA_LEGER,
    MODES_IA,
    NB_COMPTES_MAX,
    PALETTE,
    SENSIBILITES,
)
from bot.ui.couleurs import BLEU, hex_vers_int, normaliser_hex
from bot.ui.embeds import embed_erreur, embed_succes
from bot.ui.format import tronquer
from bot.ui.vues import VueBase, VueConfirmation, repondre

if TYPE_CHECKING:
    from bot.main import TekkitBot

log = logging.getLogger("tekkit.panneau")

PINGS: dict[str, str] = {
    "ping_disparition": "🔴 Mention si un compte disparaît",
    "message_retour": "🟢 Message quand un compte revient",
    "ping_retour": "🔔 Mention aussi au retour",
    "ping_zone": "🛡️ Mention si la zone change",
    "ping_drop": "🎁 Mention si drop rare",
    "ping_anomalies": "⚠️ Mention si anomalie",
    "ping_objectif": "🎯 Mention si objectif atteint",
}

CATEGORIES: dict[str, tuple[str, str]] = {
    "comptes": ("👤", "Comptes"),
    "temps": ("⏱️", "Temps"),
    "infos": ("📋", "Infos du résumé"),
    "apparence": ("🎨", "Apparence"),
    "alertes": ("🔔", "Alertes"),
    "ia": ("🤖", "IA"),
    "osint": ("🛡️", "OSINT"),
}

RE_USERNAME = re.compile(r"^[A-Za-z0-9_]{3,20}$")
RE_HEURE = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")


def oui_non(valeur: Any) -> str:
    return "✅" if valeur else "❌"


def _embed(titre: str, lignes: list[str]) -> discord.Embed:
    e = discord.Embed(title=f"⚙️ Paramètres · {titre}", description=tronquer("\n".join(lignes), 4000), color=BLEU)
    e.set_footer(text="Tekkit Watch · chaque changement est enregistré immédiatement")
    return e


def _salon(valeur: Any) -> str:
    return f"<#{valeur}>" if valeur else "salon du webhook"


# ====================================================================== base


class VuePanneau(VueBase):
    """Base de toutes les pages du panneau (réservé au propriétaire)."""

    titre = "Accueil"

    def __init__(self, bot: TekkitBot, auteur_id: int) -> None:
        super().__init__(timeout=900)
        self.bot = bot
        self.auteur_id = auteur_id

    @property
    def r(self) -> Any:
        return self.bot.reglages

    async def preparer(self) -> None:
        """Chargements asynchrones avant affichage (ex. liste des modèles IA)."""
        self.construire()

    def construire(self) -> None:
        raise NotImplementedError

    def embed(self) -> discord.Embed:
        raise NotImplementedError

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.auteur_id or not self.bot.est_proprietaire(interaction.user):
            await repondre(interaction, embed=embed_erreur("🔒 Ce panneau est réservé au propriétaire."))
            return False
        return True

    # ------------------------------------------------------------ outils

    async def afficher(self, interaction: discord.Interaction, vue: VuePanneau | None = None) -> None:
        """Affiche une page (ou rafraîchit celle-ci) dans le même message."""
        vue = vue or type(self)(self.bot, self.auteur_id)
        await vue.preparer()
        if interaction.response.is_done():
            await interaction.edit_original_response(embed=vue.embed(), view=vue)
        else:
            await interaction.response.edit_message(embed=vue.embed(), view=vue)
        self.stop()

    def bouton(
        self,
        label: str,
        action: Callable[[discord.Interaction], Awaitable[None]],
        row: int,
        emoji: str | None = None,
        style: discord.ButtonStyle = discord.ButtonStyle.secondary,
    ) -> discord.ui.Button:
        b: discord.ui.Button = discord.ui.Button(label=label, emoji=emoji, style=style, row=row)

        async def callback(interaction: discord.Interaction) -> None:
            await action(interaction)

        b.callback = callback  # type: ignore[method-assign]
        self.add_item(b)
        return b

    def bascule(self, cle: str, label: str, row: int, apres: Callable[[], Awaitable[None]] | None = None) -> None:
        """Bouton oui/non vert (activé) ou gris (désactivé)."""
        actif = bool(self.r[cle])

        async def action(interaction: discord.Interaction) -> None:
            await self.r.basculer(cle)
            if apres is not None:
                await apres()
            await self.afficher(interaction)

        self.bouton(
            f"{label} : {'oui' if actif else 'non'}",
            action,
            row,
            style=discord.ButtonStyle.success if actif else discord.ButtonStyle.secondary,
        )

    def retour(self, row: int, vers: type[VuePanneau] | None = None) -> None:
        async def action(interaction: discord.Interaction) -> None:
            await self.afficher(interaction, (vers or VueAccueil)(self.bot, self.auteur_id))

        self.bouton("Retour", action, row, emoji="⬅️")


# ====================================================================== accueil


class VueAccueil(VuePanneau):
    titre = "Accueil"

    def construire(self) -> None:
        menu: discord.ui.Select = discord.ui.Select(
            placeholder="📂 Choisis une catégorie…",
            options=[discord.SelectOption(label=nom, value=cle, emoji=emoji) for cle, (emoji, nom) in CATEGORIES.items()],
            row=0,
        )

        async def choisir(interaction: discord.Interaction) -> None:
            classe = PAGES[menu.values[0]]
            await self.afficher(interaction, classe(self.bot, self.auteur_id))

        menu.callback = choisir  # type: ignore[method-assign]
        self.add_item(menu)

        pause = self.bot.moteur.pause
        self.bouton(
            "Relancer la surveillance" if pause else "Mettre en pause",
            self._basculer_surveillance,
            1,
            emoji="▶️" if pause else "⏸️",
            style=discord.ButtonStyle.success if pause else discord.ButtonStyle.secondary,
        )
        self.bouton("Aperçu du résumé", self._apercu, 1, emoji="👁️")
        self.bouton("Exporter", self._exporter, 1, emoji="💾")
        self.bouton("Tout remettre par défaut", self._reinitialiser, 1, emoji="♻️", style=discord.ButtonStyle.danger)

    def embed(self) -> discord.Embed:
        r = self.r
        comptes = ", ".join(f"`{c}`" for c in r["comptes"]) or "aucun"
        lignes = [
            f"**Surveillance** : {'⏸️ en pause' if self.bot.moteur.pause else '▶️ active'}",
            f"👤 **Comptes** ({len(r['comptes'])}/{NB_COMPTES_MAX}) : {comptes}",
            f"⏱️ Alerte après **{r['delai_absence_min']} min** d'absence · résumé "
            + (f"toutes les **{r['resume_intervalle_min']} min**" if r["resume_auto"] else "**désactivé**"),
            f"🎨 Format : {FORMATS_RESUME.get(r['resume_format'], r['resume_format'])} · couleur : `{r['couleur']}`",
            f"🔔 Rareté minimum : **{r['rarete_min']}** · sensibilité : {SENSIBILITES.get(r['sensibilite_anomalies'])}",
            f"📺 Alertes : {_salon(r['salon_alertes'])} · résumés : {_salon(r['salon_resumes'])}",
            f"🤖 IA : {oui_non(r['ia_active'])} `{r['ia_modele']}` · 🛡️ OSINT : {oui_non(r['osint_active'])}",
            "",
            "Choisis une catégorie dans le menu ci-dessous.",
        ]
        return _embed(self.titre, lignes)

    async def _basculer_surveillance(self, interaction: discord.Interaction) -> None:
        cog = self.bot.get_cog("Surveillance")
        if cog is not None:
            await cog.definir_pause(not self.bot.moteur.pause)  # type: ignore[attr-defined]
        await self.afficher(interaction)

    async def _apercu(self, interaction: discord.Interaction) -> None:
        cog = self.bot.get_cog("Resumes")
        if cog is None:
            await repondre(interaction, embed=embed_erreur("Le module des résumés n'est pas disponible."))
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        await repondre(interaction, embed=await cog.construire())  # type: ignore[attr-defined]

    async def _exporter(self, interaction: discord.Interaction) -> None:
        donnees = json.dumps(self.r.exporter(), ensure_ascii=False, indent=2).encode("utf-8")
        fichier = discord.File(io.BytesIO(donnees), filename="tekkit_reglages.json")
        await repondre(
            interaction,
            embed=embed_succes("Voici tes réglages. Pour les restaurer : `/parametres importer:<ce fichier>`.", "💾 Sauvegarde"),
            file=fichier,
        )

    async def _reinitialiser(self, interaction: discord.Interaction) -> None:
        async def confirmer(inter: discord.Interaction) -> None:
            await self.r.tout_remettre_par_defaut()
            self.bot.moteur.configurer(self.r["comptes"])
            await self.bot.mettre_a_jour_statut()
            await self.afficher(inter, VueAccueil(self.bot, self.auteur_id))

        async def annuler(inter: discord.Interaction) -> None:
            await self.afficher(inter, VueAccueil(self.bot, self.auteur_id))

        vue = VueConfirmation(confirmer, self.auteur_id, "Oui, tout remettre par défaut", annuler)
        await interaction.response.edit_message(
            embed=discord.Embed(
                title="♻️ Tout remettre par défaut ?",
                description="Tous les réglages (comptes, délais, couleurs, alertes, IA...) reviennent aux valeurs "
                "d'origine. Les missions enregistrées ne sont **pas** supprimées.",
                color=0xED4245,
            ),
            view=vue,
        )


# ====================================================================== comptes


class ModalCompte(discord.ui.Modal, title="Ajouter un compte"):
    nom: discord.ui.TextInput = discord.ui.TextInput(
        label="Username Roblox", placeholder="ex. abslt98", min_length=3, max_length=20
    )

    def __init__(self, page: VuePanneau) -> None:
        super().__init__()
        self.page = page

    async def on_submit(self, interaction: discord.Interaction) -> None:
        nom = self.nom.value.strip()
        comptes = list(self.page.r["comptes"])
        if not RE_USERNAME.match(nom):
            await repondre(interaction, embed=embed_erreur("Un username Roblox fait 3 à 20 caractères : lettres, chiffres ou _."))
            return
        if any(c.casefold() == nom.casefold() for c in comptes):
            await repondre(interaction, embed=embed_erreur(f"`{nom}` est déjà dans la liste."))
            return
        if len(comptes) >= NB_COMPTES_MAX:
            await repondre(interaction, embed=embed_erreur(f"Maximum {NB_COMPTES_MAX} comptes."))
            return
        await self.page.r.definir("comptes", [*comptes, nom])
        self.page.bot.moteur.configurer(self.page.r["comptes"])
        await self.page.bot.mettre_a_jour_statut()
        await self.page.afficher(interaction)


class VueComptes(VuePanneau):
    titre = "Comptes"

    def construire(self) -> None:
        async def ajouter(interaction: discord.Interaction) -> None:
            await interaction.response.send_modal(ModalCompte(self))

        bouton = self.bouton("Ajouter un compte", ajouter, 0, emoji="➕", style=discord.ButtonStyle.success)
        bouton.disabled = len(self.r["comptes"]) >= NB_COMPTES_MAX
        self.retour(0)
        comptes = list(self.r["comptes"])
        if comptes:
            menu: discord.ui.Select = discord.ui.Select(
                placeholder="➖ Retirer un compte…",
                options=[discord.SelectOption(label=c, value=c, emoji="👤") for c in comptes[:25]],
                row=1,
            )

            async def retirer(interaction: discord.Interaction) -> None:
                restant = [c for c in self.r["comptes"] if c != menu.values[0]]
                await self.r.definir("comptes", restant)
                self.bot.moteur.configurer(restant)
                await self.bot.mettre_a_jour_statut()
                await self.afficher(interaction)

            menu.callback = retirer  # type: ignore[method-assign]
            self.add_item(menu)

    def embed(self) -> discord.Embed:
        comptes = self.r["comptes"]
        lignes = [f"`{i + 1}.` 👤 **{c}**" for i, c in enumerate(comptes)] or ["Aucun compte."]
        lignes += ["", f"{len(comptes)}/{NB_COMPTES_MAX} comptes. Le nom doit être **exactement** celui du webhook."]
        return _embed(self.titre, lignes)


# ====================================================================== temps


def _entier(texte: str, mini: int, maxi: int, nom: str) -> int:
    try:
        valeur = int(texte.strip())
    except ValueError:
        raise ValueError(f"« {nom} » doit être un nombre entier.") from None
    if not mini <= valeur <= maxi:
        raise ValueError(f"« {nom} » doit être entre {mini} et {maxi}.")
    return valeur


class ModalTemps(discord.ui.Modal, title="Réglages de temps"):
    def __init__(self, page: VuePanneau) -> None:
        super().__init__()
        self.page = page
        r = page.r
        self.intervalle = discord.ui.TextInput(label="Résumé toutes les ... min (1 à 60)", default=str(r["resume_intervalle_min"]), max_length=2)
        self.delai = discord.ui.TextInput(label="Alerte absence après ... min (1 à 120)", default=str(r["delai_absence_min"]), max_length=3)
        self.periode = discord.ui.TextInput(label="Période des gains en min (5 à 1440)", default=str(r["periode_gains_min"]), max_length=4)
        self.estimation = discord.ui.TextInput(label="Durée d'estimation en h (1 à 48)", default=str(r["estimation_heures"]), max_length=2)
        self.heure = discord.ui.TextInput(label="Heure du rapport quotidien (HH:MM)", default=str(r["rapport_heure"]), max_length=5)
        for champ in (self.intervalle, self.delai, self.periode, self.estimation, self.heure):
            self.add_item(champ)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            valeurs = {
                "resume_intervalle_min": _entier(self.intervalle.value, 1, 60, "Résumé"),
                "delai_absence_min": _entier(self.delai.value, 1, 120, "Alerte absence"),
                "periode_gains_min": _entier(self.periode.value, 5, 1440, "Période des gains"),
                "estimation_heures": _entier(self.estimation.value, 1, 48, "Estimation"),
            }
            m = RE_HEURE.match(self.heure.value.strip())
            if not m:
                raise ValueError("L'heure du rapport doit ressembler à 21:00.")
            valeurs["rapport_heure"] = f"{int(m.group(1)):02d}:{m.group(2)}"
        except ValueError as exc:
            await repondre(interaction, embed=embed_erreur(str(exc)))
            return
        for cle, valeur in valeurs.items():
            await self.page.r.definir(cle, valeur)
        await self.page.afficher(interaction)


class ModalConservation(discord.ui.Modal, title="Conservation des données"):
    def __init__(self, page: VuePanneau) -> None:
        super().__init__()
        self.page = page
        self.jours = discord.ui.TextInput(label="Garder les données ... jours (7 à 3650)", default=str(page.r["purge_jours"]), max_length=4)
        self.add_item(self.jours)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            jours = _entier(self.jours.value, 7, 3650, "Jours")
        except ValueError as exc:
            await repondre(interaction, embed=embed_erreur(str(exc)))
            return
        await self.page.r.definir("purge_jours", jours)
        await self.page.afficher(interaction)


class VueTemps(VuePanneau):
    titre = "Temps"

    def construire(self) -> None:
        async def modifier(interaction: discord.Interaction) -> None:
            await interaction.response.send_modal(ModalTemps(self))

        async def conservation(interaction: discord.Interaction) -> None:
            await interaction.response.send_modal(ModalConservation(self))

        self.bouton("Modifier les temps", modifier, 0, emoji="✏️", style=discord.ButtonStyle.primary)
        self.bouton("Conservation", conservation, 0, emoji="🗑️")
        self.retour(0)
        self.bascule("resume_auto", "Résumé auto", 1)
        self.bascule("rapport_quotidien", "Rapport du jour", 1)
        self.bascule("rapport_hebdo", "Rapport de la semaine", 1)

    def embed(self) -> discord.Embed:
        r = self.r
        return _embed(self.titre, [
            f"📋 Résumé automatique : {oui_non(r['resume_auto'])} toutes les **{r['resume_intervalle_min']} min**",
            f"🔴 Alerte de disparition après **{r['delai_absence_min']} min**",
            f"📊 Période des gains dans le résumé : **{r['periode_gains_min']} min**",
            f"🔮 Durée d'estimation : **{r['estimation_heures']} h**",
            f"🌙 Rapport du jour : {oui_non(r['rapport_quotidien'])} à **{r['rapport_heure']}** · "
            f"rapport de la semaine (dimanche) : {oui_non(r['rapport_hebdo'])}",
            f"🗑️ Données gardées **{r['purge_jours']} jours**",
        ])


# ====================================================================== infos


class VueInfos(VuePanneau):
    titre = "Infos du résumé"

    def construire(self) -> None:
        cochees = set(self.r["resume_infos"])
        menu: discord.ui.Select = discord.ui.Select(
            placeholder="Coche ce qui apparaît dans le résumé…",
            min_values=0,
            max_values=len(INFOS_RESUME),
            options=[
                discord.SelectOption(label=libelle, value=cle, default=cle in cochees)
                for cle, libelle in INFOS_RESUME.items()
            ],
            row=0,
        )

        async def choisir(interaction: discord.Interaction) -> None:
            ordre = [c for c in INFOS_RESUME if c in menu.values]
            await self.r.definir("resume_infos", ordre)
            await self.afficher(interaction)

        menu.callback = choisir  # type: ignore[method-assign]
        self.add_item(menu)
        self.retour(1)

    def embed(self) -> discord.Embed:
        cochees = set(self.r["resume_infos"])
        return _embed(self.titre, [f"{oui_non(c in cochees)} {libelle}" for c, libelle in INFOS_RESUME.items()])


# ====================================================================== apparence


class ModalCouleur(discord.ui.Modal, title="Couleur personnalisée"):
    def __init__(self, page: VuePanneau) -> None:
        super().__init__()
        self.page = page
        actuelle = page.r["couleur"] if page.r["couleur"] != "auto" else "#5865F2"
        self.code = discord.ui.TextInput(label="Code couleur (ex. #5865F2)", default=actuelle, min_length=6, max_length=7)
        self.add_item(self.code)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        code = normaliser_hex(self.code.value)
        if code is None:
            await repondre(interaction, embed=embed_erreur("Code invalide. Exemple valide : `#5865F2`."))
            return
        await self.page.r.definir("couleur", code)
        await self.page.afficher(interaction)


class VueApparence(VuePanneau):
    titre = "Apparence"

    def construire(self) -> None:
        r = self.r
        formats: discord.ui.Select = discord.ui.Select(
            placeholder="Format du résumé",
            options=[discord.SelectOption(label=v, value=k, default=k == r["resume_format"]) for k, v in FORMATS_RESUME.items()],
            row=0,
        )

        async def choisir_format(interaction: discord.Interaction) -> None:
            await self.r.definir("resume_format", formats.values[0])
            await self.afficher(interaction)

        formats.callback = choisir_format  # type: ignore[method-assign]
        self.add_item(formats)

        options = [discord.SelectOption(label=nom, value=code, default=code == r["couleur"]) for code, nom in PALETTE.items()]
        if r["couleur"] not in PALETTE:
            options.append(discord.SelectOption(label=f"Perso {r['couleur']}", value=r["couleur"], default=True))
        couleurs: discord.ui.Select = discord.ui.Select(placeholder="Couleur du résumé", options=options[:25], row=1)

        async def choisir_couleur(interaction: discord.Interaction) -> None:
            await self.r.definir("couleur", couleurs.values[0])
            await self.afficher(interaction)

        couleurs.callback = choisir_couleur  # type: ignore[method-assign]
        self.add_item(couleurs)

        async def perso(interaction: discord.Interaction) -> None:
            await interaction.response.send_modal(ModalCouleur(self))

        self.bouton("Couleur perso", perso, 2, emoji="🎨")
        self.bascule("resume_boutons", "Boutons", 2)
        self.bascule("resume_supprimer_ancien", "Suppr. ancien", 2)
        self.bascule("resume_ping", "Ping résumé", 2)
        self.retour(3)

    def embed(self) -> discord.Embed:
        r = self.r
        couleur = r["couleur"]
        e = _embed(self.titre, [
            f"🖼️ Format : **{FORMATS_RESUME.get(r['resume_format'])}**",
            f"🎨 Couleur : **{PALETTE.get(couleur, couleur)}** (`{couleur}`)",
            f"🔘 Boutons sous le résumé : {oui_non(r['resume_boutons'])}",
            f"🗑️ Supprimer l'ancien résumé : {oui_non(r['resume_supprimer_ancien'])}",
            f"🔔 Mention dans le résumé auto : {oui_non(r['resume_ping'])}",
        ])
        if couleur != "auto":
            e.color = hex_vers_int(couleur) or BLEU
        return e


# ====================================================================== alertes


class VueAlertes(VuePanneau):
    titre = "Alertes"

    def construire(self) -> None:
        r = self.r
        pings: discord.ui.Select = discord.ui.Select(
            placeholder="Coche les alertes / mentions voulues…",
            min_values=0,
            max_values=len(PINGS),
            options=[discord.SelectOption(label=v, value=k, default=bool(r[k])) for k, v in PINGS.items()],
            row=0,
        )

        async def choisir_pings(interaction: discord.Interaction) -> None:
            for cle in PINGS:
                await self.r.definir(cle, cle in pings.values)
            await self.afficher(interaction)

        pings.callback = choisir_pings  # type: ignore[method-assign]
        self.add_item(pings)

        raretes: discord.ui.Select = discord.ui.Select(
            placeholder="Rareté minimum pour un drop rare",
            options=[
                discord.SelectOption(label=f"{x} et plus", value=x, default=x == r["rarete_min"])
                for x in list(r["raretes"])[:25]
            ],
            row=1,
        )

        async def choisir_rarete(interaction: discord.Interaction) -> None:
            await self.r.definir("rarete_min", raretes.values[0])
            await self.afficher(interaction)

        raretes.callback = choisir_rarete  # type: ignore[method-assign]
        self.add_item(raretes)

        sensibilite: discord.ui.Select = discord.ui.Select(
            placeholder="Sensibilité des anomalies",
            options=[
                discord.SelectOption(label=v, value=k, default=k == r["sensibilite_anomalies"])
                for k, v in SENSIBILITES.items()
            ],
            row=2,
        )

        async def choisir_sensibilite(interaction: discord.Interaction) -> None:
            await self.r.definir("sensibilite_anomalies", sensibilite.values[0])
            await self.afficher(interaction)

        sensibilite.callback = choisir_sensibilite  # type: ignore[method-assign]
        self.add_item(sensibilite)

        async def salons(interaction: discord.Interaction) -> None:
            await self.afficher(interaction, VueSalons(self.bot, self.auteur_id))

        self.bouton("Salons", salons, 3, emoji="📺", style=discord.ButtonStyle.primary)
        self.retour(3)

    def embed(self) -> discord.Embed:
        r = self.r
        lignes = [f"{oui_non(r[k])} {v}" for k, v in PINGS.items()]
        lignes += [
            "",
            f"🎁 Drop rare à partir de : **{r['rarete_min']}**",
            f"⚠️ Sensibilité des anomalies : **{SENSIBILITES.get(r['sensibilite_anomalies'])}**",
            f"📺 Alertes : {_salon(r['salon_alertes'])} · résumés : {_salon(r['salon_resumes'])}",
            "",
            "-# Les alertes sont toujours envoyées ; ces cases choisissent si tu es **mentionné**.",
        ]
        return _embed(self.titre, lignes)


class VueSalons(VuePanneau):
    titre = "Salons"

    def construire(self) -> None:
        types = [discord.ChannelType.text, discord.ChannelType.news]
        alertes: discord.ui.ChannelSelect = discord.ui.ChannelSelect(
            placeholder="📢 Salon des alertes…", channel_types=types, row=0
        )
        resumes: discord.ui.ChannelSelect = discord.ui.ChannelSelect(
            placeholder="📋 Salon des résumés…", channel_types=types, row=1
        )

        def fabrique(menu: discord.ui.ChannelSelect, cle: str) -> Callable[[discord.Interaction], Awaitable[None]]:
            async def choisir(interaction: discord.Interaction) -> None:
                salon = menu.values[0]
                await self.r.definir(cle, int(salon.id))
                await self.afficher(interaction)

            return choisir

        alertes.callback = fabrique(alertes, "salon_alertes")  # type: ignore[method-assign]
        resumes.callback = fabrique(resumes, "salon_resumes")  # type: ignore[method-assign]
        self.add_item(alertes)
        self.add_item(resumes)

        async def remettre(interaction: discord.Interaction) -> None:
            await self.r.definir("salon_alertes", None)
            await self.r.definir("salon_resumes", None)
            await self.afficher(interaction)

        self.bouton("Utiliser le salon du webhook", remettre, 2, emoji="↩️")
        self.retour(2, VueAlertes)

    def embed(self) -> discord.Embed:
        r = self.r
        return _embed(self.titre, [
            f"📢 Alertes : {_salon(r['salon_alertes'])}",
            f"📋 Résumés et rapports : {_salon(r['salon_resumes'])}",
            "",
            "Le bot doit pouvoir **voir** et **écrire** dans ces salons.",
        ])


# ====================================================================== IA


class ModalIA(discord.ui.Modal, title="IA : réglages avancés"):
    def __init__(self, page: VuePanneau) -> None:
        super().__init__()
        self.page = page
        r = page.r
        self.keep_alive = discord.ui.TextInput(label="Décharger le modèle après ... min (1 à 60)", default=str(r["ia_keep_alive_min"]), max_length=2)
        self.limite = discord.ui.TextInput(label="Questions max par minute (1 à 30)", default=str(r["ia_limite_minute"]), max_length=2)
        self.memoire = discord.ui.TextInput(label="Mémoire : derniers échanges (0 à 20)", default=str(r["ia_memoire"]), max_length=2)
        for champ in (self.keep_alive, self.limite, self.memoire):
            self.add_item(champ)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            valeurs = {
                "ia_keep_alive_min": _entier(self.keep_alive.value, 1, 60, "Décharger après"),
                "ia_limite_minute": _entier(self.limite.value, 1, 30, "Questions par minute"),
                "ia_memoire": _entier(self.memoire.value, 0, 20, "Mémoire"),
            }
        except ValueError as exc:
            await repondre(interaction, embed=embed_erreur(str(exc)))
            return
        for cle, valeur in valeurs.items():
            await self.page.r.definir(cle, valeur)
        await self.page.afficher(interaction)


class VueIA(VuePanneau):
    titre = "IA locale (Ollama)"

    def __init__(self, bot: TekkitBot, auteur_id: int) -> None:
        super().__init__(bot, auteur_id)
        self.modeles: list[str] = []

    async def preparer(self) -> None:
        cog = self.bot.get_cog("IA")
        if cog is not None:
            try:
                self.modeles = await cog.moteur.modeles_installes()  # type: ignore[attr-defined]
            except Exception:
                self.modeles = []
        self.construire()

    def construire(self) -> None:
        r = self.r
        self.bascule("ia_active", "IA", 0)

        async def tester(interaction: discord.Interaction) -> None:
            cog = self.bot.get_cog("IA")
            if cog is None:
                await repondre(interaction, embed=embed_erreur("Le module IA n'est pas chargé."))
                return
            await cog.tester(interaction)  # type: ignore[attr-defined]

        async def avance(interaction: discord.Interaction) -> None:
            await interaction.response.send_modal(ModalIA(self))

        self.bouton("Tester l'IA", tester, 0, emoji="🧪", style=discord.ButtonStyle.primary)
        self.bouton("Avancé", avance, 0, emoji="⚙️")
        self.retour(0)

        noms = list(dict.fromkeys([r["ia_modele"], *self.modeles, MODELE_IA_DEFAUT, MODELE_IA_LEGER]))[:25]
        modeles: discord.ui.Select = discord.ui.Select(
            placeholder="Modèle Ollama",
            options=[
                discord.SelectOption(
                    label=tronquer(nom, 100),
                    value=nom[:100],
                    default=nom == r["ia_modele"],
                    description="installé" if nom in self.modeles else "pas encore téléchargé",
                )
                for nom in noms
            ],
            row=1,
        )

        async def choisir_modele(interaction: discord.Interaction) -> None:
            await self.r.definir("ia_modele", modeles.values[0])
            await self.afficher(interaction)

        modeles.callback = choisir_modele  # type: ignore[method-assign]
        self.add_item(modeles)

        modes: discord.ui.Select = discord.ui.Select(
            placeholder="Mode",
            options=[discord.SelectOption(label=v, value=k, default=k == r["ia_mode"]) for k, v in MODES_IA.items()],
            row=2,
        )

        async def choisir_mode(interaction: discord.Interaction) -> None:
            await self.r.definir("ia_mode", modes.values[0])
            await self.afficher(interaction)

        modes.callback = choisir_mode  # type: ignore[method-assign]
        self.add_item(modes)

        utilisateurs: discord.ui.UserSelect = discord.ui.UserSelect(
            placeholder="👥 Utilisateurs autorisés (en plus de toi)…",
            min_values=0,
            max_values=25,
            default_values=[discord.Object(id=int(u)) for u in list(r["ia_utilisateurs"])[:25]],
            row=3,
        )

        async def choisir_utilisateurs(interaction: discord.Interaction) -> None:
            ids = [int(u.id) for u in utilisateurs.values if not getattr(u, "bot", False)]
            await self.r.definir("ia_utilisateurs", ids)
            await self.afficher(interaction)

        utilisateurs.callback = choisir_utilisateurs  # type: ignore[method-assign]
        self.add_item(utilisateurs)

    def embed(self) -> discord.Embed:
        r = self.r
        installe = r["ia_modele"] in self.modeles
        autorises = ", ".join(f"<@{u}>" for u in r["ia_utilisateurs"]) or "toi uniquement"
        lignes = [
            f"🤖 IA : {oui_non(r['ia_active'])}",
            f"🧠 Modèle : `{r['ia_modele']}` " + ("✅ installé" if installe else "⚠️ pas trouvé dans Ollama"),
            f"⚡ Mode : **{MODES_IA.get(r['ia_mode'])}**",
            f"💤 Déchargé de la mémoire après **{r['ia_keep_alive_min']} min** sans question",
            f"🚦 Max **{r['ia_limite_minute']}** questions / min / personne · mémoire : **{r['ia_memoire']}** échanges",
            f"👥 Autorisés : {autorises}",
        ]
        if not installe:
            lignes += ["", f"Pour l'installer : `ollama pull {r['ia_modele']}`"]
        return _embed(self.titre, lignes)


# ====================================================================== OSINT


class VueOSINT(VuePanneau):
    titre = "OSINT"

    def construire(self) -> None:
        self.bascule("osint_active", "OSINT", 0)

        async def journal(interaction: discord.Interaction) -> None:
            cog = self.bot.get_cog("OSINT")
            if cog is None:
                await repondre(interaction, embed=embed_erreur("Le module OSINT n'est pas chargé."))
                return
            await cog.afficher_journal(interaction)  # type: ignore[attr-defined]

        self.bouton("Voir le journal", journal, 0, emoji="📜")
        self.retour(0)

    def embed(self) -> discord.Embed:
        return _embed(self.titre, [
            f"🛡️ Commandes OSINT : {oui_non(self.r['osint_active'])}",
            "",
            "Uniquement : domaines, adresses IP, liens, entreprises (BCE), tes propres mots de passe et images.",
            "Jamais de recherche sur des personnes privées. Chaque recherche est notée dans le journal.",
        ])


PAGES: dict[str, type[VuePanneau]] = {
    "comptes": VueComptes,
    "temps": VueTemps,
    "infos": VueInfos,
    "apparence": VueApparence,
    "alertes": VueAlertes,
    "ia": VueIA,
    "osint": VueOSINT,
}
