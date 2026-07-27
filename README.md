# Surveillance des annonces in'li

Ce projet vérifie automatiquement les nouvelles annonces de location sur
inli.fr toutes les 15 minutes et t'envoie une notification Telegram
instantanée dès qu'une nouvelle annonce correspond à tes critères.

Coût : **0 €**. Tout tourne sur GitHub Actions (gratuit pour un dépôt public,
2000 min/mois gratuites même en privé).

## Installation (10-15 minutes)

### 1. Créer le bot Telegram
1. Dans Telegram, cherche **@BotFather** et démarre une conversation.
2. Envoie `/newbot`, choisis un nom et un identifiant (doit finir par `bot`).
3. BotFather te donne un **token** (ex: `123456:ABC-DEF...`). Garde-le.
4. Cherche ton nouveau bot dans Telegram et envoie-lui n'importe quel message
   (ex: "salut") pour l'activer.
5. Va sur cette URL dans ton navigateur (remplace `<TOKEN>`) :
   `https://api.telegram.org/bot<TOKEN>/getUpdates`
   Tu verras un champ `"chat":{"id":123456789,...}` — c'est ton **chat_id**.

### 2. Créer le dépôt GitHub
1. Crée un nouveau dépôt sur GitHub (public ou privé, peu importe).
2. Mets-y tous les fichiers de ce projet (via l'interface web "Add file" >
   "Upload files", ou via `git`).

### 3. Configurer les secrets et variables
Dans le dépôt GitHub : **Settings > Secrets and variables > Actions**

Onglet **Secrets** (valeurs sensibles, jamais visibles) :
- `TELEGRAM_BOT_TOKEN` → le token de BotFather
- `TELEGRAM_CHAT_ID` → ton chat_id

Onglet **Variables** (tes critères de recherche, modifiables librement) :
- `MAX_RENT` → ex: `1300` (loyer max en €, laisser vide = pas de limite)
- `MIN_SURFACE` → ex: `35` (surface min en m²)
- `MIN_ROOMS` → ex: `2` (nombre de pièces min, Studio = 1)
- `CITIES` → ex: `Villejuif,Vitry sur seine,Ivry sur seine` (villes acceptées,
  séparées par des virgules — laisser vide = toutes les villes)

### 4. Activer les Actions
1. Va dans l'onglet **Actions** du dépôt.
2. Si demandé, clique pour activer les workflows.
3. Le premier lancement se fait automatiquement (ou lance-le manuellement
   via "Surveillance annonces in'li" > "Run workflow").
4. **Important** : le premier lancement enregistre juste les annonces
   existantes comme référence, sans notifier (sinon tu reçois d'un coup
   toutes les annonces déjà en ligne). Les notifications commencent à partir
   du 2e passage.

## Ajuster la fréquence
Le cron est réglé sur `*/15 * * * *` (toutes les 15 min) dans
`.github/workflows/watch.yml`. GitHub n'autorise pas en dessous de 5 minutes
et peut ajouter un léger retard en période de forte charge — c'est normal,
gratuit et sans garantie de seconde près.

## Maintenance
GitHub désactive automatiquement les workflows programmés après 60 jours
sans activité sur le dépôt (pas de souci ici puisque le workflow committe
lui-même à chaque run, donc il reste actif). Si tu vois "This scheduled
workflow is disabled" dans l'onglet Actions, réactive-le manuellement une
fois.

## Limites à connaître
- Basé sur le contenu affiché publiquement sur inli.fr/locations/offres —
  si in'li change la structure de leur site, le script peut nécessiter un
  ajustement.
- Ne remplace pas une candidature rapide une fois l'alerte reçue : la
  réactivité reste le facteur clé une fois notifié.
