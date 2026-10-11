"""Construction de tous les embeds du bot (même structure, mêmes emojis partout)."""

from __future__ import annotations

import time
from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any

import discord

from bot.calculs import PERIODES, Gains, StatsCompte, additionner_estimations
from bot.config import RARETES_DEFAUT
from bot.database import DropEnregistre, Objectif
from bot.moteur_surveillance import Alerte
from bot.services import TYPES_OBJECTIF, EstimationCompte, EtatCompteResume
from bot.ui.couleurs import BLEU, GRIS, ORANGE, ROUGE, VERT, couleur_resume
from bot.ui.format import EMOJI, barre, formater_duree, nombre, pluriel, ts
from bot.ui.limites import securiser_embed

PIED = "Tekkit Watch"


def _embed(titre: str, description: str | None = None, couleur: int = BLEU) -> discord.Embed:
    e = discord.Embed(title=titre, description=description, color=couleur)
    e.set_footer(text=PIED)
    return e


def embed_info(titre: str, texte: str) -> discord.Embed:
    return securiser_embed(_embed(titre, texte, BLEU))


def embed_succes(texte: str, titre: str = "✅ C'est fait") -> discord.Embed:
    return securiser_embed(_embed(titre, texte, VERT))


def embed_erreur(texte: str, titre: str = "😕 Oups") -> discord.Embed:
    return securiser_embed(_embed(titre, texte, ROUGE))


def embed_attention(texte: str, titre: str = "⚠️ Attention") -> discord.Embed:
    return securiser_embed(_embed(titre, texte, ORANGE))


# ---------------------------------------------------------------- objets


def texte_objets(objets: Counter[str], raretes: Sequence[str] = RARETES_DEFAUT) -> str:
    """« 3 Common · 1 Rare » trié de la rareté la plus haute à la plus basse."""
    if not objets:
        return "aucun"
    ordre = {r: i for i, r in enumerate(raretes)}
    tries = sorted(objets.items(), key=lambda p: -ordre.get(p[0], -1))
    return " · ".join(f"{n} {r}" for r, n in tries)


# ---------------------------------------------------------------- résumé


def _ligne_connexion(e: EtatCompteResume) -> str:
    if e.en_ligne is None:
        return f"{EMOJI['inconnu']} Jamais vu"
    vue = e.derniere.horodatage if e.derniere else None
    if e.en_ligne:
        return f"{EMOJI['en_ligne']} En ligne · dernière mission {ts(vue)}"
    return f"{EMOJI['absent']} Absent · dernière mission {ts(vue)}"


def _ligne_zone(e: EtatCompteResume) -> str:
    if e.zone is None:
        return "🛡️ Zone : inconnue"
    return f"🛡️ Zone : {e.zone}" if e.est_safe else f"🚨 Zone : **{e.zone}**"


def _niveau(e: EtatCompteResume) -> str:
    d = e.derniere
    if not d or (d.level is None and d.prestige is None):
        return ""
    morceaux = []
    if d.level is not None:
        morceaux.append(f"Niv. {d.level}")
    if d.prestige is not None:
        morceaux.append(f"Prestige {d.prestige}")
    return " · ".join(morceaux)


