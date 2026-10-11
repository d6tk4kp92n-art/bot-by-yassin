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

Compte environ 30 minutes. Fais les étapes **dans l'ordre**, une à la fois.

> 🔒 Ne montre **jamais** ton fichier `.env` ni ton token (pas de capture d'écran, pas de message Discord). Celui qui a le token contrôle le bot.

### Étape 1 : vérifier Python

1. Appuie sur la touche **Windows**, tape `cmd`, puis **Entrée**. Une fenêtre noire s'ouvre.
2. Tape `py --version` puis **Entrée**.
   - Tu vois `Python 3.12`, `3.13`, `3.14` ou `3.15` (avec des chiffres après) ? C'est bon, passe à l'étape 2. Ton Python 3.15 convient très bien.
   - Tu vois « `'py' n'est pas reconnu…` » ? Ouvre le **Microsoft Store**, cherche **Python Install Manager**, installe-le, **ferme la fenêtre noire**, ouvres-en une nouvelle et tape `py install 3.15`.

### Étape 2 : télécharger le bot

1. Ouvre <https://github.com/d6tk4kp92n-art/bot-by-yassin>.
2. Clique sur le bouton vert **Code** puis, tout en bas du menu, sur **Download ZIP**. (GitHub est en anglais.)
3. Va dans ton dossier **Téléchargements**. Fais un **clic droit sur le ZIP → Propriétés**. En bas, si tu vois une case **Débloquer**, coche-la, puis **Appliquer** et **OK**. Ça évite que Windows bloque les fichiers `.bat`.
4. **Clic droit sur le ZIP → Extraire tout…** Clique sur **Parcourir…**, choisis un dossier simple comme `C:\TekkitWatch` (évite le Bureau et OneDrive), puis **Extraire**.
5. Ouvre les dossiers jusqu'à voir **`lancer_bot.bat`**, **`README.md`** et le dossier **`bot`** côte à côte. (Il y a souvent un dossier dans un dossier : c'est normal.)

### Étape 3 : créer le bot sur le site de Discord

Le site des développeurs Discord est en anglais : suis les noms des boutons tels quels.

1. Ouvre <https://discord.com/developers/applications> et connecte-toi avec ton compte Discord.
2. Clique sur **New Application** (en haut à droite), tape le nom `Tekkit Watch`, coche la case des conditions si elle apparaît, puis **Create**.
3. Tu arrives sur **General Information**. Sous **APPLICATION ID**, clique sur **Copy** et colle ce nombre dans le Bloc-notes : tu en auras besoin au point 7.
4. Dans le menu de gauche, clique sur **Bot**.
5. Clique sur **Reset Token**, confirme (Discord peut te redemander ton mot de passe ou ton code), puis **Copy**. Colle le token dans le Bloc-notes **tout de suite** : Discord ne le remontre jamais. (Si tu le perds : refais **Reset Token**.)
6. Toujours sur la page **Bot**, descends jusqu'à **Privileged Gateway Intents** et active **uniquement** **Message Content Intent**. Clique sur **Save Changes**. Laisse **Requires OAuth2 Code Grant** désactivé, et ne touche pas à l'onglet **Installation**.
7. Invite le bot sur ton serveur : copie ce lien dans ton navigateur en remplaçant `TON_APPLICATION_ID` par le nombre du point 3 (sans espace) :

   ```
   https://discord.com/oauth2/authorize?client_id=TON_APPLICATION_ID&scope=bot+applications.commands&permissions=117760&integration_type=0
   ```

   Choisis ton serveur, continue, puis valide. Il faut être le propriétaire du serveur ou avoir la permission « Gérer le serveur ». Le bot demande seulement 5 permissions : voir les salons, envoyer des messages, intégrer des liens, joindre des fichiers et lire l'historique.
8. Si le salon du webhook est **privé** : ouvre les paramètres du salon → **Permissions**, ajoute le rôle **Tekkit Watch** et autorise-le à voir le salon et à lire l'historique des messages.

### Étape 4 : copier deux identifiants dans Discord

1. Dans l'application Discord, clique sur la **roue dentée** en bas à gauche (Paramètres utilisateur).
2. Dans la barre de recherche en haut à gauche des paramètres, tape `développeur` et active l'interrupteur **Mode développeur**. (Selon ta version, il est dans la page « Avancés » ou « Développeur ».) Ferme les paramètres.
3. **Ton identifiant** : envoie un message `test` dans un salon, fais un **clic droit sur ton pseudo** au-dessus de ce message → **Copier l'identifiant de l'utilisateur**. Colle-le dans le Bloc-notes.
4. **L'identifiant du salon du webhook** : clic droit sur le **nom du salon** (dans la colonne de gauche) où « Tekkit | Rewards Logger » poste → **Copier l'identifiant du salon**. Colle-le dans le Bloc-notes.

