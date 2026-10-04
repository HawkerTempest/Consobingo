"""Contenus et corrigés du cas. Aucune donnée nominative dans ce module."""
from __future__ import annotations
import copy
import json
from pathlib import Path
BASE = json.loads(Path(__file__).with_name("base_catalog.json").read_text(encoding="utf-8"))
CLUES = {c["id"]: c for c in BASE["clues"]}
CLUES["b1"]["text"] = "Demain, je passe chez Pulse pour prendre l’abonnement. Cette fois, je m’y tiens."
CLUES["b2"]["text"] = "La dernière fois, je suis restée devant les machines sans savoir par quoi commencer. Au bout de trois visites, j’ai laissé tomber."
CLUES["d2"]["text"] = "Cette semaine, avec le dossier urgent, je ne sors pas avant 19 h. Si le trajet s’éternise, je vais encore renoncer."
CLUES["c2"]["text"] = "Chez mes parents, le dimanche, on enfilait les baskets avant même de discuter du programme. Ça m’est resté."
CLUES["a2"]["text"] = "Une fois mon loyer et mes dépenses habituelles payés, je peux mettre 40 € par mois dans la salle, tout compris."
CLUES["f2"]["text"] = "La séance d’essai offerte, c’est jusqu’à ce soir ? Bon… je vais regarder ça tout de suite."
FACTOR_REQUIRED = ["a2", "b2", "c2", "d2", "e2", "f2"]
FACTOR_OPTIONAL = {"d1": 0}
EFFECTS = {
    "budget": "Écarter les offres dont le coût réel dépasse ses ressources",
    "coaching": "Rechercher une aide concrète pour utiliser les appareils",
    "time": "Vérifier la compatibilité du trajet et des horaires",
    "peers": "Se sentir soutenue par quelqu’un de son entourage",
    "values": "Retrouver une pratique qui correspond aux habitudes transmises",
    "urgency": "Accélérer la recherche ou la décision avant la fin de l’offre",
    "motivation": "Chercher à réduire l’écart entre son état actuel et l’énergie souhaitée",
    "status": "Choisir avant tout pour afficher un statut social",
}
EFFECT_KEY = {"a2": "budget", "b2": "coaching", "c2": "values", "d2": "time", "e2": "peers", "f2": "urgency", "d1": "motivation"}
ATTITUDE = copy.deepcopy(BASE["mcg"])
ATTITUDE[0].update(art="exposure", who="Sur le trajet", text="Léa laisse son regard flotter. Une affiche de salle de sport se trouve sur la paroi, dans son champ de vision.")
ATTITUDE[1].update(who="Quelques instants après", text="Léa tourne les yeux vers l’affiche. « Tiens… après le travail ? »")
ATTITUDE[2].update(text="« Débutants accompagnés »… Donc quelqu’un me montrera par où commencer, même si je ne connais pas les machines.")
ATTITUDE[3].update(text="Si ton coach t’a vraiment accompagnée comme ça, je veux bien essayer.")
ATTITUDE[4].update(who="Un autre jour", text="La salle dont Sarah m’a parlé… Celle avec les séances accompagnées. Pulse, voilà !")
OFFERS = {o["id"]: {**o, "area": 500 if o["id"] == "pulse" else 800 if o["id"] == "tempo" else 350,
                      "followers": 2100 if o["id"] == "pulse" else 8200 if o["id"] == "tempo" else 1450,
                      "sauna": 0 if o["id"] == "tempo" else 1} for o in BASE["offers"]}