def lignes_compte(
    e: EtatCompteResume, infos: Sequence[str], periode_min: int, raretes: Sequence[str]
) -> list[str]:
    """Lignes affichées pour un compte, selon les infos cochées."""
    g, d = e.gains, e.derniere
    if d is None:
        return [f"{EMOJI['inconnu']} Jamais vu : aucune mission reçue pour ce compte."]
    lignes = []
    if "connexion" in infos:
        lignes.append(_ligne_connexion(e))
    if "zone" in infos:
        lignes.append(_ligne_zone(e))
    if "niveau" in infos and _niveau(e):
        lignes.append(f"{EMOJI['niveau']} {_niveau(e)}")
    if "missions" in infos:
        lignes.append(f"{EMOJI['missions']} {pluriel(g.missions, 'mission')} ({periode_min} min)")
    if "gold" in infos:
        total = f" · total {nombre(d.gold_total)}" if d and d.gold_total is not None else ""
        lignes.append(f"{EMOJI['gold']} +{nombre(g.gold)} gold{total}")
    if "xp" in infos:
        lignes.append(f"{EMOJI['xp']} +{nombre(g.xp)} XP")
    if "gems" in infos:
        total = f" · total {nombre(d.gems_total)}" if d and d.gems_total is not None else ""
        lignes.append(f"{EMOJI['gems']} +{nombre(g.gems)} gems{total}")
    if "temps_moyen" in infos:
        lignes.append(f"{EMOJI['temps']} {formater_duree(g.duree_moyenne_s)} / mission")
    if "objets" in infos:
        lignes.append(f"{EMOJI['drops']} {texte_objets(g.objets, raretes)}")
    if "estimation" in infos:
        if e.estimation:
            est = e.estimation
            lignes.append(
                f"{EMOJI['estimation']} {est.heures:g} h : ~{nombre(est.gold)} gold · "
                f"~{nombre(est.gems)} gems"
            )
        else:
            lignes.append(f"{EMOJI['estimation']} Estimation : pas encore assez de recul")
    if "changements" in infos and e.evenements:
        for ev in e.evenements[:3]:
            lignes.append(f"📜 {ev.texte} {ts(ev.horodatage)}")
    if "session" in infos:
        s = e.session
        lignes.append(
            f"🧮 Session : {pluriel(s.missions, 'mission')} · {nombre(s.gold)} gold · "
            f"{nombre(s.xp)} XP · {nombre(s.gems)} gems"
        )
    return lignes


def _total(etats: Sequence[EtatCompteResume], attr: str = "gains") -> Gains:
    total = Gains()
    for e in etats:
        g: Gains = getattr(e, attr)
        total.missions += g.missions
        total.gold += g.gold
        total.xp += g.xp
        total.gems += g.gems
        total.objets.update(g.objets)
    return total


def lignes_bilan(
    etats: Sequence[EtatCompteResume], periode_min: int, raretes: Sequence[str]
) -> list[str]:
    t = _total(etats)
    actifs = sum(1 for e in etats if e.en_ligne)
    gold_h = sum(e.rythme.gold_h for e in etats if e.rythme)
    gems_h = sum(e.rythme.gems_h for e in etats if e.rythme)
    return [
        f"👥 {actifs}/{len(etats)} comptes en ligne",
        f"{EMOJI['missions']} {pluriel(t.missions, 'mission')} · {EMOJI['gold']} {nombre(t.gold)} gold · "
        f"{EMOJI['xp']} {nombre(t.xp)} XP · {EMOJI['gems']} {nombre(t.gems)} gems ({periode_min} min)",
        f"⚡ Rythme actuel : {nombre(gold_h)} gold/h · {nombre(gems_h)} gems/h",
        f"{EMOJI['drops']} {texte_objets(t.objets, raretes)}",
    ]


def embed_resume(
    etats: Sequence[EtatCompteResume],
    reglages: Mapping[str, Any],
    pause: bool = False,
    format_: str | None = None,
    maintenant: float | None = None,
) -> discord.Embed:
    """Le résumé du farm, dans le format choisi."""
    maintenant = maintenant or time.time()
    format_ = format_ or str(reglages.get("resume_format", "detaille"))
    infos = list(reglages.get("resume_infos") or [])
    periode_min = int(reglages.get("periode_gains_min", 60))
    raretes = list(reglages.get("raretes") or RARETES_DEFAUT)
    couleur = couleur_resume(reglages, etats)
    entete = f"Mis à jour {ts(maintenant)}" + (" · ⏸️ **surveillance en pause**" if pause else "")
    e = _embed("📋 Résumé du farm", entete, couleur)

    if not etats:
        e.description = (
            entete + "\n\nAucun compte configuré. Ajoute-en avec `/parametres` → 👤 Comptes."
        )
        return securiser_embed(e)

    if format_ == "texte":
        e.description = entete + "\n" + texte_copiable(etats, reglages)
    elif format_ == "compact":
        lignes = [entete, ""]
        for et in etats:
            lignes.append(ligne_compacte(et))
        if "bilan" in infos:
            lignes += ["", "**📊 Bilan**", *lignes_bilan(etats, periode_min, raretes)]
        e.description = "\n".join(lignes)
    else:
        for et in etats:
            icone = {True: EMOJI["en_ligne"], False: EMOJI["absent"], None: EMOJI["inconnu"]}[
                et.en_ligne
            ]
            niveau = f" · {_niveau(et)}" if "niveau" in infos and _niveau(et) else ""
            valeur = "\n".join(
                lignes_compte(et, [i for i in infos if i != "niveau"], periode_min, raretes)
            )
            e.add_field(name=f"{icone} {et.nom}{niveau}", value=valeur or "—", inline=False)
        if "bilan" in infos:
            e.add_field(
                name="📊 Bilan",
                value="\n".join(lignes_bilan(etats, periode_min, raretes)),
                inline=False,
            )
    e.set_footer(text=f"{PIED} · {'⏸️ en pause' if pause else '👀 surveillance active'}")
    return securiser_embed(e)


