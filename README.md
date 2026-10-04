# ConsoBingo 1.0

**Version prête pour GitHub et Streamlit Cloud.** Commencer par [LIRE_AVANT_GITHUB.md](LIRE_AVANT_GITHUB.md). Les fichiers `app.py` et `requirements.txt` doivent rester à la racine du dépôt. Le modèle des paramètres à renseigner dans Streamlit est `secrets.toml.example`.

Jeu individuel d’autoévaluation pour le cours de comportement du consommateur. Une BD met en scène Léa, qui compare trois salles de sport. L’étudiant analyse son parcours puis conseille Pulse, une enseigne de salles de gym.

Le carnet distingue les activités comprises sur ce cas, les aides utilisées, les corrigés consultés et les points à reprendre. Terminer ne verrouille pas le parcours.

## Essayer immédiatement sur son ordinateur

Python 3.12 recommandé, version utilisée pour les vérifications.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
CONSOBINGO_DEMO=true streamlit run app.py
```

Sous Windows PowerShell :

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:CONSOBINGO_DEMO="true"
streamlit run app.py
```

La démo fonctionne sans Supabase ni Brevo. Elle conserve la partie uniquement dans la session ouverte. Aucun courriel n’est envoyé. Fermer ou recharger cette démo peut réinitialiser le jeu.

## Mettre en ligne

Suivre **[DEPLOIEMENT.md](DEPLOIEMENT.md)**. Le projet contient le SQL, l’exemple de secrets et les ressources graphiques. Aucun compte, mot de passe ou fichier d’étudiants n’est livré.

La connexion utilise les codes Supabase Auth habituels. Par défaut, les étudiants et enseignants viennent directement des tables `swot_students` et `swot_teachers`, dans le même projet Supabase. ConsoBingo ne recopie pas cet annuaire. Ses parties et ses courriels utilisent des tables distinctes `conso_*`.

## Parcours

1. **La BD** : annoter les étapes EKB, puis les influences et deux conséquences sur le choix.
2. **Du message à l’attitude** : réordonner cinq vignettes, au clavier ou par déplacement.
3. **Les offres** : choisir les critères utiles, les justifier et reconstituer un tableau à partir de documents mélangés.
4. **Les règles** : appliquer trois règles, nommer le modèle puis tester une modification de l’offre.
5. **Les chiffres** : construire les groupes NPS, sélectionner les données et calculer NPS, churn, rétention et LTV simplifiée.
6. **Bonus** : composer deux chaînes complémentaires « indice → objectif → action » pour Pulse.
7. **Mon bilan** : reprendre les activités, télécharger son carnet PDF ou demander son envoi par e-mail si Brevo est configuré.

L’ordre aléatoire est propre à chaque partie et reste stable lors d’une reprise. Les choix répondent immédiatement dans le navigateur ; Python vérifie les réponses. Les sauvegardes ont lieu toutes les 15 secondes en cas de changement et lors des vérifications, de la navigation et du bouton Enregistrer. Attendre « Sauvegarde confirmée » avant de fermer l’onglet.

## Architecture

| Élément | Rôle |
|---|---|
| `app.py` | Point d’entrée Streamlit Cloud |
| `consobingo/portal.py` | Connexion, reprise, espace enseignant, courriels |
| `consobingo/frontend/` | Composant BD HTML/CSS/JS local, sans compilation Node |
| `consobingo/content.py` | Contenus, variantes et corrigés |
| `consobingo/engine.py` | Vérifications formatives, aides, historique |
| `consobingo/cloud.py` | Appels Supabase avec la session de l’utilisateur |
| `sql/01_installation.sql` | Vues d’annuaire, sauvegardes et RPC autorisées |
| `consobingo/mailer.py` | Brevo API ou SMTP, réservation anti-doublon |
| `consobingo/reports.py` | Carnet PDF et export CSV du suivi d’usage |

## Vérification et limites

```bash
pip install -r requirements-dev.txt
python -m pytest -q
```

Les tests PostgreSQL optionnels utilisent une base éphémère PGlite, sans accès au projet réel :

```bash
npm install --no-save @electric-sql/pglite
node tests/test_sql.cjs
```

Le livrable a été vérifié localement. La connexion aux comptes réels, la réception du code et la distribution des courriels doivent être vérifiées après configuration dans l’environnement de déploiement. Il n’y a pas de dépendance à une API d’IA.

Le jeu porte sur un cas et les notions choisies dans le polycopié fourni. Le repère « Compris sur ce cas » décrit la compréhension observée dans cette situation.

Voir [PEDAGOGIE.md](PEDAGOGIE.md) pour les principes des corrections et [VERIFICATION.md](VERIFICATION.md) pour le périmètre testé.
