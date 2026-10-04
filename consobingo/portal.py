"""Portail Streamlit : OTP, annuaire partagé, reprise et suivi formatif."""
from __future__ import annotations
import copy
import hashlib
import json
import os
from pathlib import Path
import time
from uuid import uuid4
import streamlit as st
from . import __version__
from .cloud import CloudStore, CloudError, ConflictError, game_from_row
from .engine import new_game, process_event, summary, validate_game
from .component import play
from .mailer import valid_email, configured, build_message, dispatch
from .reports import build_pdf, dashboard_rows, csv_export

NAMES=['SUPABASE_URL','SUPABASE_PUBLISHABLE_KEY','SUPABASE_ANON_KEY','BREVO_API_KEY','BREVO_SMTP_HOST','BREVO_SMTP_PORT','BREVO_SMTP_USERNAME','BREVO_SMTP_PASSWORD','BREVO_SENDER_EMAIL','BREVO_SENDER_NAME','APP_URL','EMAIL_ATTACH_PDF','SEND_COMPLETION_EMAILS','CONSOBINGO_DEMO']

def settings():
    result={}
    for key in NAMES:
        try:value=st.secrets.get(key,os.environ.get(key))
        except Exception:value=os.environ.get(key)
        if value is not None:result[key]=value
    for key,default in [('EMAIL_ATTACH_PDF',True),('SEND_COMPLETION_EMAILS',False),('CONSOBINGO_DEMO',False)]:
        result[key]=str(result.get(key,default)).lower() in ('true','1','oui','yes')
    result.setdefault('BREVO_SENDER_NAME','ConsoBingo')
    return result

def store():
    if 'store' not in st.session_state:
        c=settings();key=c.get('SUPABASE_PUBLISHABLE_KEY') or c.get('SUPABASE_ANON_KEY')
        st.session_state.store=CloudStore(c['SUPABASE_URL'],key)
    return st.session_state.store

def install_game(game,row=None):
    st.session_state.game=game
    if row is not None:st.session_state.cloud_row=row
    for key in ('save_packet','sync_error','conflict','after_action','restart_target','pdf_cache'):
        st.session_state.pop(key,None)
    st.session_state.ack='';st.session_state.message='';st.session_state.event_error=''

def try_save():
    packet=st.session_state.get('save_packet')
    if not packet:return True
    try:
        row=store().save(st.session_state.cloud_session,packet['revision'],packet['state'],packet['event_id'],packet['finish'])
    except ConflictError as exc:
        st.session_state.conflict=True;st.session_state.sync_error=str(exc);return False
    except (CloudError,ValueError) as exc:
        st.session_state.sync_error=str(exc);return False
    st.session_state.cloud_row=row
    st.session_state.pop('save_packet',None);st.session_state.pop('sync_error',None)
    return True

def enqueue_save(finish=False):
    if st.session_state.get('demo'):return True
    st.session_state.save_packet={'state':copy.deepcopy(st.session_state.game),'revision':st.session_state.cloud_row['revision'],'event_id':str(uuid4()),'finish':finish}
    return try_save()

def after_save():
    action=st.session_state.get('after_action')
    if not action or st.session_state.get('save_packet'):return
    demo=st.session_state.get('demo',False)
    if action=='restart':
        target=st.session_state.setdefault('restart_target',new_game())
        if demo:install_game(target)
        else:
            try:row=store().restart(st.session_state.cloud_session,st.session_state.cloud_row['revision'],target)
            except (CloudError,ValueError) as exc:st.session_state.sync_error=str(exc);return
            install_game(game_from_row(row),row)
        st.session_state.pop('after_action',None);st.rerun()
    if action=='leave':
        if demo and st.session_state.get('identity',{}).get('role')=='teacher':
            for key in ('game','demo','after_action','ack','message','event_error','pdf_cache'):st.session_state.pop(key,None)
        elif demo:
            install_game(new_game());st.session_state.pop('after_action',None)
        else:
            try:store().close(st.session_state.cloud_session)
            except CloudError:pass
            store().logout();st.session_state.clear()
        st.rerun()

