"""Moteur formatif déterministe. Pas de note académique ni de classement."""
from __future__ import annotations
import ast
import copy
from datetime import datetime, timezone
import hashlib
import json
import math
import random
import re
import secrets
from uuid import uuid4
from . import __version__
from . import content as C
MAX_ATTEMPTS = 30

def now():
    return datetime.now(timezone.utc).isoformat()

def number(value):
    if isinstance(value, bool):
        return None
    text = str(value if value is not None else "").strip().lower().replace("−", "-")
    text = re.sub(r"[\s\u00a0\u202f]", "", text).replace(",", ".")
    text = re.sub(r"(?:€/mois|€/client|euros?|points?|€|%|h|min|mois)$", "", text)
    try:
        n = float(text)
        return n if math.isfinite(n) else None
    except (ValueError, TypeError):
        return None

def same_number(value, expected):
    n = number(value)
    return n is not None and abs(n-expected) <= 0.011

def calculate(expression):
    text = str(expression).replace(",", ".").replace("−", "-").replace("×", "*").replace("÷", "/")
    if not 0 < len(text) <= 160:
        raise ValueError("Saisis une expression de 160 caractères maximum.")
    try:
        tree = ast.parse(text.strip(), mode="eval")
        if len(list(ast.walk(tree))) > 80:
            raise ValueError()
        def visit(n):
            if isinstance(n, ast.Expression): return visit(n.body)
            if isinstance(n, ast.Constant) and type(n.value) in (int,float): return float(n.value)
            if isinstance(n, ast.UnaryOp) and isinstance(n.op,(ast.UAdd,ast.USub)): return visit(n.operand)*(1 if isinstance(n.op,ast.UAdd) else -1)
            if isinstance(n, ast.BinOp) and isinstance(n.op,(ast.Add,ast.Sub,ast.Mult,ast.Div)):
                a,b = visit(n.left),visit(n.right)
                if isinstance(n.op,ast.Add): return a+b
                if isinstance(n.op,ast.Sub): return a-b
                if isinstance(n.op,ast.Mult): return a*b
                return a/b
            raise ValueError()
        result = visit(tree)
        if not math.isfinite(result) or abs(result) > 1e15: raise ValueError()
        return result
    except (SyntaxError, ValueError, ZeroDivisionError, OverflowError, RecursionError):
        raise ValueError("Utilise des nombres, +, −, ×, / et des parenthèses. Vérifie aussi le diviseur.") from None

def default_answers():
    return {"ekb":{}, "factors":{}, "influence_links":[{"clue":"","effect":""} for _ in range(2)],
            "attitude":[], "criteria":[], "criteria_evidence":{}, "table":{},
            "rules":{k:{"keep":[],"model":"","counter_keep":[]} for k in C.RULES},
            "metrics":{m["id"]:{"groups":{},"data":{},"result":""} for m in C.METRICS},
            "bonus":[{"clue":"","objective":"","action":""} for _ in range(2)]}

def orders(seed):
    rng=random.Random(seed)
    def mix(values):
        values=list(values);rng.shuffle(values);return values
    result={"panels":mix(p["letter"] for p in C.BASE["panels"]),"criteria":mix(C.CRITERIA),"documents":mix(d["id"] for d in C.DOCUMENTS),"rules":mix(C.RULES),"survey":mix(C.SURVEY),"objectives":mix(C.OBJECTIVES),"actions":mix(C.ACTIONS),"bonus_clues":mix(C.BONUS_KEY),"effects":mix(C.EFFECTS),"factors":mix(range(3)),"metric_documents":mix(d["id"] for d in C.METRIC_DOCS)}
    result["offers"]={k:mix(C.OFFERS) for k in C.RULES}
    result["models"]={k:mix(C.MODEL_NAMES) for k in C.RULES}
    return result

