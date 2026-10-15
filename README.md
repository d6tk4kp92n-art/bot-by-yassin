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

### Avant de commencer : ce qu'il te faut

Un **webhook**, c'est une adresse secrète qui permet à Tekkit d'écrire tout seul dans un salon Discord. Le bot lit les messages de ce salon. Vérifie ces deux points :

1. **Un serveur Discord où tu peux inviter un bot** : il est à toi, ou tu y as la permission « Gérer le serveur ». Tu n'en as pas ? Dans Discord, clique sur le **+** en bas de la liste des serveurs (colonne de gauche), puis crée ton serveur.
2. **Un salon de ce serveur où « Tekkit | Rewards Logger » poste déjà** un message après chaque mission. Pas encore de webhook ? Dans les paramètres du salon (roue dentée à côté de son nom) → **Intégrations** → **Webhooks**, crée un webhook, copie son URL et colle-la dans Tekkit, à l'endroit prévu pour le webhook. Ne montre cette adresse à personne.

Ouvre ensuite le **Bloc-notes** (touche **Windows**, tape `bloc-notes`, **Entrée**) et tapes-y ces 4 lignes. Tu y colleras chaque information au fur et à mesure :

```
APPLICATION ID :
TOKEN :
MON IDENTIFIANT :
SALON DU WEBHOOK :
```

Garde ce Bloc-notes ouvert jusqu'à la fin de l'étape 7. Ne l'enregistre pas et ne le montre à personne : il contiendra ton token.

### Étape 1 : vérifier Python

1. Appuie sur la touche **Windows**, tape `cmd`, puis **Entrée**. Une fenêtre noire s'ouvre.
2. Tape `py --version` puis **Entrée**.
   - Tu vois `Python 3.12`, `3.13`, `3.14` ou `3.15` (avec des chiffres après) ? C'est bon, ferme la fenêtre et passe à l'étape 2. Ton Python 3.15 convient très bien.
   - Tu vois « `'py' n'est pas reconnu…` » ou une version plus ancienne ? Ouvre le **Microsoft Store**, cherche **Python Install Manager** et installe-le. Ferme la fenêtre noire, ouvres-en une **nouvelle** et tape `pymanager install 3.15`.

### Étape 2 : télécharger le bot