@st.fragment(run_every=30)
def heartbeat():
    if st.session_state.get('demo') or not st.session_state.get('cloud_session'):return
    if st.session_state.get('save_packet') and not st.session_state.get('conflict'):
        if try_save():after_save();st.rerun()
    else:
        try:store().touch(st.session_state.cloud_session)
        except CloudError:pass

def auth_failure(stage, exc):
    """Retourne un diagnostic borné, sans afficher les messages bruts du serveur."""
    hints={
        'PGRST202':'La fonction de vérification est indisponible dans ce projet.',
        '42501':'Les droits d’accès à l’annuaire doivent être vérifiés.',
        'PGRST301':'La clé ou la session Supabase doit être vérifiée.',
        'PGRST303':'La clé ou la session Supabase doit être vérifiée.',
        'invalid_api_key':'La clé Supabase doit être vérifiée.',
        'bad_jwt':'La clé ou la session Supabase doit être vérifiée.',
        'no_authorization':'La configuration de connexion doit être vérifiée.',
        'email_address_not_authorized':'Le service d’envoi Supabase doit être configuré pour cette adresse.',
        'over_email_send_rate_limit':'La limite d’envoi est atteinte. Patiente avant de demander un nouveau code.',
        'over_request_rate_limit':'Les demandes sont trop rapprochées. Patiente avant de réessayer.',
        'email_provider_disabled':'La connexion par e-mail est désactivée dans Supabase.',
        'otp_disabled':'La connexion par code est désactivée dans Supabase.',
        'signup_disabled':'La création du compte de connexion est désactivée dans Supabase.',
        'otp_expired':'Le code est incorrect ou expiré. Utilise le dernier code reçu.',
        'invalid_credentials':'Le code n’a pas été accepté. Vérifie l’adresse et le dernier code reçu.',
        'captcha_failed':'La configuration de vérification de connexion doit être contrôlée.',
        'request_timeout':'Le service n’a pas répondu dans le délai prévu.',
        'unexpected_failure':'Le service a rencontré une erreur. Consulte son journal avec cette référence.',
    }
    reference='INDISPONIBLE';hint='';seen=set();current=exc
    for _ in range(8):
        if current is None or id(current) in seen:break
        seen.add(id(current))
        code=getattr(current,'code',None)
        if isinstance(code,str) and code in hints:
            reference=code;hint=hints[code];break
        if isinstance(current,TimeoutError) or type(current).__name__ in ('ReadTimeout','ConnectTimeout','WriteTimeout','PoolTimeout','AuthRetryableError'):
            reference='DELAI';hint='La réponse du service n’a pas été confirmée.'
        for name in ('status','status_code'):
            status=getattr(current,name,None)
            if reference=='INDISPONIBLE' and type(status) is int and 400<=status<=599:
                reference='HTTP_'+str(status)
        current=current.__cause__ or current.__context__
    labels={
        'CONFIGURATION':'La connexion à Supabase n’a pas pu être préparée.',
        'ANNUAIRE':'La vérification de l’annuaire n’a pas abouti.',
        'ENVOI':'L’envoi du code n’a pas pu être confirmé.',
        'VALIDATION':'La connexion a échoué : le code ou l’accès n’a pas pu être validé.',
        'SESSION':'Le code a été validé, mais la session de jeu n’a pas pu être ouverte.',
    }
    return ' '.join(x for x in (labels[stage],hint,f'Référence : {stage}/{reference}.') if x)