def new_game(seed=None):
    seed=secrets.randbits(32) if seed is None else int(seed)
    if not 0 <= seed <= 4294967295: raise ValueError("Graine de partie invalide.")
    a=default_answers();a["attitude"]=[x["id"] for x in C.ATTITUDE]
    random.Random(seed ^ 0xA773).shuffle(a["attitude"])
    if a["attitude"]==[x["id"] for x in C.ATTITUDE]: a["attitude"]=a["attitude"][1:]+a["attitude"][:1]
    return {"app":"ConsoBingo","schema_version":1,"version":__version__,"case_id":"lea-pulse-v1","run_id":str(uuid4()),"seed":seed,"answers":a,"history":{},"feedback":{},"aids":{},"unlocked":[],"ui":{"screen":"home","mode":"ekb","rule":orders(seed)["rules"][0],"metric":"nps"},"finished_at":None,"created_at":now()}

def validate_game(game):
    if not isinstance(game,dict) or game.get("app")!="ConsoBingo" or game.get("schema_version")!=1 or game.get("case_id")!="lea-pulse-v1":
        raise ValueError("Cette sauvegarde n’appartient pas à cette version de ConsoBingo.")
    if type(game.get("seed")) is not int or not 0<=game["seed"]<=4294967295: raise ValueError("Partie invalide.")
    if len(json.dumps(game,ensure_ascii=False).encode())>500_000: raise ValueError("Sauvegarde trop volumineuse.")
    for key in ("answers","history","feedback","aids","ui"):
        if not isinstance(game.get(key),dict): raise ValueError("Sauvegarde incomplète.")
    return game

def merge_input(game, answers, ui=None):
    """Ne reçoit du navigateur que les réponses éditables, jamais le profil ou le corrigé."""
    if not isinstance(answers,dict) or len(json.dumps(answers).encode())>60_000: raise ValueError("Réponses invalides.")
    a=default_answers()
    for sec,maxv in (("ekb",5),("factors",2)):
        incoming=answers.get(sec,{})
        if not isinstance(incoming,dict): raise ValueError("Annotations invalides.")
        a[sec]={k:v for k,v in incoming.items() if k in C.CLUES and type(v) is int and 0<=v<=maxv}
    for sec,fields in (("influence_links",("clue","effect")),("bonus",("clue","objective","action"))):
        vals=answers.get(sec,[])
        if not isinstance(vals,list): raise ValueError("Liens invalides.")
        for i,v in enumerate(vals[:2]):
            if not isinstance(v,dict): continue
            a[sec][i]={k:str(v.get(k,""))[:80] for k in fields}
    attitude=answers.get("attitude",game["answers"]["attitude"])
    if not isinstance(attitude,list) or sorted(attitude)!=sorted(x["id"] for x in C.ATTITUDE): raise ValueError("Ordre de vignettes invalide.")
    a["attitude"]=list(attitude)
    criteria=answers.get("criteria",[])
    if not isinstance(criteria,list) or any(type(x) is not str for x in criteria): raise ValueError("Critères invalides.")
    a["criteria"]=list(dict.fromkeys(x for x in criteria if x in C.CRITERIA))[:4]
    evidence=answers.get("criteria_evidence",{})
    if not isinstance(evidence,dict): raise ValueError("Justifications invalides.")
    a["criteria_evidence"]={k:str(v)[:20] for k,v in evidence.items() if k in C.CRITERIA}
    table=answers.get("table",{})
    if not isinstance(table,dict): raise ValueError("Tableau invalide.")
    a["table"]={k:str(v)[:50] for k,v in table.items() if k in {f"{o}_{c}" for o in C.OFFERS for c in C.CRITERIA}}
    rules=answers.get("rules",{})
    if not isinstance(rules,dict): raise ValueError("Règles invalides.")
    for k in C.RULES:
        v=rules.get(k,{})
        if not isinstance(v,dict): continue
        for field in ("keep","counter_keep"):
            if not isinstance(v.get(field,[]),list): raise ValueError("Sélection invalide.")
            a["rules"][k][field]=list(dict.fromkeys(x for x in v.get(field,[]) if isinstance(x,str) and x in C.OFFERS))
        a["rules"][k]["model"]=v.get("model","") if v.get("model","") in C.MODEL_NAMES else ""
    metrics=answers.get("metrics",{})
    if not isinstance(metrics,dict): raise ValueError("Indicateurs invalides.")
    for m in C.METRICS:
        v=metrics.get(m["id"],{})
        if not isinstance(v,dict) or not isinstance(v.get("data",{}),dict) or not isinstance(v.get("groups",{}),dict): raise ValueError("Calcul invalide.")
        a["metrics"][m["id"]]={"data":{f:str(v.get("data",{}).get(f,""))[:50] for f,_,_ in m["fields"]},"result":str(v.get("result",""))[:50],"groups":{k:g for k,g in v.get("groups",{}).items() if k in C.SURVEY and isinstance(g,str) and g in C.SURVEY_GROUPS}}
    game["answers"]=a
    if isinstance(ui,dict):
        for k in ("screen","mode","rule","metric"):
            if k in ui: game["ui"][k]=str(ui[k])[:30]
    return game