def ligne_compacte(e: EtatCompteResume) -> str:
    icone = {True: EMOJI["en_ligne"], False: EMOJI["absent"], None: EMOJI["inconnu"]}[e.en_ligne]
    zone = "🛡️" if e.est_safe else ("🚨" if e.est_safe is False else "❔")
    niveau = f" · {_niveau(e)}" if _niveau(e) else ""
    g = e.gains
    return (
        f"{icone} **{e.nom}**{niveau} · {zone} · {EMOJI['missions']} {nombre(g.missions)} · "
        f"{EMOJI['gold']} +{nombre(g.gold)} · {EMOJI['xp']} +{nombre(g.xp)} · {EMOJI['gems']} +{nombre(g.gems)}"
    )


def texte_copiable(etats: Sequence[EtatCompteResume], reglages: Mapping[str, Any]) -> str:
    """Résumé en texte brut dans un bloc de code (facile à copier-coller)."""
    periode_min = int(reglages.get("periode_gains_min", 60))
    lignes = [f"Résumé Tekkit Watch ({periode_min} dernières minutes)", ""]
    for e in etats:
        d = e.derniere
        etat = {True: "EN LIGNE", False: "ABSENT", None: "JAMAIS VU"}[e.en_ligne]
        lignes.append(f"{e.nom} [{etat}] zone: {e.zone or '?'}")
        if d is not None:
            lignes.append(
                f"  niveau {d.level if d.level is not None else '?'} | prestige {d.prestige if d.prestige is not None else '?'}"
            )
        g = e.gains
        lignes.append(
            f"  missions {g.missions} | gold +{nombre(g.gold)} | xp +{nombre(g.xp)} | gems +{nombre(g.gems)}"
        )
        lignes.append(
            f"  temps moyen {formater_duree(g.duree_moyenne_s)} | objets {texte_objets(g.objets)}"
        )
        if e.estimation:
            lignes.append(
                f"  estimation {e.estimation.heures:g} h : ~{nombre(e.estimation.gold)} gold"
            )
        lignes.append("")
    t = _total(etats)
    lignes.append(
        f"TOTAL : {t.missions} missions | gold +{nombre(t.gold)} | xp +{nombre(t.xp)} | gems +{nombre(t.gems)}"
    )
    texte = "\n".join(lignes).replace(" ", " ")
    if len(texte) > 3900:
        texte = texte[:3890] + "\n…"
    return f"```\n{texte}\n```"


# ---------------------------------------------------------------- alertes


def embed_alerte(alerte: Alerte) -> discord.Embed:
    e = discord.Embed(
        title=alerte.titre,
        description=f"{alerte.texte}\n\n🕒 {ts(alerte.horodatage)}",
        color=alerte.couleur,
    )
    e.set_footer(text=f"{PIED} · {alerte.compte}")
    return securiser_embed(e)


# ---------------------------------------------------------------- estimation