def auth_screen():
    st.title('ConsoBingo')
    st.write('Une BD interactive pour explorer le comportement du consommateur et conseiller Pulse, une enseigne de salles de gym.')
    role=st.radio('Accès',['student','teacher'],format_func=lambda x:'Étudiant' if x=='student' else 'Enseignant',horizontal=True,key='auth_role')
    st.caption('Demande un code, puis saisis-le ci-dessous. Si tu as déjà reçu un code, tu peux directement te connecter avec ton adresse et ce code.')
    # Les deux étapes restent visibles, même après un délai réseau ou une nouvelle session.
    with st.form('auth',enter_to_submit=False):
        email=st.text_input('Adresse e-mail habituelle',placeholder='prenom.nom@grenoble-em.com',key='auth_email').strip().lower()
        send=st.form_submit_button('Recevoir mon code',key='auth_send')
        st.divider()
        code=st.text_input('Code reçu',autocomplete='one-time-code',max_chars=10,key='auth_code')
        verify=st.form_submit_button('Se connecter',type='primary',key='auth_verify')
    if send or verify:
        if not valid_email(email):st.error('Saisis une adresse valide.');return
        if verify and not code.strip():st.error('Saisis le code reçu par e-mail.');return
        try:client=store()
        except Exception as exc:st.error(auth_failure('CONFIGURATION',exc));return
        if send:
            if time.time()-st.session_state.get('otp_at',0)<60:
                st.info('Patiente une minute avant de demander un autre code. Tu peux saisir un code déjà reçu ci-dessus.');return
            try:allowed=client.allowed(email,role)
            except Exception as exc:st.error(auth_failure('ANNUAIRE',exc));return
            if not allowed:
                access='enseignant' if role=='teacher' else 'étudiant'
                st.error(f'Cette adresse n’est pas autorisée pour l’accès {access}. Vérifie le rôle sélectionné et l’adresse saisie.');return
            pending={'email':email,'role':role,'confirmed':False}
            st.session_state.otp_pending=pending
            # Un délai réseau peut survenir après l’envoi : éviter les demandes répétées.
            st.session_state.otp_at=time.time()
            try:client.send_otp(email)
            except Exception as exc:pending['error']=auth_failure('ENVOI',exc)
            else:pending['confirmed']=True
        elif verify:
            try:identity=client.login(email,code.strip(),role)
            except Exception as exc:
                client.logout();st.error(auth_failure('VALIDATION',exc));return
            try:session=client.open_session() if identity['role']=='student' else None
            except Exception as exc:
                client.logout();st.error(auth_failure('SESSION',exc));return
            st.session_state.identity=identity;st.session_state.cloud_session=session;st.session_state.demo=False
            st.session_state.pop('otp_pending',None);st.rerun()
    pending=st.session_state.get('otp_pending')
    if pending and pending['email']==email and pending['role']==role:
        if pending.get('confirmed'):
            st.success('Code envoyé à '+email+'. Saisis-le dans le champ « Code reçu », puis clique sur « Se connecter ».')
        elif pending.get('error'):
            st.warning(pending['error']+' Si le code est arrivé, saisis-le ci-dessus et clique sur « Se connecter ».')
    st.caption('L’accès utilise l’annuaire déjà présent dans les jeux de marketing. Les résultats servent à l’autoévaluation et au suivi d’activité.')

def start_screen():
    p=st.session_state.identity
    st.title('ConsoBingo');st.write(f"{p['first_name']} {p['last_name']} · {p['campus']} · Groupe {p['group_name']}")
    try:row=store().get_run()
    except CloudError as exc:st.error(str(exc));return
    if row:
        st.write('Ton parcours est enregistré. Tu peux le reprendre sur cet appareil, même après avoir consulté le bilan.')
        st.caption('Dernière sauvegarde : '+row['updated_at'])
        if st.button('Reprendre mon parcours ici',type='primary'):
            try:claimed=store().claim(st.session_state.cloud_session)
            except CloudError as exc:st.error(str(exc));return
            install_game(game_from_row(claimed),claimed);st.rerun()
    elif st.button('Commencer mon enquête',type='primary'):
        try:claimed=store().claim(st.session_state.cloud_session,new_game())
        except CloudError as exc:st.error(str(exc));return
        install_game(game_from_row(claimed),claimed);st.rerun()
    if st.button('Se déconnecter'):store().logout();st.session_state.clear();st.rerun()