def fingerprint(game,section):
    a=game["answers"]
    if section=="factors": relevant=[a["factors"],a["influence_links"]]
    elif section=="table": relevant=[a[k] for k in ("criteria","criteria_evidence","table")]
    elif section.startswith("rule_"): relevant=a["rules"][section[5:]]
    elif section.startswith("selection_"): relevant=a["rules"][section[10:]]["keep"]
    elif section.startswith("metric_"): relevant=a["metrics"][section[7:]]
    else: relevant=a.get(section)
    return hashlib.sha256(json.dumps(relevant,sort_keys=True,ensure_ascii=False).encode()).hexdigest()

def item(key,label,ok,detail): return {"key":key,"label":label,"ok":bool(ok),"detail":detail}

def evaluate(game,section):
    a=game["answers"];items=[];note="";extra=""
    if section in ("ekb","factors"):
        key="ekb" if section=="ekb" else "factors"
        required=[k for k,c in C.CLUES.items() if "ekb" in c] if key=="ekb" else C.FACTOR_REQUIRED
        labels=C.BASE["cats"][key]
        for k in required:
            c=C.CLUES[k];expected=c[key]
            items.append(item(k,c["text"],a[key].get(k)==expected,f"{labels[expected]}. {c['why']}"))
        for k,value in a[key].items():
            if k in required: continue
            if key=="factors" and k in C.FACTOR_OPTIONAL and value==C.FACTOR_OPTIONAL[k]:
                extra="Tu as aussi repéré la motivation de retrouver de l’énergie : cette lecture individuelle est recevable, en plus de son rôle dans EKB."
            else: items.append(item(k,C.CLUES[k]["text"],False,"Cet extrait ne constitue pas ici un indice explicite de cette catégorie pour le choix initial. Replace-le dans son contexte ou retire l’annotation."))
        if key=="factors":
            used=set()
            for i,link in enumerate(a["influence_links"]):
                clue=link["clue"];effect=link["effect"];ok=clue in C.EFFECT_KEY and C.EFFECT_KEY[clue]==effect and clue not in used
                used.add(clue)
                detail=C.EFFECTS[C.EFFECT_KEY[clue]] if clue in C.EFFECT_KEY else "Choisis un indice de la BD et sa conséquence sur la décision."
                if clue and list(x["clue"] for x in a["influence_links"]).count(clue)>1: detail+=" Relie deux indices différents pour expliquer plusieurs influences."
                items.append(item(f"link{i}",f"Lien indice → conséquence {i+1}",ok,detail))
            note="L’expérience passée rend l’accompagnement important, tandis que le budget et le temps limitent les options. L’entourage intervient aussi. Les six indices principaux suffisent, la motivation est une lecture supplémentaire acceptée."
        else: note="Une intention n’est pas un achat réalisé. Après usage, Léa confronte le service vécu à ses attentes. EKB aide à lire ce parcours, sans imposer la même succession à tous les achats."
    elif section=="attitude":
        for i,c in enumerate(C.ATTITUDE): items.append(item(str(i),c["label"],a["attitude"][i]==c["id"],c["why"]))
        note="Comprendre une promesse ne suffit pas à y croire. Ici, le témoignage de Sarah soutient son acceptation. La rétention désigne la mémoire du message, pas encore la fidélisation du client."
    elif section=="table":
        selected=set(a["criteria"])
        for k in sorted(C.CORE_CRITERIA): items.append(item("criterion_"+k,C.CRITERIA[k]["label"],k in selected,"Ce critère répond à une contrainte explicitement exprimée par Léa."))
        for k in a["criteria"]:
            valid=k in C.CRITERIA_EVIDENCE
            items.append(item("evidence_"+k,"Pertinence : "+C.CRITERIA[k]["label"],valid and a["criteria_evidence"].get(k) in C.CRITERIA_EVIDENCE.get(k,set()),"Relie ce critère au passage qui le justifie." if valid else "Cette caractéristique peut compter pour d’autres clients, mais aucun besoin exprimé par Léa ne la rend décisive ici."))
            for oid,o in C.OFFERS.items():
                expected=o[k];detail=f"{o['name']} : {expected} {C.CRITERIA[k]['unit']}."
                if oid=="pulse" and k=="fee": detail="Pulse : 36 € + 3 € obligatoires = 39 € par mois. Compare le coût total."
                if oid=="tempo" and k=="coach": detail="Tempo : 0 séance incluse. Une prestation disponible en supplément n’est pas une prestation incluse."
                items.append(item(oid+"_"+k,o["name"]+" · "+C.CRITERIA[k]["label"],same_number(a["table"].get(oid+"_"+k),expected),detail))
        note="Prix total, trajet et accompagnement permettent l’arbitrage. La fermeture est un critère recevable lié à ses horaires, même si aucune salle ne ferme avant 21 h. Surface, sauna et audience sociale ne sont pas justifiés par ses propos."
    elif section.startswith(("rule_","selection_")):
        selection=section.startswith("selection_");rid=section.split("_",1)[1];r=C.RULES[rid];v=a["rules"][rid]
        items.append(item("keep","Salles conservées",set(v["keep"])==set(r["keep"]),"À conserver : "+", ".join(C.OFFERS[k]["name"] for k in r["keep"])+". "+r["why"]))
        if not selection:
            items.append(item("model","Modèle de décision",v["model"]==r["model"],C.MODEL_NAMES[r["model"]]+". "+r["why"]))
            items.append(item("counter","Après le changement",set(v["counter_keep"])==set(r["counter_keep"]),r["counter_why"]))
        note=r["transfer"]
    elif section.startswith("metric_"):
        mid=section[7:];m=next(x for x in C.METRICS if x["id"]==mid);v=a["metrics"][mid]
        if mid=="nps":
            for k,row in C.SURVEY.items():
                expected="prom" if row["note"]>=9 else "pass" if row["note"]>=7 else "det"
                items.append(item(k,f"Note {row['note']} · {row['count']} réponses",v["groups"].get(k)==expected,C.SURVEY_GROUPS[expected]))
        for field,label,source in m["fields"]:
            items.append(item(field,label,same_number(v["data"].get(field),C.FACTS[source]["v"]),"L’indice utile est : "+C.FACTS[source]["label"]+"."))
        items.append(item("result","Résultat",same_number(v["result"],m["result"]),f"{m['result']} {m['unit']}."))
        note=m["why"]
        if mid=="nps" and same_number(v["data"].get("total"),42): extra="Les passifs restent inclus dans les 60 réponses, même s’ils ne sont pas soustraits au numérateur."
        if mid=="ltv" and same_number(v["result"],702): extra="702 € est un revenu cumulé. Il faut ici utiliser la marge de contribution."
    elif section=="bonus":
        evidence=set();objectives=set();actions=set()
        for i,link in enumerate(a["bonus"]):
            clue,obj,action=link["clue"],link["objective"],link["action"]
            eligible=C.BONUS_KEY.get(clue,{})
            relation_ok=obj in eligible
            items.append(item(f"objective{i}",f"Chaîne {i+1} · indice → objectif",relation_ok,"L’objectif doit répondre à ce que cet indice révèle. "+("Objectif(s) recevable(s) : "+", ".join(C.OBJECTIVES[k] for k in eligible) if eligible else "Choisis d’abord un indice du cas.")))
            action_ok=relation_ok and action in eligible[obj]
            detail="L’action doit agir sur cet objectif."
            if relation_ok: detail+=" Possibilités : "+" ou ".join(C.ACTIONS[k] for k in sorted(eligible[obj]))+"."
            if action=="discount" and action_ok: detail+=" La remise répond au budget, mais 39 € est déjà sous le plafond de Léa. Elle ne résout pas les difficultés d’accompagnement ou d’horaires."
            items.append(item(f"action{i}",f"Chaîne {i+1} · objectif → action",action_ok,detail))
            evidence.add(clue);objectives.add(obj);actions.add(action)
        distinct=len(evidence)==len(objectives)==len(actions)==2 and "" not in evidence|objectives|actions
        items.append(item("distinct","Deux obstacles différents",distinct,"Deux actions sur le même obstacle laissent les autres contraintes sans réponse. Choisis deux chaînes complémentaires."))
        note="Plusieurs combinaisons sont recevables. La cohérence indice → objectif → action compte davantage que le nom de l’action. Une recommandation doit aussi préciser ce qu’elle ne résout pas."
    else: raise ValueError("Activité inconnue.")
    good=sum(x["ok"] for x in items)
    return {"section":section,"correct":good,"total":len(items),"complete":bool(items) and good==len(items),"items":items,"note":note,"extra":extra,"fingerprint":fingerprint(game,section),"at":now()}

