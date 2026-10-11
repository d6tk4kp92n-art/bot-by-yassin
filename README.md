# 👀 Tekkit Watch

Bot Discord qui surveille ton farm AFK sur **Attack on Titan: Revolution** (Roblox), à partir des messages du webhook **« Tekkit | Rewards Logger »**.

- 🔴 **Alerte** si un compte disparaît (une seule mention), 🟢 message quand il revient
- 🚨 **Zone** : alerte si un compte quitte la zone Safe
- 🎁 **Drops rares**, ⚠️ **anomalies** (missions lentes, gains en chute, compte bloqué)
- 📋 **Résumés automatiques** avec boutons, 📈 stats, 🔮 estimations, 📊 graphiques, 🎯 objectifs, 📤 export Excel
- 🤖 **IA gratuite en local** (Ollama) qui connaît tes vraies stats
- 🛡️ **OSINT légal** : domaines, IP, liens suspects, entreprises belges (BCE), fuite de **tes** mots de passe, métadonnées de **tes** images

**Budget : 0 €.** Aucun service payant. Toutes les clés d'API sont gratuites et optionnelles.

---

## 🚀 Installation pas à pas (Windows)

### Étape 1 : installer Python

1. Va sur <https://www.python.org/downloads/> et télécharge **Python 3.13** (ou plus récent).
2. Lance l'installateur et **coche la case « Add python.exe to PATH »** en bas de la première fenêtre. C'est important !
3. Clique sur **Install Now**.

> 💡 Tu as déjà Python 3.15 ? Ça peut marcher. Mais si l'installation des dépendances échoue (erreur de « compilation » ou de « wheel »), installe **aussi** Python 3.13 : `lancer_bot.bat` le choisira automatiquement.

### Étape 2 : créer le bot sur Discord

1. Va sur <https://discord.com/developers/applications> et connecte-toi.
2. Clique sur **New Application**, donne-lui un nom (ex. *Tekkit Watch*), accepte les conditions, **Create**.
3. Dans le menu de gauche, clique sur **Bot** :
   - Descends jusqu'à **Privileged Gateway Intents** et **active « MESSAGE CONTENT INTENT »**, puis **Save Changes**. Sans ça, le bot ne peut pas lire le webhook.
   - En haut, clique sur **Reset Token**, confirme, puis **Copy**. Garde ce token pour l'étape 4.
     ⚠️ Le token, c'est le mot de passe du bot : ne le montre à personne.
4. Dans le menu de gauche, clique sur **OAuth2**, puis note l'**APPLICATION ID** (le *Client ID*).
5. Invite le bot sur ton serveur en ouvrant ce lien (remplace `TON_CLIENT_ID`) :

   ```
   https://discord.com/oauth2/authorize?client_id=TON_CLIENT_ID&scope=bot+applications.commands&permissions=117760
   ```

   Choisis ton serveur puis **Autoriser**. Les permissions demandées sont seulement : voir les salons, envoyer des messages, intégrer des liens, joindre des fichiers et lire l'historique.

   > Tu préfères le faire à la main ? **OAuth2 → URL Generator** : coche `bot` et `applications.commands`, puis les permissions *View Channels*, *Send Messages*, *Embed Links*, *Attach Files* et *Read Message History*.

### Étape 3 : activer le mode développeur de Discord (pour copier les IDs)

Dans Discord : **⚙️ Paramètres utilisateur → Avancés → Mode développeur** (active-le).

Ensuite :
- **ton ID** : clic droit sur ton pseudo → **Copier l'identifiant de l'utilisateur** ;
- **l'ID du salon du webhook** : clic droit sur le salon où « Tekkit | Rewards Logger » poste → **Copier l'identifiant du salon**.

### Étape 4 : remplir le fichier `.env`