def report_panel():
    game=st.session_state.game
    if game['ui'].get('screen')!='end':return
    profile=st.session_state.get('identity') if not st.session_state.get('demo') else None
    signature=hashlib.sha256(json.dumps(game,sort_keys=True).encode()).hexdigest()
    if st.session_state.get('pdf_cache',{}).get('signature')!=signature:
        st.session_state.pdf_cache={'signature':signature,'data':build_pdf(game,profile)}
    st.download_button('Télécharger mon bilan personnel (PDF)',st.session_state.pdf_cache['data'],'ConsoBingo_bilan.pdf','application/pdf',key='pdf_bilan')
    if st.session_state.get('demo'):st.caption('Démo : aucun courriel ni résultat étudiant n’est enregistré.');return
    if not game.get('finished_at') or st.session_state.get('sync_error'):return
    conf=settings()
    if not configured(conf):return
    with st.expander('Recevoir mon bilan par e-mail'):
        msg=build_message(profile,'completion',game,conf.get('APP_URL',''))
        st.caption('Destinataire : '+profile['email']);st.text(msg['text'])
        if st.button('Envoyer ce bilan à mon adresse'):
            try:r=dispatch(store(),conf,profile,'completion','',game)
            except (CloudError,ValueError) as exc:st.error(str(exc));return
            st.info(r['message'])
    if conf['SEND_COMPLETION_EMAILS']:
        cycle=st.session_state.cloud_row['cycle']
        if st.session_state.get('completion_cycle')!=cycle:
            st.session_state.completion_cycle=cycle
            try:r=dispatch(store(),conf,profile,'completion','',game)
            except (CloudError,ValueError) as exc:st.warning(str(exc))
            else:st.caption(r['message'])

def game_screen():
    heartbeat()
    if st.session_state.get('sync_error'):
        st.error(st.session_state.sync_error)
        st.download_button('Conserver une copie de secours',json.dumps(st.session_state.game,ensure_ascii=False,indent=2).encode(),'ConsoBingo_secours.json','application/json')
        if st.session_state.get('conflict'):
            st.caption('La copie de secours conserve les réponses de cet onglet. La reprise ci-dessous charge la version enregistrée et reprend la main sur l’autre connexion.')
            if st.button('Recharger la sauvegarde et reprendre ici'):
                try:row=store().claim(st.session_state.cloud_session)
                except CloudError as exc:st.error(str(exc));return
                install_game(game_from_row(row),row);st.rerun()
        elif st.button('Réessayer l’enregistrement'):
            if try_save():after_save();st.rerun()
    event=play(st.session_state.game,ack=st.session_state.get('ack',''),message=st.session_state.get('message',''),error=st.session_state.get('event_error',''),demo=st.session_state.get('demo',False),sync_error=bool(st.session_state.get('sync_error')),disabled=bool(st.session_state.get('sync_error')))
    if isinstance(event,dict) and event.get('nonce') and event['nonce']!=st.session_state.get('ack'):
        st.session_state.ack=event['nonce'];st.session_state.message='';st.session_state.event_error=''
        if st.session_state.get('sync_error'):
            st.session_state.event_error='Réessaie d’abord la sauvegarde ou recharge la partie.';st.rerun()
        try:game,message=process_event(st.session_state.game,event)
        except (ValueError,KeyError,TypeError) as exc:
            st.session_state.event_error=str(exc) if isinstance(exc,ValueError) else 'Cette action n’a pas pu être interprétée.';st.rerun()
        st.session_state.game=game;st.session_state.message=message
        kind=event.get('kind')
        if kind in ('restart','leave'):st.session_state.after_action=kind
        if enqueue_save(finish=kind=='finish'):after_save()
        st.rerun()
    report_panel()