def record_check(game,section):
    result=evaluate(game,section);game["feedback"][section]=result
    if section.startswith("selection_"):
        rid=section[10:]
        if rid not in game["unlocked"]: game["unlocked"].append(rid)
        return result
    history=game["history"].setdefault(section,[])
    if not history or history[-1]["fingerprint"]!=result["fingerprint"]:
        history.append({k:result[k] for k in ("correct","total","complete","fingerprint","at")}|{"aided":bool(game["aids"].get(section))})
        if len(history)>MAX_ATTEMPTS: del history[1]
    return result

def hint(game,section):
    previous=game["aids"].get(section,0)
    level=min(2,previous+1);game["aids"][section]=max(previous,level)
    if section.startswith("metric_"):
        m=next(x for x in C.METRICS if x["id"]==section[7:])
        text="Identifie la population suivie, la période et l’unité du résultat. Pour la valeur vie, distingue revenu et marge."
        if level==2: text=m["formula"]
    else:
        hints={"ekb":"Cherche ce que Léa fait à chaque moment. Les propos sur son budget ou son passé donnent un contexte.","factors":"Distingue caractéristiques personnelles, circonstances du moment et influence de l’entourage. Puis relie deux indices à leurs effets.","attitude":"Être exposée, remarquer, comprendre, croire et se souvenir sont des opérations distinctes.","table":"Pars des contraintes de Léa. Reconstitue le coût obligatoire et distingue séance incluse et séance facturée en supplément.","bonus":"Pars d’un obstacle observé, puis choisis ce que tu veux changer et une action capable d’y répondre."}
        text=hints.get(section,"Applique les mots de la règle. Une priorité absolue, des seuils reliés par ET et des seuils reliés par OU ne produisent pas les mêmes choix.")
    return text

