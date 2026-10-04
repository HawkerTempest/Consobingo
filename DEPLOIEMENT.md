# Installer ConsoBingo sur la base de SWOTmania

## 1. Installer les tables du jeu

Ouvrir **le projet Supabase déjà utilisé par SWOTmania** et son éditeur SQL. Exécuter intégralement `sql/01_installation.sql`.

Le script crée des vues vers `swot_students` et `swot_teachers` ainsi que les tables propres à ConsoBingo. Il ne modifie pas les inscriptions existantes ni les résultats des autres jeux. Il peut être exécuté à nouveau sur le même annuaire sans supprimer les parties.

Les sources livrées de SWOTmania et STP-by-Step possèdent deux annuaires distincts. Le choix par défaut est **SWOTmania**, conformément à la demande. Si l’annuaire réellement tenu à jour est uniquement celui de STP-by-Step, remplacer `source_prefix text := 'swot'` par `source_prefix text := 'stp'` dans le premier bloc, **avant la première installation**. Ne pas changer ensuite de source sur une base ayant déjà des parties : les matricules sont les identifiants de référence.

Le message `CONSO_ROSTER_MISSING` signifie que le SQL n’est pas exécuté dans le projet contenant cet annuaire, ou que le préfixe choisi ne correspond pas aux tables existantes.

Les enseignants actifs de l’annuaire existant ont accès au suivi. Les inscriptions se gèrent dans l’application qui possède l’annuaire. ConsoBingo n’ajoute pas de second écran d’import ni de mot de passe partagé.

## 2. Préparer Streamlit Cloud

Placer **le contenu de ce dossier** dans un dépôt GitHub, en conservant les sous-dossiers et notamment `consobingo/frontend/assets/` et `consobingo/fonts/`.

Créer une application Streamlit Cloud avec :

- fichier principal : `app.py` ;
- Python : `3.12` ;
- dépendances : `requirements.txt`, à la racine.

Dans les secrets de l’application, copier `secrets.toml.example`, puis remplacer les exemples par les paramètres existants de SWOTmania :

- `SUPABASE_URL` : URL du même projet ;
- `SUPABASE_PUBLISHABLE_KEY` : clé publique, ou ancienne `SUPABASE_ANON_KEY` ;
- `APP_URL` : URL HTTPS de **ConsoBingo** ;
- paramètres Brevo : mêmes identifiants SMTP ou clé API et même expéditeur validé ;
- `BREVO_SENDER_NAME = "ConsoBingo"` ;
- `CONSOBINGO_DEMO = false`.

Ne pas déposer `.streamlit/secrets.toml` dans GitHub. Le fichier d’exemple seul peut être partagé. Aucune clé `service_role` ou `sb_secret` n’est nécessaire.

Pour une installation locale connectée, copier le modèle dans `.streamlit/secrets.toml` et lancer `streamlit run app.py`. Les variables d’environnement portant les mêmes noms sont aussi acceptées ; les secrets Streamlit ont priorité.

## 3. Réutiliser la connexion habituelle

Supabase Auth envoie le code de connexion. La configuration SMTP Auth existante de SWOTmania est réutilisée, indépendamment des secrets Brevo de cette application, qui servent aux invitations et bilans.

Si SWOTmania fonctionne déjà par code, conserver sa configuration Auth. Le modèle de courriel Auth doit afficher `{{ .Token }}` ; ConsoBingo demande de saisir le code reçu. Les limites d’envoi et la durée de validité restent celles du projet Supabase.

L’adresse doit être active dans l’annuaire correspondant au rôle choisi. L’application vérifie cette condition avant l’envoi et après la validation du code. Le passage d’un jeu à l’autre peut demander une nouvelle connexion, même si le compte et l’annuaire sont communs.

## 4. Configurer les courriels

Deux transports sont prévus :

- **SMTP Brevo**, avec `BREVO_SMTP_USERNAME` et `BREVO_SMTP_PASSWORD`, comme les jeux précédents ;
- **API Brevo**, avec `BREVO_API_KEY`, prioritaire lorsqu’elle est renseignée.

Sans Brevo, le jeu, les sauvegardes et les PDF fonctionnent ; les boutons d’envoi sont masqués ou indiquent que l’envoi n’est pas configuré.

Par défaut, `SEND_COMPLETION_EMAILS = false`. L’étudiant prévisualise son bilan et demande lui-même son envoi. L’enseignant sélectionne les destinataires, prépare un aperçu, puis lance explicitement les invitations, rappels ou bilans. Il faut garder la page des courriels ouverte pendant le traitement ; ce n’est pas une tâche d’arrière-plan.

Option : `SEND_COMPLETION_EMAILS = true` active un envoi au premier affichage du bilan enregistré de chaque partie. `EMAIL_ATTACH_PDF = true` ajoute le carnet PDF.

Une réservation en base précède l’envoi. Un bilan automatique ou demandé par l’étudiant n’est expédié qu’une fois par partie. Un résultat `unknown` indique que l’accusé du fournisseur manque ; aucun renvoi aveugle n’est lancé. Le statut `sent` signifie « accepté par le service d’envoi », pas « distribué ». Vérifier le journal Brevo en cas de doute. L’enseignant peut préparer un nouvel envoi distinct après vérification.

## 5. Vérifier l’installation

Avec un compte de test déjà présent dans l’annuaire :

1. Recevoir le code, se connecter et commencer une partie.
2. Annoter une bulle, vérifier la sauvegarde, se déconnecter puis reprendre.
3. Tester un corrigé : le carnet doit indiquer « Corrigé consulté ».
4. Enregistrer le bilan, télécharger le PDF et vérifier que les activités restent accessibles.
5. Avec l’accès enseignant, vérifier la présence de cet étudiant et essayer le jeu en démo.
6. Si nécessaire, demander un seul bilan à l’adresse de test et vérifier sa réception ainsi que le journal.

Les vérifications livrées n’envoient pas de courriels et n’utilisent pas la base réelle.

## Reprise et incidents

Une seule connexion écrit à la fois dans une partie. Reprendre sur un autre appareil transfère ce droit à cette connexion. L’ancien onglet affiche un conflit au prochain enregistrement, propose une copie de secours, puis une reprise explicite de la version sauvegardée.

En cas d’indisponibilité Supabase, les réponses restent dans la session et l’interface demande de réessayer. Une copie JSON peut être téléchargée pour ne pas perdre le travail. Elle ne se réimporte pas automatiquement : le jeu reprend la version effectivement enregistrée. Ne pas fermer l’onglet tant que la sauvegarde n’est pas confirmée si l’on veut conserver les dernières modifications en ligne.

« Nouvelle partie » archive la précédente et change l’ordre de présentation. Les archives restent en base et sont accessibles par les fonctions autorisées ; le portail reprend la partie courante.

## Contrôle des accès

Les tables et vues `conso_*` ne sont pas accessibles directement aux rôles publics. Les RPC déterminent l’identité à partir de la session Supabase Auth et vérifient les droits sur chaque opération. Un étudiant accède à ses propres parties ; un enseignant actif peut consulter le suivi. Les clés Brevo restent côté serveur.

Le suivi est formatif et les états sont autoévaluatifs. Ce dispositif n’a pas pour objet de résister à la falsification d’une note d’examen.