1. Dans le dossier du bot, fais une copie de `.env.example` et renomme la copie en **`.env`**.
   (Pas de panique si tu n'y arrives pas : `lancer_bot.bat` le crée tout seul au premier lancement et l'ouvre dans le Bloc-notes.)
2. Ouvre `.env` avec le Bloc-notes et remplis :

   ```
   DISCORD_TOKEN=le_token_copié_à_l_étape_2
   OWNER_ID=ton_ID
   WEBHOOK_CHANNEL_ID=l_ID_du_salon
   ```

3. **Optionnel** (gratuit, pour `/osint lien`) :
   - `VIRUSTOTAL_API_KEY` : crée un compte sur <https://www.virustotal.com>, puis clique sur ton avatar → **API key** ;
   - `URLSCAN_API_KEY` : crée un compte sur <https://urlscan.io>, puis **Settings & API → New API key**.

   Laisse vide si tu n'en veux pas : le bot marche très bien sans.

### Étape 5 : installer l'IA locale (Ollama), gratuite et optionnelle

1. Télécharge Ollama sur <https://ollama.com/download> et installe-le. Il démarre tout seul (icône de lama près de l'horloge).
2. Ouvre un terminal (touche **Windows**, tape `cmd`, **Entrée**) et télécharge le modèle conseillé :

   ```
   ollama pull qwen3.5:4b
   ```

   - **qwen3.5:4b** (modèle par défaut) : environ **3,4 Go** à télécharger. Il occupe environ **4 Go de RAM**, mais **seulement** quand tu poses une question, puis il se décharge tout seul au bout de 5 minutes. Il parle bien français et sait lire tes stats.
   - Ton PC rame quand l'IA répond ? Prends le modèle plus léger :

     ```
     ollama pull qwen3.5:2b
     ```

     puis choisis-le dans `/parametres` → 🤖 IA → *Modèle*. Tu peux aussi passer en mode **Léger** au même endroit.
   - Si `qwen3.5` n'existe pas dans ta version d'Ollama : `ollama pull qwen3:4b` marche aussi.

> L'IA ne tourne qu'**une question à la fois**, avec un nombre de cœurs limité, pour laisser le processeur à Roblox. Si Ollama est éteint, le bot continue de surveiller normalement.

### Étape 6 : lancer le bot

**Double-clique sur `lancer_bot.bat`.**

Au premier lancement, il crée un environnement Python et installe tout (quelques minutes). Ensuite le bot démarre et écrit **« ✅ Surveillance lancée »** dans le salon du webhook.

Laisse la fenêtre ouverte : la fermer arrête le bot. S'il plante, il redémarre tout seul au bout de 10 secondes.

### Étape 7 : tester

Dans ton serveur Discord, tape :