def apply_solution(game,section):
    # Le corrigé reste accessible, sans verrouillage ni pénalité académique.
    was_complete=bool(game["feedback"].get(section,{}).get("complete") and game["feedback"][section].get("fingerprint")==fingerprint(game,section))
    if not was_complete: game["aids"][section]=3
    a=game["answers"]
    if section=="ekb": a["ekb"]={k:c["ekb"] for k,c in C.CLUES.items() if "ekb" in c}
    elif section=="factors":
        a["factors"]={k:C.CLUES[k]["factors"] for k in C.FACTOR_REQUIRED}
        a["influence_links"]=[{"clue":"b2","effect":"coaching"},{"clue":"a2","effect":"budget"}]
    elif section=="attitude": a["attitude"]=[x["id"] for x in C.ATTITUDE]
    elif section=="table":
        a["criteria"]=["fee","travel","coach","close"]
        a["criteria_evidence"]={k:sorted(v)[0] for k,v in C.CRITERIA_EVIDENCE.items()}
        a["table"]={f"{o}_{k}":str(v[k]) for o,v in C.OFFERS.items() for k in a["criteria"]}
    elif section.startswith("rule_"):
        rid=section[5:];r=C.RULES[rid]
        a["rules"][rid]={"keep":r["keep"].copy(),"model":r["model"],"counter_keep":r["counter_keep"].copy()}
        if rid not in game["unlocked"]: game["unlocked"].append(rid)
    elif section.startswith("metric_"):
        mid=section[7:];m=next(x for x in C.METRICS if x["id"]==mid)
        a["metrics"][mid]={"data":{f:str(C.FACTS[s]["v"]) for f,_,s in m["fields"]},"result":str(m["result"]),"groups":{k:("prom" if v["note"]>=9 else "pass" if v["note"]>=7 else "det") for k,v in C.SURVEY.items()} if mid=="nps" else {}}
    elif section=="bonus": a["bonus"]=[{"clue":"b2","objective":"risk","action":"trial"},{"clue":"d2","objective":"fit","action":"calendar"}]
    else: raise ValueError("Activité inconnue.")
    result=evaluate(game,section);game["feedback"][section]=result
    # Voir la correction n’ajoute jamais une tentative autonome fictive.
    return result

