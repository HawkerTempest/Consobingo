"""Brevo : aperçu puis envoi demandé, réservation en base avant tout appel externe."""
from __future__ import annotations
import base64
import html
import re
import smtplib
import ssl
from email.message import EmailMessage
from urllib.parse import urlparse
import requests
from .engine import summary
from .reports import build_pdf

def valid_email(value):return bool(re.fullmatch(r"[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+",str(value)))
def configured(config):return valid_email(config.get('BREVO_SENDER_EMAIL','')) and bool(config.get('BREVO_API_KEY') or (config.get('BREVO_SMTP_USERNAME') and config.get('BREVO_SMTP_PASSWORD')))

def build_message(profile,kind,game=None,app_url='',extra=''):
    if app_url and (urlparse(app_url).scheme!='https' or not urlparse(app_url).netloc):raise ValueError('L’adresse du jeu doit commencer par https://.')
    parts=['Bonjour '+profile.get('first_name','').strip()+',']
    if kind in ('completion','result'):
        if not game or not game.get('finished_at'):raise ValueError('Enregistre le bilan avant de demander son envoi.')
        subject='ConsoBingo : ton carnet d’autoévaluation'
        parts+=['Ton parcours ConsoBingo a été enregistré. Voici ton carnet d’autoévaluation.', '\n'.join(x['label']+' : '+x['status'] for x in summary(game)), 'Tu peux revenir dans le jeu pour reprendre les activités, consulter les explications ou recommencer une partie.']
    elif kind=='invitation':
        subject='ConsoBingo : mène l’enquête dans le parcours de Léa'
        parts+=['Une BD, des indices à retrouver et plusieurs façons de décider : ConsoBingo t’invite à utiliser les notions du cours sur le comportement du consommateur pour conseiller Pulse, une enseigne de salles de gym.', 'L’activité est individuelle et autonome. Connecte-toi avec ton adresse habituelle, puis saisis le code reçu par e-mail.']
    elif kind=='reminder':
        subject='ConsoBingo : ton enquête reste à explorer'
        parts+=['Tu peux commencer ou reprendre ton parcours ConsoBingo. Les indices, les tentatives et les corrigés servent uniquement à ton autoévaluation.', 'Reconnecte-toi avec ton adresse habituelle pour retrouver ta progression.']
    else:raise ValueError('Type de courriel inconnu.')
    if extra.strip():parts.append(extra.strip())
    if app_url:parts.append('Ouvrir ConsoBingo : '+app_url)
    parts.append('L’équipe enseignante\nConsoBingo · Comportement du consommateur')
    return {'subject':subject,'text':'\n\n'.join(parts),'html':'<div style="font-family:Arial,sans-serif;line-height:1.5"><h2>ConsoBingo</h2>'+''.join('<p>'+html.escape(p).replace('\n','<br>')+'</p>' for p in parts)+'</div>'}

class DeliveryError(RuntimeError):
    def __init__(self,status,message):super().__init__(message);self.status=status

def transport_send(config,recipient,message,attachment=None,job_id=None):
    if not configured(config) or not valid_email(recipient):raise DeliveryError('failed','Configuration ou destinataire invalide.')
    sender=config['BREVO_SENDER_EMAIL'];name=config.get('BREVO_SENDER_NAME','ConsoBingo')
    if config.get('BREVO_API_KEY'):
        payload={'sender':{'email':sender,'name':name},'to':[{'email':recipient}],'subject':message['subject'],'textContent':message['text'],'htmlContent':message['html'],'tags':['ConsoBingo']}
        if job_id:payload['headers']={'idempotencyKey':str(job_id)}
        if attachment:payload['attachment']=[{'name':'ConsoBingo_bilan.pdf','content':base64.b64encode(attachment).decode()}]
        try:r=requests.post('https://api.brevo.com/v3/smtp/email',headers={'api-key':config['BREVO_API_KEY'],'accept':'application/json'},json=payload,timeout=(5,20))
        except requests.RequestException:raise DeliveryError('unknown','Brevo n’a pas confirmé l’envoi. Consulter le journal avant de renvoyer.') from None
        if not 200<=r.status_code<300:raise DeliveryError('failed' if 400<=r.status_code<500 else 'unknown',f'Brevo a retourné le statut HTTP {r.status_code}.')
        return
    message_out=EmailMessage();message_out['From']=f'{name} <{sender}>';message_out['To']=recipient;message_out['Subject']=message['subject']
    message_out.set_content(message['text']);message_out.add_alternative(message['html'],subtype='html')
    if attachment:message_out.add_attachment(attachment,maintype='application',subtype='pdf',filename='ConsoBingo_bilan.pdf')
    try:
        port=int(config.get('BREVO_SMTP_PORT',587));host=config.get('BREVO_SMTP_HOST','smtp-relay.brevo.com')
        cls=smtplib.SMTP_SSL if port==465 else smtplib.SMTP
        with cls(host,port,timeout=20,**({'context':ssl.create_default_context()} if port==465 else {})) as smtp:
            smtp.ehlo()
            if port!=465:smtp.starttls(context=ssl.create_default_context());smtp.ehlo()
            smtp.login(config['BREVO_SMTP_USERNAME'],config['BREVO_SMTP_PASSWORD'])
            if smtp.send_message(message_out):raise DeliveryError('failed','Destinataire refusé.')
    except DeliveryError:raise
    except (smtplib.SMTPAuthenticationError,smtplib.SMTPRecipientsRefused,smtplib.SMTPSenderRefused,smtplib.SMTPDataError):raise DeliveryError('failed','Le serveur SMTP a refusé l’envoi.') from None
    except Exception:raise DeliveryError('unknown','L’envoi SMTP n’est pas confirmé. Consulter le journal avant de renvoyer.') from None

def dispatch(store,config,profile,kind,campaign,game=None,extra='',sender=transport_send):
    if not configured(config):return {'status':'not_configured','message':'L’envoi de courriels n’est pas configuré.'}
    message=build_message(profile,kind,game,config.get('APP_URL',''),extra)
    attachment=build_pdf(game,profile) if game and kind in ('completion','result') and config.get('EMAIL_ATTACH_PDF',True) else None
    job=store.reserve_mail(profile['student_id'],kind,campaign)
    if not job['allowed']:return {'status':job['status'],'skipped':True,'message':'Ce courriel figure déjà dans le journal. Aucun nouvel envoi.'}
    status,explanation='sent','Courriel accepté par le service d’envoi.'
    try:
        if job['recipient'].lower()!=profile['email'].lower():raise DeliveryError('failed','L’adresse a changé depuis l’aperçu. Actualise la sélection.')
        sender(config,job['recipient'],message,attachment,job_id=job['job_id'])
    except DeliveryError as e:status,explanation=e.status,str(e)
    except Exception:status,explanation='unknown','Résultat de l’envoi non confirmé. Consulter le journal du fournisseur.'
    try:store.mark_mail(job['job_id'],job['token'],status,'' if status=='sent' else explanation)
    except Exception:return {'status':'unknown','message':'L’envoi n’a pas pu être confirmé dans le suivi. Consulter le journal avant de renvoyer.'}
    return {'status':status,'message':explanation}