def fetch_students(force=False):
    if force or 'roster_rows' not in st.session_state or time.time()-st.session_state.get('roster_at',0)>60:
        st.session_state.roster_rows=store().dashboard();st.session_state.roster_at=time.time()
    return st.session_state.roster_rows

@st.fragment(run_every=2)
def mail_queue():
    q=st.session_state.get('mail_queue')
    if not q:return
    total=len(q['profiles']);i=q['index']
    st.progress(i/max(total,1),text=f'{i} / {total} courriels traités')
    if st.button('Arrêter les envois restants',disabled=i>=total):q['stopped']=True
    if i<total and not q.get('stopped'):
        profile=q['profiles'][i]
        try:
            game=game_from_row(store().get_run(profile['student_id'])) if q['kind']=='result' else None
            result=dispatch(store(),settings(),profile,q['kind'],q['campaign'],game,extra=q['extra'])
        except Exception:result={'status':'unknown','message':'Cet envoi n’a pas pu être confirmé. Consulter le journal.'}
        q['results'].append({'E-mail':profile['email'],'Statut':result['status'],'Détail':result['message']});q['index']+=1
    if q['results']:st.dataframe(q['results'],hide_index=True,width='stretch')
    if q['index']>=total or q.get('stopped'):st.caption('Traitement terminé ou arrêté. Aucun nouvel envoi automatique.');q['stopped']=True

def teacher_mails(rows):
    conf=settings()
    if not configured(conf):st.info('Renseignez les paramètres Brevo pour activer les envois.');return
    labels={'invitation':'Invitation','reminder':'Rappel','result':'Bilan personnel'}
    kind=st.selectbox('Objet',list(labels),format_func=labels.get)
    eligible=[s for s in rows if (kind!='reminder' or not s.get('completed_at')) and (kind!='result' or s.get('completed_at'))]
    by_id={s['student_id']:s for s in eligible}
    ids=st.multiselect('Destinataires',list(by_id),format_func=lambda k:by_id[k]['first_name']+' '+by_id[k]['last_name']+' · '+by_id[k]['email'])
    extra=st.text_area('Message complémentaire',max_chars=4000)
    signature=json.dumps([kind,sorted(ids),extra],ensure_ascii=False)
    if st.button('Préparer l’aperçu',disabled=not ids):
        sample=by_id[ids[0]]
        try:game=game_from_row(store().get_run(sample['student_id'])) if kind=='result' else None;message=build_message(sample,kind,game,conf.get('APP_URL',''),extra)
        except (CloudError,ValueError) as exc:st.error(str(exc));return
        st.session_state.mail_preview={'signature':signature,'profiles':[by_id[k] for k in ids],'kind':kind,'extra':extra,'message':message,'campaign':str(uuid4())}
    preview=st.session_state.get('mail_preview')
    if preview and preview['signature']==signature:
        st.subheader(preview['message']['subject']);st.text(preview['message']['text'])
        st.dataframe([{'Nom':s['first_name']+' '+s['last_name'],'Destinataire':s['email']} for s in preview['profiles']],hide_index=True)
        confirmed=st.checkbox(f"Envoyer ce message aux {len(preview['profiles'])} destinataires affichés",key='confirm_'+preview['campaign'])
        busy=st.session_state.get('mail_queue',{});busy=busy and not busy.get('stopped') and busy['index']<len(busy['profiles'])
        if st.button('Lancer ces envois',type='primary',disabled=not confirmed or bool(busy)):
            st.session_state.mail_queue={**preview,'index':0,'results':[],'stopped':False};st.session_state.pop('mail_preview',None);st.rerun()
    mail_queue()
    if st.button('Afficher le journal des courriels'):
        try:st.dataframe(store().mails(),hide_index=True,width='stretch')
        except CloudError as exc:st.error(str(exc))

