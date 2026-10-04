"""Même projet/Auth Supabase que SWOTmania, RPC et résultats propres à ConsoBingo."""
from __future__ import annotations
import copy
from uuid import uuid4
from supabase import create_client
from supabase.lib.client_options import SyncClientOptions
from .engine import summary, validate_game

class CloudError(RuntimeError): pass
class ConflictError(CloudError): pass

class CloudStore:
    def __init__(self,url,public_key,client=None):
        if not url.startswith('https://'): raise ValueError('L’adresse Supabase doit commencer par https://.')
        self.client=client or create_client(url,public_key,options=SyncClientOptions(postgrest_client_timeout=15,storage_client_timeout=15))

    def rpc(self,name,params=None):
        try: return self.client.rpc('conso_'+name,params or {}).execute().data
        except Exception as exc:
            message=str(exc)
            if 'CONSO_CONFLICT' in message or 'CONSO_LEASE' in message:
                raise ConflictError('Une autre connexion a repris ou modifié cette partie. Recharge la sauvegarde avant de continuer.') from None
            if 'CONSO_DENIED' in message: raise CloudError('Cette opération n’est pas autorisée pour ce compte.') from None
            if 'CONSO_NOT_FINISHED' in message: raise CloudError('Enregistre d’abord ton bilan de fin de parcours.') from None
            if 'CONSO_INVALID' in message: raise CloudError('Ces réponses ne peuvent pas être enregistrées dans cette version du jeu.') from None
            raise CloudError('Le suivi est momentanément indisponible. Tes réponses restent dans cet onglet. Réessaie avant de quitter.') from None

    def allowed(self,email,role): return bool(self.rpc('can_login',{'p_email':email,'p_role':role}))
    def send_otp(self,email): self.client.auth.sign_in_with_otp({'email':email,'options':{'should_create_user':True}})
    def login(self,email,code,role):
        self.client.auth.verify_otp({'email':email,'token':code,'type':'email'})
        return self.rpc('identity',{'p_role':role})
    def logout(self):
        try: self.client.auth.sign_out({'scope':'local'})
        except Exception: pass
    def open_session(self): return self.rpc('open_session')
    def get_run(self,student_id=None): return self.rpc('get_run',{'p_student_id':student_id})
    def claim(self,session_id,initial=None): return self.rpc('claim_run',{'p_session_id':session_id,'p_initial_state':initial})
    def save(self,session_id,revision,game,event_id=None,finish=False):
        validate_game(game)
        return self.rpc('save_run',{'p_session_id':session_id,'p_revision':revision,'p_state':game,'p_summary':summary(game),'p_event_id':event_id or str(uuid4()),'p_finish':finish})
    def restart(self,session_id,revision,initial): return self.rpc('restart',{'p_session_id':session_id,'p_revision':revision,'p_initial_state':initial})
    def touch(self,session_id): return self.rpc('touch',{'p_session_id':session_id})
    def close(self,session_id): return self.rpc('close_session',{'p_session_id':session_id})
    def dashboard(self):
        rows=[]
        for offset in range(0,100000,200):
            page=self.rpc('dashboard',{'p_offset':offset,'p_limit':200}) or []
            rows.extend(page)
            if len(page)<200: break
        return rows
    def archives(self,student_id=None): return self.rpc('archived_runs',{'p_student_id':student_id}) or []
    def reserve_mail(self,student_id,kind,campaign): return self.rpc('reserve_mail',{'p_student_id':student_id,'p_kind':kind,'p_campaign':campaign})
    def mark_mail(self,job_id,token,status,error=''): return self.rpc('mark_mail',{'p_job_id':job_id,'p_token':token,'p_status':status,'p_error':error})
    def mails(self): return self.rpc('mails') or []

def game_from_row(row):
    game=copy.deepcopy(row['state']);validate_game(game);return game