def embed_estimation(heures: float, estimations: Sequence[EstimationCompte]) -> discord.Embed:
    e = _embed(f"🔮 Estimation sur {heures:g} h", "Au rythme des **30 dernières minutes**.", BLEU)
    disponibles = []
    avertissements = []
    for est in estimations:
        if est.en_ligne is False:
            avertissements.append(
                f"⚠️ **{est.nom}** est déconnecté : son estimation risque d'être fausse."
            )
        if est.estimation is None:
            e.add_field(
                name=f"⚪ {est.nom}",
                value="Pas encore assez de recul (au moins 2 min de données).",
                inline=True,
            )
            continue
        disponibles.append(est.estimation)
        x = est.estimation
        e.add_field(
            name=f"{EMOJI['en_ligne'] if est.en_ligne else EMOJI['absent']} {est.nom}",
            value=(
                f"{EMOJI['gold']} {nombre(x.gold)} gold\n{EMOJI['xp']} {nombre(x.xp)} XP\n"
                f"{EMOJI['gems']} {nombre(x.gems)} gems\n{EMOJI['missions']} {nombre(x.missions)} missions"
            ),
            inline=True,
        )
    if disponibles:
        t = additionner_estimations(disponibles, heures)
        e.add_field(
            name="📊 Total",
            value=(
                f"{EMOJI['gold']} **{nombre(t.gold)}** gold · {EMOJI['xp']} **{nombre(t.xp)}** XP · "
                f"{EMOJI['gems']} **{nombre(t.gems)}** gems · {EMOJI['missions']} **{nombre(t.missions)}** missions"
            ),
            inline=False,
        )
    if avertissements:
        e.description = (e.description or "") + "\n\n" + "\n".join(avertissements)
    return securiser_embed(e)


# ---------------------------------------------------------------- stats


def valeur_stats(s: StatsCompte, raretes: Sequence[str]) -> str:
    g = s.gains
    lignes = [
        f"{EMOJI['gold']} {nombre(g.gold)} gold (≈ {nombre(s.par_heure(g.gold))}/h)",
        f"{EMOJI['xp']} {nombre(g.xp)} XP (≈ {nombre(s.par_heure(g.xp))}/h)",
        f"{EMOJI['gems']} {nombre(g.gems)} gems (≈ {nombre(s.par_heure(g.gems))}/h)",
        f"{EMOJI['missions']} {pluriel(g.missions, 'mission')} (≈ {nombre(s.par_heure(g.missions))}/h)",
        f"{EMOJI['temps']} Temps de jeu : {formater_duree(s.temps_actif_s)} · dispo {s.disponibilite:.0f} %",
        f"{EMOJI['temps']} Moyenne : {formater_duree(g.duree_moyenne_s)} / mission",
    ]
    if s.meilleure_heure:
        h, gold = s.meilleure_heure
        lignes.append(f"🕐 Meilleure heure : {h} h – {h + 1} h (≈ {nombre(gold)} gold)")
    if g.record_gold:
        lignes.append(f"🏆 Record : {nombre(g.record_gold)} gold en une mission")
    lignes.append(f"{EMOJI['drops']} {texte_objets(g.objets, raretes)}")
    return "\n".join(lignes)


def embed_stats(
    periode: str, debut: float, stats: Sequence[StatsCompte], raretes: Sequence[str]
) -> discord.Embed:
    e = _embed(f"📈 Stats · {PERIODES.get(periode, periode)}", f"Depuis {ts(debut, 'f')}", BLEU)
    if not stats:
        e.description = "Aucun compte configuré."
        return securiser_embed(e)
    for s in stats:
        e.add_field(
            name=f"👤 {s.compte}",
            value=valeur_stats(s, raretes)
            if s.gains.missions
            else "Aucune mission sur cette période.",
            inline=False,
        )
    if len(stats) > 1:
        t = Gains()
        for s in stats:
            t.missions += s.gains.missions
            t.gold += s.gains.gold
            t.xp += s.gains.xp
            t.gems += s.gains.gems
        e.add_field(
            name="📊 Total",
            value=(
                f"{EMOJI['missions']} {nombre(t.missions)} · {EMOJI['gold']} {nombre(t.gold)} · "
                f"{EMOJI['xp']} {nombre(t.xp)} · {EMOJI['gems']} {nombre(t.gems)}"
            ),
            inline=False,
        )
    return securiser_embed(e)