CRITERIA = {c["id"]: c for c in BASE["columns"]}
CRITERIA.update({
    "area": {"id": "area", "label": "Surface totale", "unit": "m²"},
    "followers": {"id": "followers", "label": "Audience Instagram", "unit": "abonnés"},
    "sauna": {"id": "sauna", "label": "Présence d’un sauna", "unit": "1 = oui, 0 = non"},
})
CORE_CRITERIA = {"fee", "travel", "coach"}
CRITERIA_EVIDENCE = {"fee": {"a2"}, "travel": {"d2"}, "close": {"d2"}, "coach": {"b2"}}
# Les textes mêlent volontairement caractéristiques utiles, composantes de prix et informations non décisives.
DOCUMENTS = [
    {"id": "window", "art": 4, "title": "Photographie de la vitrine", "lines": [
        "Pulse affiche 36 € par mois pour l’abonnement de base. Les portes ferment à 22 h.",
        "Sur la vitrine voisine : Tempo, 29 € par mois, tout compris pour l’accès libre. Plateau de 800 m².",
        "Les trois salles sont sans engagement et sans frais d’inscription."]},
    {"id": "email", "art": 8, "title": "Un mail et une annotation au dos", "lines": [
        "Chez Pulse, le forfait services obligatoire ajoute 3 € par mois au tarif de base. Aucun autre supplément obligatoire.",
        "Atelier Sport confirme 49 € par mois, tout compris. Sa page Instagram compte 1 450 abonnés.",
        "Le plateau de Pulse mesure 500 m². Celui d’Atelier Sport mesure 350 m²."]},
    {"id": "sarah", "art": 1, "title": "Le message vocal de Sarah", "lines": [
        "Du bureau, j’ai mis 12 minutes pour rejoindre Pulse. Leur abonnement comprend deux séances accompagnées chaque semaine.",
        "Tempo facture chaque séance accompagnée 12 € en plus de l’abonnement. Aucune n’est incluse.",
        "Atelier Sport en inclut quatre par semaine et ferme à 21 h. Les vestiaires ont été repeints en bleu."]},
    {"id": "phone", "art": 3, "title": "Trois onglets sur le téléphone", "lines": [
        "Calcul d’itinéraire depuis le bureau : Atelier Sport, 8 minutes. Tempo, 25 minutes.",
        "Tempo ferme à 23 h. Sur Instagram : 8 200 abonnés pour Tempo, 2 100 pour Pulse.",
        "Un sauna chez Pulse et Atelier Sport. Aucun chez Tempo. Batterie du téléphone : 12 %."]},
]
MODEL_NAMES = {"lex": "Lexicographique", "and": "Conjonctive", "or": "Disjonctive", "weighted": "Compensatoire", "aspects": "Élimination par aspects"}
RULES = {
    "price": {**BASE["rules"][0], "model": "lex", "counter_text": "Tempo passe à 42 € par mois. Tous les autres renseignements et la priorité de Léa restent identiques. Que conserve-t-elle ?", "counter_keep": ["pulse"], "counter_why": "Pulse devient le moins cher, à 39 €. Le critère prioritaire reste le prix."},
    "all": {**BASE["rules"][1], "model": "and", "counter_text": "Tempo ouvre une entrée plus proche : le trajet tombe à 10 minutes. Tout le reste est inchangé. Que conserve Léa ?", "counter_keep": ["pulse"], "counter_why": "Tempo respecte maintenant le trajet, mais toujours pas le seuil d’accompagnement inclus. Toutes les conditions restent nécessaires."},
    "either": {**BASE["rules"][2], "model": "or", "counter_text": "Atelier Sport n’inclut plus que trois séances accompagnées par semaine. Tout le reste est inchangé. Quelles salles restent en lice ?", "counter_keep": ["tempo"], "counter_why": "Atelier Sport ne franchit plus le seuil de quatre séances et reste au-dessus de 30 €. Tempo passe toujours par le prix."},
}
METRICS = copy.deepcopy(BASE["metrics"])
# Décomposition des 60 réponses : les regroupements sont à construire par l’étudiant.
SURVEY = {"note10": {"note": 10, "count": 18}, "note9": {"note": 9, "count": 12},
          "note8": {"note": 8, "count": 10}, "note7": {"note": 7, "count": 8},
          "note6": {"note": 6, "count": 5}, "note5": {"note": 5, "count": 3},
          "note3": {"note": 3, "count": 2}, "note0": {"note": 0, "count": 2}}