Ce sont des nombres d'environ 18 chiffres. Ne confonds pas avec l'identifiant du **serveur** (clic droit sur l'icône ronde).

### Étape 5 : premier lancement (il crée le fichier `.env`)

1. Dans le dossier du bot, **double-clique sur `lancer_bot.bat`**.
   Une fenêtre bleue « Windows a protégé votre PC » ? Clique sur **Informations complémentaires**, puis **Exécuter quand même**.
2. Au premier lancement, le Bloc-notes s'ouvre sur le fichier `.env`. Colle chaque valeur **juste après le signe `=`**, sans espace ni guillemets :
   - `DISCORD_TOKEN=` → le token (étape 3, point 5) ;
   - `OWNER_ID=` → ton identifiant (étape 4, point 3) ;
   - `WEBHOOK_CHANNEL_ID=` → l'identifiant du salon (étape 4, point 4).

   Ça ressemble à ceci (avec tes vrais nombres) :

   ```
   DISCORD_TOKEN=MTI3NDU2Nzg5MDEy.GaBcDe.xxxxxxxxxxxxxxxxxxxxxxxx
   OWNER_ID=123456789012345678
   WEBHOOK_CHANNEL_ID=987654321098765432
   ```

3. Fais **Ctrl+S** pour enregistrer (obligatoire : le Bloc-notes de Windows 11 peut se fermer sans enregistrer), puis ferme le Bloc-notes.
4. Dans la fenêtre noire, appuie sur une touche : elle se ferme. C'est normal.

Les clés VirusTotal et urlscan.io (pour `/osint lien`) sont **gratuites et optionnelles** : laisse ces lignes vides pour l'instant.

### Étape 6 : lancer le bot pour de vrai

1. **Double-clique à nouveau sur `lancer_bot.bat`**.
2. La première fois, il installe tout : **1 à 5 minutes**, avec beaucoup de texte en anglais. **Ne ferme pas la fenêtre.**
3. Quand c'est prêt, la fenêtre affiche `✅ … commandes synchronisées sur le serveur …` et le bot écrit **« ✅ Surveillance lancée »** dans le salon du webhook.
4. **Laisse la fenêtre ouverte** : la fermer arrête le bot.

Message `[!] Corrige le problème indiqué juste au-dessus` ? Lis la ligne d'erreur, corrige le `.env` (le Bloc-notes s'ouvre tout seul), **Ctrl+S**, puis relance `lancer_bot.bat`.

### Étape 7 : tester dans Discord

Dans un salon de ton serveur, tape `/` (sur un clavier belge : **Maj + la touche `:`**). La liste des commandes apparaît.