| Commande | Ce que tu dois voir |
|---|---|
| `/aide` | la liste des commandes, avec un menu |
| `/resume` | le résumé de tes comptes, avec des boutons |
| `/parametres` | le panneau de réglages (toi seul peux l'ouvrir) |
| `/ia-statut` | 🟢 si Ollama et le modèle sont prêts |

Par défaut, les comptes surveillés sont `abslt98` et `yayaoui00`. Pour en ajouter ou en retirer (10 maximum) : `/parametres` → 👤 Comptes.

### Étape 8 : démarrage automatique et hébergement 24 h/24

**Démarrer le bot avec Windows** : double-clique sur **`installer_demarrage_auto.bat`**. Le bot se lancera tout seul, en fenêtre réduite, à chaque démarrage du PC. Pour l'enlever, relance le même fichier et réponds **O**.

**Héberger 24 h/24 sur un serveur (VPS)**, pour que le bot tourne même PC éteint :

1. Il faut un serveur Linux avec Docker. Gratuit : l'offre *Always Free* d'Oracle Cloud (une carte bancaire est demandée pour la vérification, mais rien n'est facturé si tu restes dans l'offre gratuite).
2. Copie le dossier du bot sur le serveur, avec ton fichier `.env`.
3. Dans le dossier, lance :

   ```bash
   mkdir -p data && sudo chown 1000:1000 data
   docker compose up -d --build
   docker compose logs -f bot        # pour voir ce qui se passe (Ctrl+C pour quitter)
   ```

4. **IA sur le serveur** : elle demande au moins **4 Go de RAM libres** (ou **2 à 3 Go** avec `qwen3.5:2b`). Si ton serveur en a assez :

   ```bash
   docker compose --profile ia up -d --build
   docker compose exec ollama ollama pull qwen3.5:4b
   ```

   puis mets `OLLAMA_URL=http://ollama:11434` dans `.env` et relance avec `docker compose --profile ia up -d`.

> ⚠️ Ne fais **pas** tourner le bot à deux endroits en même temps (PC + serveur) : tu recevrais les alertes en double.

---

## 📚 Toutes les commandes

| Commande | Rôle |
|---|---|
| `/resume`, `/résumé` | Résumé du farm (boutons 🔄 Actualiser, 📋 Copiable, 📈 Stats, 🔮 Estimation, 📊 Graphique, ⚙️ Paramètres) |
| `/estimation heures:` | Gold, XP, gems et missions attendus (1 à 48 h), au rythme des 30 dernières minutes |
| `/stats periode:` | Totaux, moyennes par heure, temps de jeu, disponibilité, meilleure heure, record |
| `/graphique type: periode:` | Courbe par compte (gold, XP, gems, missions) en image |
| `/drops` | Historique des objets rares (filtres : compte, rareté, période) |
| `/comparer` | Comparaison des comptes côte à côte |
| `/export` | Export CSV des missions (s'ouvre dans Excel) |
| `/objectif ajouter / liste / supprimer` | Objectifs avec barre de progression et date estimée |
| `/pause` | Met en pause ou relance toutes les alertes |
| `/parametres` | Panneau de réglages complet (propriétaire) |
| `/ia question:` | Discuter avec l'IA locale (elle a accès à tes stats) |
| `/ia-generer type: sujet:` | Annonce, règles du serveur, description, idées... |
| `/ia-statut` | État d'Ollama, modèle chargé, RAM utilisée |
| `/osint domaine / ip / lien / entreprise / motdepasse / image` | Outils OSINT légaux (propriétaire) |
| `/aide` | Aide avec menu par catégorie |
| `/sync` | Resynchronise les commandes slash (propriétaire) |

Le bot envoie aussi un **rapport chaque jour** (21 h par défaut) et **chaque dimanche**, avec un graphique et les records battus.

---

## 🛡️ OSINT : ce qui est permis, ce qui ne l'est pas

Usage **personnel, défensif et légal** uniquement (RGPD, droit belge). Tu restes responsable de ce que tu en fais.

- ✅ Domaines, adresses IP publiques, liens (avant de cliquer), entreprises (données publiques de la BCE), **tes** mots de passe, **tes** images.
- 🚫 Aucune recherche de nom, adresse, téléphone, plaque, pseudo ou profil de réseau social d'une personne. Ces demandes sont **refusées avant tout appel internet**.
- Chaque recherche est notée dans un journal (`/parametres` → 🛡️ OSINT → *Voir le journal*). Aucun résultat concernant une personne n'est stocké.
- `/osint motdepasse` : le mot de passe est tapé dans une fenêtre privée, n'est **jamais** enregistré ni écrit dans les logs. Seuls les **5 premiers caractères de son empreinte SHA-1** sont envoyés à *Have I Been Pwned* (méthode « k-anonymity »).
- `/osint entreprise` : une entreprise en **personne physique** est une personne, donc son nom et son adresse sont masqués. La recherche par nom ne porte que sur les sociétés (personnes morales).
- `/osint lien` : le bot refuse tout lien qui mène vers ton réseau local (box, PC...).

---

## 🆘 Problèmes fréquents

**Les commandes `/` n'apparaissent pas**
- Attends une minute, puis redémarre Discord (Ctrl+R).
- Vérifie que le bot a été invité avec le scope `applications.commands` (lien de l'étape 2).
- Vérifie `WEBHOOK_CHANNEL_ID` : les commandes sont installées sur le serveur de **ce** salon.
- En dernier recours, tape `/sync`.

**Le bot est hors ligne**
- La fenêtre de `lancer_bot.bat` doit rester ouverte. Lis le message affiché dedans.
- « Token Discord refusé » : refais **Reset Token** (étape 2) et colle le nouveau dans `.env`.
- « Active MESSAGE CONTENT INTENT » : étape 2, point 3.
- « Discord injoignable » : problème d'internet. Le bot réessaie tout seul.

**« Salon WEBHOOK_CHANNEL_ID introuvable »**
- L'ID doit être celui du **salon** (pas du serveur ni du message).
- Le bot doit avoir le droit de **voir** ce salon (permissions du salon ou de la catégorie).

**Le bot ne voit pas les missions**
- Vérifie le *Message Content Intent* (étape 2).
- Le nom du compte dans `/parametres` → 👤 Comptes doit être **exactement** celui affiché par le webhook (`Bob` n'est pas `Bob2`).

**« Ollama ne répond pas »**
- Lance l'application Ollama (menu Démarrer → *Ollama*). L'icône du lama doit être près de l'horloge.
- Vérifie avec `/ia-statut`.
- Le modèle n'est pas téléchargé ? Fais `ollama pull qwen3.5:4b` dans un terminal.

**Le PC rame**
- `/parametres` → 🤖 IA → mode **Léger**, et/ou modèle `qwen3.5:2b`.
- Réduis « Décharger le modèle après ... min » (bouton ⚙️ Avancé) à 1 ou 2 minutes.
- Tu peux aussi désactiver complètement l'IA au même endroit : la surveillance n'en a pas besoin.

**L'installation des dépendances échoue**
- Installe **Python 3.13** (étape 1) et relance `lancer_bot.bat` : il le choisira automatiquement.
- Si besoin, supprime le dossier `.venv` pour repartir de zéro.

**Où sont mes données ?**
- Dans le dossier `data/` : `tekkit.db` (missions, réglages...) et `logs/bot.log`. Les données de plus de 90 jours sont supprimées automatiquement (réglable dans `/parametres` → ⏱️ Temps → 🗑️ Conservation).
- Pour sauvegarder tes réglages : `/parametres` → 💾 Exporter. Pour les restaurer : `/parametres importer:<fichier>`.

---

## 🧑‍💻 Pour les curieux : développement et tests

```bash
pip install -r requirements-dev.txt
python -m pytest          # plus de 100 tests, sans internet ni vrai Discord
ruff check bot tests      # vérification du style
```

Organisation :

```
bot/
├── main.py                 point d'entrée, chargement des modules, synchronisation des commandes
├── config.py               lecture de .env + réglages par défaut
├── reglages.py             réglages modifiables (cache + base)
├── database.py             schéma SQLite, migrations, requêtes
├── parser.py               lecture des embeds du webhook (fonctions pures)
├── calculs.py              rythmes, estimations, stats, anomalies, records (fonctions pures)
├── moteur_surveillance.py  décide quand alerter (sans Discord)
├── services.py             rassemble les données pour les résumés, les stats et l'IA
├── graphiques.py           graphiques matplotlib (PNG en mémoire)
├── ia_moteur.py            client Ollama, file d'attente, outils
├── osint_outils.py         outils OSINT + contrôles de périmètre
├── ui/                     embeds, couleurs, vues, panneau /parametres, limites Discord
└── cogs/                   surveillance, resumes, stats, objectifs, parametres, general, ia, osint
```

Chaque module est chargé séparément : si l'un d'eux plante, les autres (et surtout la surveillance) continuent de tourner.