SURVEY_GROUPS = {"prom": "Promoteurs", "pass": "Passifs", "det": "Détracteurs"}
FACTS = BASE["facts"]
METRIC_DOCS = [
    {"id": "members", "art": 8, "title": "Carnet des abonnements", "lines": ["35 nouveaux membres ce mois-ci. Parmi les 200 présents le premier jour, 20 ont résilié avant la fin du mois. Aucun autre mouvement.", "L’affiche à l’accueil annonce toujours 36 € de base, auxquels s’ajoutent 3 € de services obligatoires par mois."]},
    {"id": "money", "art": 4, "title": "Note de gestion", "lines": ["Pour chaque membre et chaque mois, 25 € de coûts sont retenus dans le calcul de la marge de contribution.", "Hypothèse de l’exercice : revenu et coûts constants, relation moyenne de 18 mois. Pas de coût d’acquisition ni d’actualisation."]},
    {"id": "noise", "art": 3, "title": "Message de l’équipe", "lines": ["La salle a ouvert il y a 5 ans. La vidéo du mois compte 1 200 vues et 43 mentions J’aime.", "La responsable veut comprendre à la fois la recommandation, les départs et la valeur des relations clients."]},
]
OBJECTIVES = {"risk": "Réduire l’incertitude sur l’accompagnement", "fit": "Vérifier la compatibilité avec son quotidien", "budget": "Rendre le coût total compatible et compréhensible", "social": "Soutenir la pratique avec l’entourage", "continuity": "Faciliter une reprise progressive et durable", "awareness": "Faire connaître le nom de la marque", "urgency": "Rendre l’échéance de l’offre claire"}
ACTIONS = {"trial": "Une première séance guidée, avec démonstration des appareils", "video": "Une courte vidéo montrant une vraie séance débutant avec un coach", "calendar": "Un planning précis des séances accompagnées après 19 h", "late_trial": "Un essai accompagné à 19 h 45, réservable à l’avance", "price": "Un récapitulatif visible : 36 € + 3 €, soit 39 € tout compris", "discount": "Une remise de 3 € par mois, sans changement du service", "buddy": "Une première séance à deux avec Sarah", "plan": "Un programme progressif pour les premières semaines", "billboard": "Une campagne d’affichage centrée uniquement sur le logo", "deadline": "Une information exacte et visible sur la date de fin de l’essai offert"}
BONUS_KEY = {
    "b2": {"risk": {"trial", "video"}}, "d2": {"fit": {"calendar", "late_trial"}},
    "a2": {"budget": {"price", "discount"}}, "e2": {"social": {"buddy"}},
    "d1": {"continuity": {"plan", "trial"}}, "f2": {"urgency": {"deadline"}},
}
SECTION_LABELS = {"ekb": "Parcours EKB", "factors": "Facteurs d’influence", "attitude": "Du message à l’attitude", "table": "Comparaison des offres", **{"rule_"+k: "Règle : "+MODEL_NAMES[v["model"]] for k,v in RULES.items()}, **{"metric_"+m["id"]: m["name"] for m in METRICS}, "bonus": "Conseiller Pulse"}
REQUIRED_SECTIONS = [x for x in SECTION_LABELS if x != "bonus"]

def catalog():
    return {
        "clues": [{k:c[k] for k in ("id","speaker","text")} for c in CLUES.values()],
        "panels": BASE["panels"], "stages": BASE["cats"]["ekb"], "factor_labels": BASE["cats"]["factors"],
        "effects": EFFECTS, "attitude": [{k:m[k] for k in ("id","art","who","text")} for m in ATTITUDE],
        "attitude_stages": [m["label"] for m in ATTITUDE], "criteria": CRITERIA, "documents": DOCUMENTS,
        "offers": list(OFFERS.values()), "needs": [{"id":k,"text":CLUES[k]["text"]} for k in ("a2","b2","d2","d1","e2")],
        "models": MODEL_NAMES, "rules": {k:{"text":v["text"],"counter_text":v["counter_text"],"changes":({"tempo":{"fee":42}} if k=="price" else {"tempo":{"travel":10}} if k=="all" else {"atelier":{"coach":3}})} for k,v in RULES.items()},
        "metrics": [{k:m[k] for k in ("id","name","unit","fields")} for m in METRICS],
        "survey": SURVEY, "survey_groups": SURVEY_GROUPS, "metric_documents": METRIC_DOCS,
        "objectives": OBJECTIVES, "actions": ACTIONS,
        "bonus_clues": [{"id":k,"text":CLUES[k]["text"]} for k in BONUS_KEY],
        "sections": SECTION_LABELS,
    }