| Commande | Ce que tu dois voir |
|---|---|
| `/aide` | la liste des commandes, avec un menu |
| `/resume` | le résumé de tes comptes, avec des boutons |
| `/parametres` | le panneau de réglages (toi seul peux l'ouvrir) |
| `/ia-statut` | l'état de l'IA (🔴 tant qu'Ollama n'est pas installé : c'est normal) |

Les commandes n'apparaissent pas ? Clique dans Discord et fais **Ctrl+R**.

Par défaut, les comptes surveillés sont `abslt98` et `yayaoui00`. Pour en ajouter ou en retirer (10 maximum) : `/parametres` → 👤 Comptes.

### Étape 8 (optionnelle) : l'IA gratuite avec Ollama

1. Télécharge Ollama sur <https://ollama.com/download> (fichier `OllamaSetup.exe`) et installe-le. Pas besoin de compte. Il tourne ensuite en arrière-plan : son icône est près de l'horloge (clique sur la petite flèche **^** si tu ne la vois pas).
2. Ouvre une **nouvelle** fenêtre noire (touche Windows, `cmd`, Entrée) et tape exactement :

   ```
   ollama pull qwen3.5:4b
   ```

   C'est environ **3,4 Go** à télécharger. Il faut un PC avec au moins **8 Go de RAM**. Le modèle n'utilise environ 4 Go de RAM que pendant les questions, puis se décharge tout seul après 5 minutes.
3. Dans Discord, tape `/ia-statut` : tu dois voir 🟢.

Sans carte graphique, une réponse prend environ **20 à 60 secondes** : c'est normal. Ton PC rame ? Prends le modèle léger (environ 1,4 Go) avec `ollama pull qwen3:1.7b`, puis choisis-le dans `/parametres` → 🤖 IA → *Modèle* (et mets le mode **Léger**).

> Dans le menu de l'icône Ollama (en anglais), ne clique pas sur **Quit Ollama** : ça arrête l'IA. **Restart to update** installe une mise à jour.

### Étape 9 (optionnelle) : démarrage automatique et hébergement 24 h/24

**Démarrer le bot avec Windows** : quand tout marche, double-clique sur **`installer_demarrage_auto.bat`**. Le bot se lancera tout seul, en fenêtre réduite dans la barre des tâches, à chaque démarrage du PC. Ensuite, ne relance plus `lancer_bot.bat` à la main s'il tourne déjà : tu aurais deux bots et des alertes en double. Tu as déplacé le dossier ? Relance `installer_demarrage_auto.bat` et réponds **N** pour le refaire.

**Héberger 24 h/24 sur un serveur (VPS)**, pour que le bot tourne même PC éteint :

1. Il faut un serveur Linux avec Docker. Gratuit : l'offre *Always Free* d'Oracle Cloud (une carte bancaire est demandée pour la vérification, mais rien n'est facturé si tu restes dans l'offre gratuite).
2. Copie le dossier du bot sur le serveur, avec ton fichier `.env`.
3. Dans le dossier, lance :

   ```bash
   mkdir -p data && sudo chown 1000:1000 data
   docker compose up -d --build
   docker compose logs -f bot        # pour voir ce qui se passe (Ctrl+C pour quitter)
   ```

4. **IA sur le serveur** : il faut au moins **4 Go de RAM libres** (environ 2 Go avec `qwen3:1.7b`). Si ton serveur en a assez :

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

**Windows bloque `lancer_bot.bat`**
- Fenêtre bleue « Windows a protégé votre PC » : clique sur **Informations complémentaires**, puis **Exécuter quand même**.
- Aucun bouton « Exécuter quand même » : supprime le dossier extrait, puis reprends l'étape 2 en cochant bien **Débloquer** dans les propriétés du ZIP **avant** l'extraction.
- « Tu as lancé ce fichier depuis l'intérieur du ZIP » : fais d'abord **Extraire tout…** (étape 2, point 4).

**« Il manque dans le fichier .env : … »**
- Le `.env` n'a pas été enregistré : rouvre-le, complète-le, fais **Ctrl+S**, puis relance `lancer_bot.bat`.
- Pas d'espace autour du `=`, pas de guillemets, pas de `<@…>` : uniquement les chiffres pour les identifiants.

**Les commandes `/` n'apparaissent pas**
- La fenêtre noire du bot doit être ouverte et afficher `✅ … commandes synchronisées sur le serveur …`.
- Clique dans Discord et fais **Ctrl+R**. Sinon, quitte complètement Discord (clic droit sur son icône près de l'horloge → Quitter) et rouvre-le.
- Vérifie `WEBHOOK_CHANNEL_ID` : les commandes sont installées sur le serveur de **ce** salon.
- En dernier recours, tape `/sync`.

**Le bot est hors ligne ou s'arrête**
- La fenêtre de `lancer_bot.bat` doit rester ouverte. Lis le message affiché dedans.
- « Token Discord refusé » : refais **Reset Token** (étape 3, point 5) et colle le nouveau dans `.env`. Attention à ne pas copier le « Client Secret » ou la « Public Key » : ce ne sont pas des tokens.
- « Active MESSAGE CONTENT INTENT » : étape 3, point 6 (n'oublie pas **Save Changes**).
- « Discord injoignable » : problème d'internet. Le bot réessaie tout seul.
- « Le bot plante en boucle » : lis l'erreur au-dessus. Si elle parle de `python.exe` introuvable, supprime le dossier `.venv` et relance `lancer_bot.bat`.

**« Salon WEBHOOK_CHANNEL_ID introuvable »**
- L'identifiant doit être celui du **salon** (pas du serveur ni d'un message).
- Le bot doit avoir le droit de **voir** ce salon (étape 3, point 8).

**Le bot ne voit pas les missions**
- Vérifie le *Message Content Intent* (étape 3, point 6).
- Le nom du compte dans `/parametres` → 👤 Comptes doit être **exactement** celui affiché par le webhook (`Bob` n'est pas `Bob2`).

**« Ollama ne répond pas »**
- Lance l'application Ollama (menu Démarrer → *Ollama*). Son icône doit être près de l'horloge (flèche **^**).
- « `'ollama' n'est pas reconnu…` » : ferme la fenêtre noire et ouvres-en une **nouvelle** après l'installation d'Ollama.
- « `file does not exist` » : faute de frappe dans le nom du modèle. Copie-colle `ollama pull qwen3.5:4b`.
- Vérifie avec `/ia-statut`.

**Le PC rame**
- `/parametres` → 🤖 IA → mode **Léger**, et modèle `qwen3:1.7b` (à télécharger avec `ollama pull qwen3:1.7b`).
- Réduis « Décharger le modèle après ... min » (bouton ⚙️ Avancé) à 1 ou 2 minutes.
- Tu peux aussi désactiver complètement l'IA au même endroit : la surveillance n'en a pas besoin.

**L'installation des dépendances échoue**
- Vérifie ta connexion internet et relance `lancer_bot.bat` : il repart de zéro tout seul.
- Ton Python doit être en **64 bits** (le script te prévient sinon).

**Mettre le bot à jour**
- Télécharge le nouveau ZIP, débloque-le, puis extrais-le **dans le même dossier** en acceptant de **remplacer les fichiers**. Ton `.env` et ton historique (`data`) sont conservés.

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