def summary(game):
    rows=[]
    for key,label in C.SECTION_LABELS.items():
        h=game["history"].get(key,[]);f=game["feedback"].get(key);fresh=bool(f and f.get("fingerprint")==fingerprint(game,key));aided=bool(game["aids"].get(key))
        if game["aids"].get(key)==3: status="Corrigé consulté"
        elif fresh and f["complete"]: status="Compris avec aide" if aided else "Compris sur ce cas"
        elif h: status="À reprendre" if fresh else "Réponses modifiées"
        else: status="À explorer"
        rows.append({"id":key,"label":label,"status":status,"attempts":len(h),"first":h[0] if h else None,"last":h[-1] if h else None,"aided":aided,"checked":bool(h),"complete":bool(fresh and f["complete"]),"fresh":fresh})
    return rows

def public_state(game):
    validate_game(game)
    return {k:copy.deepcopy(game[k]) for k in ("run_id","seed","answers","feedback","aids","unlocked","ui","finished_at")}|{"orders":orders(game["seed"]),"summary":summary(game),"fresh_feedback":[k for k,f in game["feedback"].items() if f.get("fingerprint")==fingerprint(game,k)]}

def process_event(game,event):
    if not isinstance(event,dict): raise ValueError("Message invalide.")
    if event.get("run_id")!=game["run_id"]: raise ValueError("Cette action appartient à une autre partie.")
    result=copy.deepcopy(game)
    merge_input(result,event.get("answers",{}),event.get("ui",{}))
    kind=event.get("kind","checkpoint");section=str(event.get("section",""));message=""
    if kind=="check": record_check(result,section)
    elif kind=="hint": message=hint(result,section)
    elif kind=="solution": apply_solution(result,section)
    elif kind=="finish": result["finished_at"]=now();result["ui"]["screen"]="end"
    elif kind=="calculate": message=format(calculate(event.get("expression","")),".12g").replace(".",",")
    elif kind not in ("checkpoint","restart","leave"): raise ValueError("Action inconnue.")
    validate_game(result)
    return result,message
