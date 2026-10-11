"""Limites imposées par Discord, et outils pour les respecter / les vérifier."""

from __future__ import annotations

from collections import Counter

import discord

from bot.ui.format import tronquer

MAX_LIGNES_VUE = 5
MAX_ELEMENTS_LIGNE = 5
MAX_OPTIONS_MENU = 25
MAX_TEXTE_OPTION = 100
MAX_DESCRIPTION_OPTION = 100
MAX_LABEL_BOUTON = 80
MAX_PLACEHOLDER = 150
MAX_CUSTOM_ID = 100
MAX_CHAMPS_EMBED = 25
MAX_NOM_CHAMP = 256
MAX_VALEUR_CHAMP = 1024
MAX_TITRE_EMBED = 256
MAX_DESCRIPTION_EMBED = 4096
MAX_PIED_EMBED = 2048
MAX_TOTAL_EMBED = 6000
MAX_MESSAGE = 2000
MAX_CHAMPS_MODAL = 5
MAX_LABEL_MODAL = 45


def taille_embed(embed: discord.Embed) -> int:
    return len(embed)


def securiser_embed(embed: discord.Embed) -> discord.Embed:
    """Coupe ce qui dépasse les limites Discord pour qu'un envoi ne plante jamais."""
    if embed.title:
        embed.title = tronquer(embed.title, MAX_TITRE_EMBED)
    if embed.description:
        embed.description = tronquer(embed.description, MAX_DESCRIPTION_EMBED)
    champs = embed.fields[:MAX_CHAMPS_EMBED]
    embed.clear_fields()
    for c in champs:
        embed.add_field(
            name=tronquer(c.name or "​", MAX_NOM_CHAMP),
            value=tronquer(c.value or "​", MAX_VALEUR_CHAMP),
            inline=c.inline,
        )
    if embed.footer and embed.footer.text:
        embed.set_footer(text=tronquer(embed.footer.text, MAX_PIED_EMBED), icon_url=embed.footer.icon_url)
    # Trop long au total : on raccourcit les champs les plus longs
    while len(embed) > MAX_TOTAL_EMBED and embed.fields:
        index, plus_long = max(enumerate(embed.fields), key=lambda p: len(p[1].value or ""))
        valeur = plus_long.value or ""
        nouvelle = tronquer(valeur, max(20, len(valeur) - (len(embed) - MAX_TOTAL_EMBED) - 10))
        if nouvelle == valeur:
            embed.remove_field(index)
        else:
            embed.set_field_at(index, name=plus_long.name, value=nouvelle, inline=plus_long.inline)
    if len(embed) > MAX_TOTAL_EMBED and embed.description:
        embed.description = tronquer(embed.description, max(0, len(embed.description) - (len(embed) - MAX_TOTAL_EMBED)))
    return embed


def verifier_embed(embed: discord.Embed) -> list[str]:
    """Liste des problèmes (vide si l'embed respecte toutes les limites)."""
    problemes = []
    if embed.title and len(embed.title) > MAX_TITRE_EMBED:
        problemes.append("titre trop long")
    if embed.description and len(embed.description) > MAX_DESCRIPTION_EMBED:
        problemes.append("description trop longue")
    if len(embed.fields) > MAX_CHAMPS_EMBED:
        problemes.append("trop de champs")
    for c in embed.fields:
        if len(c.name or "") > MAX_NOM_CHAMP:
            problemes.append(f"nom de champ trop long : {c.name[:30]}")
        if len(c.value or "") > MAX_VALEUR_CHAMP:
            problemes.append(f"valeur de champ trop longue : {c.name}")
    if len(embed) > MAX_TOTAL_EMBED:
        problemes.append(f"embed trop long ({len(embed)} caractères)")
    return problemes


def verifier_vue(vue: discord.ui.View) -> list[str]:
    """Vérifie qu'une vue respecte les limites Discord. Renvoie la liste des problèmes."""
    problemes: list[str] = []
    largeur_par_ligne: Counter[int] = Counter()
    for item in vue.children:
        # Ligne réelle choisie par discord.py (placement automatique ou ligne imposée)
        ligne = item._rendered_row if item._rendered_row is not None else item.row
        if ligne is None:
            problemes.append(f"élément sans ligne : {type(item).__name__}")
            continue
        largeur_par_ligne[ligne] += item.width
        if isinstance(item, discord.ui.Button):
            if item.label and len(item.label) > MAX_LABEL_BOUTON:
                problemes.append(f"label de bouton trop long : {item.label[:30]}")
        if isinstance(item, discord.ui.Select):
            if len(item.options) > MAX_OPTIONS_MENU:
                problemes.append(f"menu avec trop d'options ({len(item.options)})")
            if item.max_values > max(1, len(item.options)):
                problemes.append("max_values plus grand que le nombre d'options")
            for o in item.options:
                if len(o.label) > MAX_TEXTE_OPTION:
                    problemes.append(f"option trop longue : {o.label[:30]}")
                if o.description and len(o.description) > MAX_DESCRIPTION_OPTION:
                    problemes.append(f"description d'option trop longue : {o.label[:30]}")
                if len(o.value) > MAX_TEXTE_OPTION:
                    problemes.append(f"valeur d'option trop longue : {o.label[:30]}")
        if isinstance(item, (discord.ui.Select, discord.ui.ChannelSelect, discord.ui.UserSelect)):
            if item.placeholder and len(item.placeholder) > MAX_PLACEHOLDER:
                problemes.append("placeholder trop long")
        custom_id = getattr(item, "custom_id", None)
        if custom_id and len(custom_id) > MAX_CUSTOM_ID:
            problemes.append("custom_id trop long")
    for ligne, largeur in largeur_par_ligne.items():
        if ligne >= MAX_LIGNES_VUE:
            problemes.append(f"ligne {ligne} : Discord n'autorise que 5 lignes (0 à 4)")
        if largeur > MAX_ELEMENTS_LIGNE:
            problemes.append(f"ligne {ligne} trop remplie ({largeur}/5)")
    return problemes


def verifier_modal(modal: discord.ui.Modal) -> list[str]:
    problemes = []
    champs = [c for c in modal.children if isinstance(c, discord.ui.TextInput)]
    if len(champs) > MAX_CHAMPS_MODAL:
        problemes.append("modal avec plus de 5 champs")
    if modal.title and len(modal.title) > MAX_LABEL_MODAL:
        problemes.append("titre de modal trop long")
    for c in champs:
        if c.label and len(c.label) > MAX_LABEL_MODAL:
            problemes.append(f"label de champ trop long : {c.label}")
    return problemes