def teacher_screen():
    st.title('ConsoBingo · Espace enseignant')
    st.caption('Suivi de participation et de besoins de révision.')
    left,right=st.columns(2)
    if left.button('Essayer le jeu en démo'):
        st.session_state.demo=True;install_game(new_game());st.rerun()
    if right.button('Se déconnecter'):store().logout();st.session_state.clear();st.rerun()
    try:
        refresh=st.button('Actualiser le suivi');rows=fetch_students(refresh)
    except CloudError as exc:st.error(str(exc));return
    cols=st.columns(3);filters={}
    for col,key,label in zip(cols,['promotion','campus','group_name'],['Promotion','Campus','Groupe']):
        filters[key]=col.selectbox(label,['Tous']+sorted({s[key] for s in rows}))
    rows=[s for s in rows if all(v=='Tous' or s[k]==v for k,v in filters.items())]
    a,b,c=st.columns(3);a.metric('Étudiants',len(rows));b.metric('Parcours commencés',sum(bool(s.get('started_at')) for s in rows));c.metric('Bilans enregistrés',sum(bool(s.get('completed_at')) for s in rows))
    tabs=st.tabs(['Participation','Détail individuel','Courriels','Annuaire'])
    with tabs[0]:
        st.dataframe(dashboard_rows(rows),hide_index=True,width='stretch')
        st.download_button('Exporter ce suivi en CSV',csv_export(rows),'ConsoBingo_suivi.csv','text/csv')
    with tabs[1]:
        started={s['student_id']:s for s in rows if s.get('started_at')}
        sid=st.selectbox('Étudiant',list(started),format_func=lambda k:started[k]['first_name']+' '+started[k]['last_name']) if started else None
        if sid and st.button('Afficher son carnet'):
            try:run=store().get_run(sid);game=game_from_row(run)
            except (CloudError,ValueError) as exc:st.error(str(exc))
            else:
                st.dataframe([{'Activité':x['label'],'Repère':x['status'],'Essais':x['attempts']} for x in summary(game)],hide_index=True)
                st.download_button('Télécharger le carnet PDF',build_pdf(game,started[sid]),'ConsoBingo_carnet.pdf','application/pdf')
    with tabs[2]:teacher_mails(rows)
    with tabs[3]:
        st.write('L’annuaire est partagé avec SWOTmania. Les ajouts, corrections et désactivations sont pris en compte par ConsoBingo sans nouvel import.')
        st.caption('Gérez les inscriptions et les enseignants dans l’application qui possède l’annuaire. Si le script a été configuré avec le préfixe stp, cet annuaire est celui de STP-by-Step.')


def main():
    st.set_page_config(page_title='ConsoBingo',page_icon='✳',layout='wide')
    st.markdown('<style>.block-container{padding-top:1.3rem;padding-bottom:2rem;max-width:1200px}header[data-testid="stHeader"]{display:none}</style>',unsafe_allow_html=True)
    conf=settings()
    if conf['CONSOBINGO_DEMO'] and not st.session_state.get('identity'):
        st.session_state.demo=True
        if 'game' not in st.session_state:install_game(new_game())
        game_screen();return
    if not conf.get('SUPABASE_URL') or not (conf.get('SUPABASE_PUBLISHABLE_KEY') or conf.get('SUPABASE_ANON_KEY')):
        st.title('ConsoBingo');st.info('L’application attend sa configuration.');st.write('Administrateur : exécutez sql/01_installation.sql dans le projet Supabase de SWOTmania, puis renseignez les secrets Streamlit décrits dans DEPLOIEMENT.md.');return
    if not st.session_state.get('identity'):auth_screen();return
    if st.session_state.get('demo'):game_screen();return
    if st.session_state.identity['role']=='teacher':teacher_screen();return
    if 'game' not in st.session_state:start_screen();return
    game_screen()
