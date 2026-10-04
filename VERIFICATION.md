# Vérifications de la version 1.0

Vérifications effectuées localement le 4 octobre 2026, avec Python 3.12, les versions de `requirements.txt`, PostgreSQL via PGlite et Chromium via Playwright.

## Résultats

- **54 tests Python réussis** : cohérence des corrigés, facteurs facultatifs, liens multifactoriels, critères et distracteurs, contre-exemples, calculs, progression formative, sécurité de la calculatrice, exports, transport Brevo simulé et portail Streamlit.
- **49 vérifications PostgreSQL réussies** : script réexécutable, annuaire vivant, étudiants inactifs, accès anonyme interdit, séparation étudiant/enseignant, lecture de sa seule partie, sauvegardes idempotentes, reprise et conflit d’onglets, archives, réservation anti-doublon des courriels.
- **Parcours navigateur complet réussi** : douze activités vérifiées par le moteur Python à travers le vrai composant Streamlit, septième facteur facultatif accepté, construction du tableau, trois règles et modifications, quatre indicateurs, calculatrice, bonus, bilan PDF téléchargé, retour aux activités et nouvelle partie.
- **Affichage** : contrôle sur ordinateur, puis aux largeurs 390 et 320 pixels. Pas de débordement de page ; le tableau peut défiler horizontalement dans son propre cadre.
- **PDF** : génération et inspection visuelle du carnet, avec police embarquée, accents et pagination.

## Reproduire

Depuis une copie de développement du projet, sans secrets de production :

```bash
pip install -r requirements-dev.txt
python -m pytest -q
npm install --no-save @electric-sql/pglite playwright
npx playwright install chromium
node tests/test_sql.cjs
node tests/test_browser.cjs
```

Le test navigateur lance lui-même Streamlit en démo sur le port 8501, qui doit être libre. Le Python actif doit contenir les dépendances. On peut définir `CONSO_PYTHON` pour choisir son interpréteur. Les captures et le PDF de test sont produits dans `qa-output/`, ignoré par Git. Aucun serveur Node n’est nécessaire pour utiliser le jeu.

## Périmètre encore dépendant du déploiement

Ces tests n’ont pas utilisé le projet Supabase réel, les adresses d’étudiants ni les identifiants Brevo. Le comportement SQL a été exécuté sur une base PostgreSQL éphémère ; l’authentification externe et les envois ont été simulés. Le parcours de connexion et la délivrabilité sont à vérifier avec un compte de test après installation des secrets, comme décrit dans `DEPLOIEMENT.md`.
