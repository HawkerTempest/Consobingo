# ConsoBingo : version prête pour GitHub

Cette archive contient le code du jeu, ses illustrations, le SQL et les exemples de configuration. Elle est organisée comme la racine d’un dépôt GitHub. Il n’y a pas de dossier supplémentaire à conserver au-dessus de `app.py`.

## 1. Déposer les fichiers dans GitHub

Décompresser l’archive sur l’ordinateur, puis ajouter **son contenu** au dépôt GitHub choisi. Ne pas déposer le fichier ZIP lui-même.

À la racine du dépôt, vérifier la présence de :

- `app.py` ;
- `requirements.txt` ;
- `consobingo/`, avec ses sous-dossiers `frontend/assets/` et `fonts/` ;
- `sql/01_installation.sql` ;
- `secrets.toml.example` ;
- `README.md` et les autres guides.

L’archive contient aussi `.streamlit/config.toml` pour l’apparence et `.gitignore` pour exclure les secrets. Ces noms commencent par un point et peuvent être masqués dans l’explorateur de fichiers. Les conserver lors de l’ajout au dépôt. Le jeu peut démarrer sans le fichier de thème, mais les polices et les images du dossier `consobingo/` sont nécessaires.

## 2. Installer le SQL dans Supabase

Dans **le projet Supabase de SWOTmania**, exécuter intégralement `sql/01_installation.sql`.

Le choix par défaut réutilise directement `swot_students` et `swot_teachers`. Il n’y a pas d’import CSV supplémentaire. Le jeu conserve ses propres parties dans des tables distinctes. Si l’annuaire de référence est exclusivement celui de STP-by-Step, suivre l’option décrite dans `DEPLOIEMENT.md` avant la première installation.

## 3. Déployer dans Streamlit Cloud

Créer l’application à partir du dépôt GitHub, avec :

| Paramètre | Valeur |
|---|---|
| Fichier principal | `app.py` |
| Version Python | `3.12` |
| Dépendances | `requirements.txt` à la racine |

Dans les secrets de l’application Streamlit, copier le contenu de `secrets.toml.example`, puis renseigner les paramètres du projet Supabase et de Brevo déjà utilisés pour les jeux précédents. Remplacer `APP_URL` par l’adresse de ConsoBingo. Garder `CONSOBINGO_DEMO = false` pour l’accès étudiant.

**Les identifiants réels se renseignent dans Streamlit, pas dans les fichiers publiés sur GitHub.** Seul le fichier d’exemple contenant des valeurs fictives est fourni.

## Essayer la démo avant de brancher la base

Pour un premier essai sur Streamlit, il suffit de définir ce secret :

```toml
CONSOBINGO_DEMO = true
```

Cette démo fonctionne sans Supabase ni Brevo. Elle n’envoie aucun courriel et ne sauvegarde pas de résultats étudiants. Remettre la valeur à `false` et ajouter les autres secrets pour l’utilisation connectée.

Les détails de configuration, de connexion par code et de vérification des courriels figurent dans `DEPLOIEMENT.md`.

Le jeu reste un outil d’autoévaluation non noté. Cette archive ne crée pas elle-même un dépôt GitHub et ne déploie pas l’application.
