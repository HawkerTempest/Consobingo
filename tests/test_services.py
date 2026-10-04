from types import SimpleNamespace
from uuid import uuid4
import pytest
import requests
from consobingo import engine as E
from consobingo import mailer as M
from consobingo.cloud import CloudStore,CloudError,ConflictError
from consobingo.reports import build_pdf,csv_export


PROFILE={'student_id':'demo1','first_name':'Léa','last_name':'Test','email':'lea@example.org','promotion':'2026','campus':'Test','group_name':'A'}
CONF={'BREVO_SENDER_EMAIL':'sender@example.org','BREVO_API_KEY':'test_key_not_real','APP_URL':'https://example.org','EMAIL_ATTACH_PDF':True}


class MailStore:
    def __init__(self,allowed=True):self.allowed=allowed;self.sent=[]
    def reserve_mail(self,*args):return {'allowed':self.allowed,'status':'sent','recipient':PROFILE['email'],'job_id':str(uuid4()),'token':str(uuid4())}
    def mark_mail(self,*args):self.sent.append(args)


def test_mail_duplicate_reservation_prevents_transport():
    def forbidden(*a,**k):raise AssertionError('No transport expected')
    r=M.dispatch(MailStore(False),CONF,PROFILE,'invitation','campaign',sender=forbidden)
    assert r['skipped']


def test_mail_send_and_uncertain_timeout_are_journaled():
    s=MailStore();sent=[]
    r=M.dispatch(s,CONF,PROFILE,'invitation','campaign',sender=lambda *a,**k:sent.append(a))
    assert r['status']=='sent' and len(sent)==1 and s.sent[0][2]=='sent'
    def timeout(*a,**k):raise M.DeliveryError('unknown','Non confirmé')
    r=M.dispatch(s,CONF,PROFILE,'invitation','new',sender=timeout)
    assert r['status']=='unknown' and s.sent[-1][2]=='unknown'


def test_changed_recipient_cannot_be_silently_mailed():
    s=MailStore();profile={**PROFILE,'email':'changed@example.org'}
    def forbidden(*a,**k):raise AssertionError('No transport expected')
    assert M.dispatch(s,CONF,profile,'invitation','campaign',sender=forbidden)['status']=='failed'


def test_brevo_payload_and_no_retry_after_timeout(monkeypatch):
    calls=[]
    def fake_post(*a,**k):calls.append((a,k));return SimpleNamespace(status_code=201)
    monkeypatch.setattr(M.requests,'post',fake_post)
    job=str(uuid4());message=M.build_message(PROFILE,'invitation',app_url='https://example.org')
    M.transport_send(CONF,PROFILE['email'],message,job_id=job)
    assert len(calls)==1 and calls[0][1]['json']['headers']['idempotencyKey']==job
    assert calls[0][1]['json']['to']==[{'email':PROFILE['email']}]
    def timeout(*a,**k):raise requests.Timeout()
    monkeypatch.setattr(M.requests,'post',timeout)
    with pytest.raises(M.DeliveryError) as e:M.transport_send(CONF,PROFILE['email'],message)
    assert e.value.status=='unknown'


def test_pdf_export_and_mail_remain_formative():
    g=E.new_game(33);E.apply_solution(g,'factors');g['finished_at']=E.now()
    assert build_pdf(g,PROFILE).startswith(b'%PDF-')
    message=M.build_message(PROFILE,'completion',g,'https://example.org')
    assert 'aucune note académique' in message['text'] and 'Corrigé consulté' in message['text']


def test_csv_neutralizes_formula_and_contains_no_grade():
    row={**PROFILE,'first_name':'=HYPERLINK("bad")','summary':E.summary(E.new_game(1))}
    result=csv_export([row]).decode('utf-8-sig')
    assert "'=HYPERLINK" in result and 'Note académique' not in result


@pytest.mark.parametrize('source,expected',[('CONSO_LEASE',ConflictError),('CONSO_CONFLICT',ConflictError),('CONSO_DENIED',CloudError),('apikey private data',CloudError)])
def test_rpc_failures_do_not_disclose_technical_secrets(source,expected):
    class Client:
        def rpc(self,*a):raise RuntimeError(source)
    s=CloudStore('https://example.supabase.co','public',client=Client())
    with pytest.raises(expected) as e:s.get_run()
    assert 'apikey' not in str(e.value) and 'private data' not in str(e.value)