1. Ouvre <https://github.com/d6tk4kp92n-art/bot-by-yassin>.
2. Clique sur le bouton vert **Code** puis, tout en bas du menu, sur **Download ZIP**. (GitHub est en anglais.)
3. Va dans ton dossier **Téléchargements**. Le ZIP s'appelle `bot-by-yassin-…zip`. Fais un **clic droit dessus → Propriétés**. En bas, si tu vois une case **Débloquer**, coche-la, puis **Appliquer** et **OK**. Ça évite que Windows bloque les fichiers `.bat`.
4. **Clic droit sur le ZIP → Extraire tout…** Dans la case du dossier de destination, efface tout et tape `C:\TekkitWatch`. Sur un clavier belge, le `\` se tape avec **AltGr + la touche `<`** (à gauche du W). Le dossier sera créé tout seul. Clique sur **Extraire**. Évite le Bureau et OneDrive.
5. Ouvre les dossiers jusqu'à voir **`lancer_bot`** (icône à engrenages), **`README`** et le dossier **`bot`** côte à côte. Il y a souvent un dossier dans un dossier : c'est normal. Windows cache souvent la fin des noms : `lancer_bot` et `lancer_bot.bat` sont le même fichier.

### Étape 3 : créer le bot sur le site de Discord

Le site des développeurs Discord est en anglais : suis les noms des boutons tels quels.

1. Ouvre <https://discord.com/developers/applications> et connecte-toi avec ton compte Discord.
2. Clique sur **New Application** (en haut à droite), tape le nom `Tekkit Watch`, coche la case des conditions si elle apparaît, puis **Create**.
3. Tu arrives sur **General Information**. Sous **APPLICATION ID**, clique sur **Copy**, puis colle le nombre au bout de la ligne `APPLICATION ID :` de ton Bloc-notes.
4. Dans le menu de gauche, clique sur **Bot**.
5. Clique sur **Reset Token**, confirme (Discord peut te redemander ton mot de passe ou ton code), puis **Copy**. Colle le token au bout de la ligne `TOKEN :` **tout de suite** : Discord ne le remontre jamais. (Si tu le perds : refais **Reset Token**.)
6. Toujours sur la page **Bot**, descends jusqu'à **Privileged Gateway Intents** et active **uniquement** **Message Content Intent**. Clique sur **Save Changes**. Laisse **Requires OAuth2 Code Grant** désactivé, et ne touche pas à l'onglet **Installation**.
7. Invite le bot sur **le serveur où se trouve le salon du webhook** :
   - copie le lien ci-dessous et colle-le sur une nouvelle ligne du Bloc-notes ;
   - remplace `TON_APPLICATION_ID` par le nombre de la ligne `APPLICATION ID :` (sans espace) ;
   - copie toute la ligne modifiée, colle-la dans la **barre d'adresse** de ton navigateur (tout en haut), puis **Entrée**.

   ```
   https://discord.com/oauth2/authorize?client_id=TON_APPLICATION_ID&scope=bot+applications.commands&permissions=117760&integration_type=0
   ```

   Choisis le serveur du webhook (pas un autre), continue, puis autorise. Ce serveur n'apparaît pas dans la liste ? Tu n'as pas la permission « Gérer le serveur » dessus : voir « Avant de commencer ». Le bot demande seulement 5 permissions : voir les salons, envoyer des messages, intégrer des liens, joindre des fichiers et voir les anciens messages.
8. Le salon du webhook a un **cadenas** à côté de son nom, ou personne ne peut y écrire ? Ouvre ses paramètres (roue dentée) → **Permissions**, ajoute le rôle **Tekkit Watch** et coche en vert : voir le salon, voir les anciens messages, envoyer des messages, intégrer des liens et joindre des fichiers. Enregistre. Sans ça, le bot ne peut ni lire Tekkit ni t'envoyer d'alertes.

### Étape 4 : copier deux identifiants dans Discord

1. Dans l'application Discord, clique sur la **roue dentée** en bas à gauche (Paramètres utilisateur).
2. Dans la barre de recherche en haut à gauche des paramètres, tape `développeur` et active l'interrupteur **Mode développeur**. (Selon ta version, il est dans la page « Avancés » ou « Développeur ».) Ferme les paramètres.
3. **Ton identifiant** : envoie un message `test` dans un salon, fais un **clic droit sur ton pseudo** au-dessus de ce message → **Copier l'identifiant de l'utilisateur**. Colle-le au bout de la ligne `MON IDENTIFIANT :`.
4. **L'identifiant du salon du webhook** : clic droit sur le **nom du salon** (dans la colonne de gauche) où « Tekkit | Rewards Logger » poste → **Copier l'identifiant du salon**. Colle-le au bout de la ligne `SALON DU WEBHOOK :`.

Ce sont des nombres d'environ 18 chiffres. Ne confonds pas avec l'identifiant du **serveur** (clic droit sur l'icône ronde).

### Étape 5 : premier lancement (il crée le fichier `.env`)

1. Dans le dossier du bot, **double-clique sur `lancer_bot`**.
   Une fenêtre bleue « Windows a protégé votre PC » ? Clique sur **Informations complémentaires**, puis **Exécuter quand même**.
2. Au premier lancement, le fichier `.env` s'ouvre dans un **nouvel onglet** du Bloc-notes, à côté de l'onglet de tes notes (en haut de la fenêtre). Passe d'un onglet à l'autre pour copier-coller. Dans l'onglet `.env`, colle chaque valeur **juste après le signe `=`**, sans espace ni guillemets :
   - `DISCORD_TOKEN=` → la ligne `TOKEN :` de tes notes ;
   - `OWNER_ID=` → la ligne `MON IDENTIFIANT :` ;
   - `WEBHOOK_CHANNEL_ID=` → la ligne `SALON DU WEBHOOK :`.

   Ça ressemble à ceci (avec tes vrais nombres) :

   ```
   DISCORD_TOKEN=MTI3NDU2Nzg5MDEy.GaBcDe.xxxxxxxxxxxxxxxxxxxxxxxx
   OWNER_ID=123456789012345678
   WEBHOOK_CHANNEL_ID=987654321098765432
   ```

   Ne touche pas aux autres lignes : `OLLAMA_URL` est déjà bonne, et les clés VirusTotal et urlscan.io (pour `/osint lien`) sont gratuites et optionnelles, laisse-les vides.
3. Fais **Ctrl+S** pour enregistrer (obligatoire : le Bloc-notes de Windows 11 peut se fermer sans enregistrer). Ferme ensuite **seulement l'onglet `.env`** (petite croix sur l'onglet) et garde tes notes ouvertes.
4. Dans la fenêtre noire, appuie sur une touche : elle se ferme. C'est normal.

### Étape 6 : lancer le bot pour de vrai

1. **Double-clique à nouveau sur `lancer_bot`**.
2. La première fois, il installe tout : **1 à 5 minutes**, avec beaucoup de texte en anglais. **Ne ferme pas la fenêtre.**
3. Quand c'est prêt, la fenêtre affiche `✅ … commandes synchronisées sur le serveur …` et le bot écrit **« ✅ Surveillance lancée · comptes : `abslt98`, `yayaoui00` … »** dans le salon du webhook. Ces deux comptes sont réglés par défaut. Si ce ne sont pas les tiens, ou s'ils ne farment pas en ce moment, tu recevras « … a disparu » avec une mention au bout de 3 minutes : ce n'est pas une panne, règle tes comptes à l'étape 7.
4. **Laisse la fenêtre ouverte** : la fermer arrête le bot.

Message `[!] …` dans la fenêtre ? Lis la ligne d'erreur juste au-dessus :
- elle parle de **MESSAGE CONTENT INTENT** : retourne à l'étape 3, point 6, sans oublier **Save Changes**. Ton `.env` est bon ;
- elle parle du **token** : refais l'étape 3, point 5, puis colle le nouveau token dans le `.env` ;
- sinon, corrige le `.env` (le Bloc-notes s'ouvre tout seul).

Fais **Ctrl+S**, appuie sur une touche dans la fenêtre noire, puis relance `lancer_bot`.

Quand tout marche, efface tes notes du Bloc-notes (**Ctrl+A** puis **Suppr**) et ferme-le sans enregistrer.

### Étape 7 : tester dans Discord

Dans un salon de ton serveur, tape `/` (sur un clavier belge : **Maj + la touche `:`**). La liste des commandes apparaît.

1. Règle **tes** comptes Roblox : tape `/parametres`, choisis **Comptes**, clique sur **Ajouter un compte** et tape ton username Roblox exactement comme le webhook l'écrit. Retire avec le menu **Retirer un compte…** ceux qui ne sont pas à toi (10 comptes maximum).
2. Essaie ensuite :

| Commande | Ce que tu dois voir |
|---|---|
| `/aide` | la liste des commandes, avec un menu |
| `/resume` | le résumé de tes comptes, avec des boutons |
| `/parametres` | le panneau de réglages (toi seul peux l'ouvrir) |
| `/ia-statut` | l'état de l'IA (🔴 tant qu'Ollama n'est pas installé : c'est normal) |

Les commandes n'apparaissent pas ? Clique dans Discord et fais **Ctrl+R**.

### Étape 8 (optionnelle) : l'IA gratuite avec Ollama

1. Télécharge Ollama sur <https://ollama.com/download> (fichier `OllamaSetup.exe`) et installe-le. Pas besoin de compte. Il tourne ensuite en arrière-plan : son icône est près de l'horloge (clique sur la petite flèche **^** si tu ne la vois pas).
2. Ouvre une **nouvelle** fenêtre noire (touche Windows, `cmd`, Entrée). Copie la ligne ci-dessous, colle-la dans la fenêtre avec **Ctrl+V**, puis **Entrée** (mieux vaut copier-coller que taper : une faute de frappe donne l'erreur `file does not exist`) :

   ```
   ollama pull qwen3.5:4b
   ```

   C'est environ **3,4 Go** à télécharger. Il faut un PC avec au moins **8 Go de RAM**. Le modèle n'utilise environ 4 Go de RAM que pendant les questions, puis se décharge tout seul après 5 minutes.
3. Dans Discord, tape `/ia-statut` : tu dois voir 🟢.

Sans carte graphique, une réponse prend environ **20 à 60 secondes** : c'est normal. Ton PC rame ? Prends le modèle léger (environ 1,4 Go) avec `ollama pull qwen3:1.7b`, puis choisis-le dans `/parametres` → 🤖 IA → *Modèle* (et mets le mode **Léger**). Il parle un peu moins bien français.

> Dans le menu de l'icône Ollama (en anglais), ne clique pas sur **Quit Ollama** : ça arrête l'IA. **Restart to update** installe une mise à jour.

### Étape 9 (optionnelle) : démarrage automatique et hébergement 24 h/24

**Démarrer le bot avec Windows** : quand tout marche, double-clique sur **`installer_demarrage_auto`**. Le bot se lancera tout seul, en fenêtre réduite dans la barre des tâches, dès que tu ouvres ta session Windows (après ton code PIN). Pour savoir s'il tourne : regarde s'il y a une fenêtre « Tekkit Watch » dans la barre des tâches, ou si le bot a un point vert dans la liste des membres Discord. Si tu relances `lancer_bot` alors qu'il tourne déjà, il te le dira et ne lancera pas un deuxième bot. Tu as déplacé le dossier ? Relance `installer_demarrage_auto` et réponds **F** pour refaire le raccourci (ou **R** pour le retirer).

**Héberger 24 h/24 sur un serveur (VPS)** (partie **avancée**) : il faut savoir se connecter à un serveur Linux (SSH), y installer Docker et y copier des fichiers (par exemple avec WinSCP). Ce guide ne l'explique pas : si ces mots ne te disent rien, garde le bot sur ton PC avec le démarrage automatique.

1. Gratuit : l'offre *Always Free* d'Oracle Cloud (une carte bancaire est demandée pour la vérification, mais rien n'est facturé si tu restes dans l'offre gratuite).
2. **Arrête d'abord le bot sur ton PC** : ferme sa fenêtre et, si tu as installé le démarrage automatique, relance `installer_demarrage_auto` et réponds **R**.
3. Copie le dossier du bot sur le serveur, avec ton fichier `.env`. Dans le dossier, lance :

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

**Ouvrir le fichier `.env` à la main**
- Un double-clic sur `.env` ne marche pas : fais **clic droit dessus → Ouvrir avec → Bloc-notes**. N'ouvre pas `.env.example`, ce n'est qu'un modèle.
- Avant de modifier `.env`, ferme la fenêtre du bot ; après, fais **Ctrl+S** et relance `lancer_bot`.

**Windows bloque `lancer_bot`**
- Fenêtre bleue « Windows a protégé votre PC » : clique sur **Informations complémentaires**, puis **Exécuter quand même**.
- Aucun bouton « Exécuter quand même » : supprime le dossier extrait, puis reprends l'étape 2 en cochant bien **Débloquer** dans les propriétés du ZIP **avant** l'extraction.
- « Tu as lancé ce fichier depuis l'intérieur du ZIP » : fais d'abord **Extraire tout…** (étape 2, point 4).

**« Il manque dans le fichier .env : … »**
- Le Bloc-notes s'ouvre tout seul sur `.env` : complète les lignes indiquées, fais **Ctrl+S**, ferme l'onglet, appuie sur une touche dans la fenêtre noire, puis relance `lancer_bot`.
- Pas d'espace autour du `=`, pas de guillemets, pas de `<@…>` : uniquement les chiffres pour les identifiants.

**« Le bot tourne déjà »**
- Il y a déjà une fenêtre « Tekkit Watch » ouverte, souvent réduite dans la barre des tâches (démarrage automatique). Utilise celle-là : un seul bot à la fois.

**Les commandes `/` n'apparaissent pas**
- La fenêtre noire du bot doit être ouverte et afficher `✅ … commandes synchronisées sur le serveur …`.
- Clique dans Discord et fais **Ctrl+R**. Sinon, quitte complètement Discord (clic droit sur son icône près de l'horloge → Quitter) et rouvre-le.
- Vérifie `WEBHOOK_CHANNEL_ID` : les commandes sont installées sur le serveur de **ce** salon.
- En dernier recours : ferme la fenêtre noire du bot, puis relance `lancer_bot`. Il réinstalle les commandes à chaque démarrage. (`/sync` ne sert que si tu vois déjà d'autres commandes du bot.)

**« Cette commande est réservée au propriétaire du bot » alors que c'est ton bot**
- `OWNER_ID` ne contient pas **ton** identifiant (erreur fréquente : l'APPLICATION ID ou l'identifiant du salon). Refais l'étape 4, point 3, puis corrige `OWNER_ID` dans `.env` (voir « Ouvrir le fichier `.env` à la main »).

**Le bot est hors ligne ou s'arrête**
- La fenêtre de `lancer_bot` doit rester ouverte. Lis le message affiché dedans.
- « Token Discord refusé » : refais **Reset Token** (étape 3, point 5) et colle le nouveau dans `.env`. Attention à ne pas copier le « Client Secret » ou la « Public Key » : ce ne sont pas des tokens.
- « Active MESSAGE CONTENT INTENT » : étape 3, point 6 (n'oublie pas **Save Changes**). Le `.env` n'y est pour rien.
- « Discord injoignable » : problème d'internet ou panne passagère de Discord. Le bot réessaie tout seul.
- « Le bot plante en boucle » : lis l'erreur au-dessus. Si elle parle de `python.exe` introuvable, supprime le dossier `.venv` et relance `lancer_bot`.

**« Salon WEBHOOK_CHANNEL_ID introuvable »** (le bot reste allumé, mais sans commandes ni alertes)
- Ferme la fenêtre noire du bot.
- `WEBHOOK_CHANNEL_ID` doit être l'identifiant du **salon** (étape 4, point 4), pas celui du serveur ni d'un message.
- Le bot doit être invité sur **le serveur de ce salon** (étape 3, point 7) et avoir le droit de voir le salon (étape 3, point 8).
- Corrige `.env`, fais **Ctrl+S**, puis relance `lancer_bot`.

**Aucune alerte n'arrive, la fenêtre dit « Impossible d'écrire dans le salon des alertes »**
- Le bot n'a pas le droit d'écrire dans ce salon : étape 3, point 8 (envoyer des messages, intégrer des liens, joindre des fichiers).

**Le bot ne voit pas les missions**
- `WEBHOOK_CHANNEL_ID` doit être l'identifiant du salon **où « Tekkit | Rewards Logger » poste vraiment** (étape 4, point 4).
- Le nom du compte dans `/parametres` → 👤 Comptes doit être **exactement** le username Roblox affiché par le webhook (`Bob` n'est pas `Bob2`).
- Vérifie que Roblox et Tekkit tournent : un nouveau message du webhook doit apparaître dans le salon après chaque mission.

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
- Vérifie ta connexion internet et relance `lancer_bot` : il repart de zéro tout seul.
- Ton Python doit être en **64 bits** (le script te prévient sinon).

**« Windows a refusé de créer le raccourci » (démarrage automatique)**
- Fais-le à la main : appuie sur **Windows + R**, tape `shell:startup`, puis **Entrée**. Un dossier s'ouvre.
- Dans le dossier du bot, fais un **clic droit sur `lancer_bot` → Afficher d'autres options → Créer un raccourci**, puis fais glisser ce raccourci dans le dossier ouvert.

**Mettre le bot à jour**
- **Ferme d'abord le bot** (sa fenêtre peut être réduite dans la barre des tâches).
- Télécharge le nouveau ZIP et débloque-le (étape 2, point 3). Fais **Extraire tout…** vers **le même dossier qu'à l'étape 2, point 4** (`C:\TekkitWatch`, **pas** le dossier qui contient `lancer_bot`). Quand Windows le demande, choisis **Remplacer les fichiers dans la destination**.
- Relance `lancer_bot` (une seule fois). Ton `.env` et ton historique (`data`) sont conservés.

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