def embed_comparer(periode: str, stats: Sequence[StatsCompte]) -> discord.Embed:
    e = _embed(f"⚖️ Comparaison · {PERIODES.get(periode, periode)}", None, BLEU)
    if not stats:
        e.description = "Aucun compte configuré."
        return securiser_embed(e)
    largeur = max(6, *(len(s.compte) for s in stats))
    entete = (
        f"{'Compte':<{largeur}} {'Gold/h':>9} {'XP/h':>8} {'Gems/h':>7} {'Mis/h':>5} {'Dispo':>5}"
    )
    lignes = [entete, "-" * len(entete)]
    for s in stats:
        g = s.gains
        lignes.append(
            f"{s.compte:<{largeur}} {nombre(s.par_heure(g.gold)):>9} {nombre(s.par_heure(g.xp)):>8} "
            f"{nombre(s.par_heure(g.gems)):>7} {nombre(s.par_heure(g.missions)):>5} {s.disponibilite:>4.0f}%"
        )
    tableau = "\n".join(lignes).replace(" ", " ")
    e.description = f"```\n{tableau}\n```"
    actifs = [s for s in stats if s.gains.missions]
    if actifs:
        meilleurs = {
            f"{EMOJI['gold']} Plus de gold/h": max(actifs, key=lambda s: s.par_heure(s.gains.gold)),
            f"{EMOJI['gems']} Plus de gems/h": max(actifs, key=lambda s: s.par_heure(s.gains.gems)),
            f"{EMOJI['temps']} Missions les plus rapides": min(
                actifs, key=lambda s: s.gains.duree_moyenne_s or float("inf")
            ),
            "🟢 Le plus disponible": max(actifs, key=lambda s: s.disponibilite),
        }
        e.add_field(
            name="🏆 Meilleurs",
            value="\n".join(f"{k} : **{v.compte}**" for k, v in meilleurs.items()),
            inline=False,
        )
    return securiser_embed(e)


# ---------------------------------------------------------------- drops


def pages_drops(
    drops: Sequence[DropEnregistre], titre: str, par_page: int = 15
) -> list[discord.Embed]:
    if not drops:
        return [_embed(titre, "Aucun objet trouvé avec ces filtres.", GRIS)]
    pages = []
    for i in range(0, len(drops), par_page):
        lignes = [
            f"{ts(d.horodatage)} · **{d.compte}** · {d.nom} ({d.rarete})"
            + (f" ×{d.quantite}" if d.quantite > 1 else "")
            for d in drops[i : i + par_page]
        ]
        e = _embed(titre, "\n".join(lignes), 0x9B59B6)
        e.set_footer(
            text=f"{PIED} · page {i // par_page + 1}/{(len(drops) - 1) // par_page + 1} · {len(drops)} objets"
        )
        pages.append(securiser_embed(e))
    return pages


# ---------------------------------------------------------------- objectifs


def ligne_objectif(o: Objectif, actuel: int | None, fraction: float, quand: float | None) -> str:
    libelle = TYPES_OBJECTIF.get(o.type, o.type)
    texte = f"**#{o.id} · {o.compte}** · {libelle} : {nombre(actuel)} / {nombre(o.valeur_cible)}\n{barre(fraction)}"
    if o.atteint_le:
        texte += f"\n🎉 Atteint {ts(o.atteint_le)}"
    elif quand:
        texte += f"\n📅 Prévu vers {ts(quand, 'f')} ({ts(quand)})"
    else:
        texte += "\n📅 Date d'atteinte : pas encore estimable"
    return texte


def embed_rapport(
    titre: str,
    stats: Sequence[StatsCompte],
    records: Sequence[str],
    raretes: Sequence[str],
    debut: float,
) -> discord.Embed:
    e = _embed(titre, f"Depuis {ts(debut, 'f')}", VERT)
    for s in stats:
        e.add_field(
            name=f"👤 {s.compte}",
            value=valeur_stats(s, raretes) if s.gains.missions else "Aucune mission.",
            inline=False,
        )
    e.add_field(
        name="🏆 Records battus",
        value="\n".join(records) if records else "Aucun record battu cette fois-ci.",
        inline=False,
    )
    return securiser_embed(e)
